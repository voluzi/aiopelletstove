"""Async HTTP client for the register protocol."""

import asyncio
from collections.abc import Sequence
from types import TracebackType
from typing import Literal, Self

import aiohttp
from yarl import URL

from . import registers as r
from .const import (
    API_KEY_GET_REGISTERS,
    API_KEY_SET_REGISTER,
    API_KEY_TOGGLE_POWER,
)
from .exceptions import (
    PelletStoveConnectionError,
    PelletStovePowerOutcomeUnknownError,
    PelletStoveRejectedError,
    PelletStoveResponseError,
    PelletStoveValueError,
)
from .models import (
    TOGGLE_BLOCKED_STATES,
    FanRegulation,
    PowerCommandOutcome,
    PowerResult,
    PowerState,
    StoveState,
)

_READ_GAP = 0.1
_WRITE_GAP = 0.15


class PelletStove:
    """A stove client; injected sessions remain owned by their caller."""

    def __init__(
        self,
        host: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 5.0,
    ) -> None:
        try:
            url = URL(f"http://{host}")
            if (
                not url.host
                or url.user is not None
                or url.path not in ("", "/")
                or url.query_string
                or url.fragment
                or "/" in host
            ):
                raise ValueError("Expected a hostname with optional port")
            _ = url.port
        except ValueError as err:
            raise PelletStoveValueError("Invalid stove host") from err
        self._base_url = str(url).rstrip("/")
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._request_lock = asyncio.Lock()
        self._next_request_at = float("-inf")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.async_close()

    async def async_close(self) -> None:
        """Close only a session created by this client."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _post_unlocked(
        self, path: str, data: dict[str, str]
    ) -> dict[str, object]:
        loop = asyncio.get_running_loop()
        while (now := loop.time()) < self._next_request_at:
            remaining = self._next_request_at - now
            await asyncio.sleep(remaining)
        if self._session is None:
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.post(
                self._base_url + path,
                data=data,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                try:
                    payload: object = await response.json(content_type=None)
                except (ValueError, UnicodeError) as err:
                    raise PelletStoveResponseError("Invalid JSON response") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PelletStoveConnectionError("Stove request failed") from err
        finally:
            gap = (
                _WRITE_GAP
                if data.get("key") in (API_KEY_SET_REGISTER, API_KEY_TOGGLE_POWER)
                else _READ_GAP
            )
            self._next_request_at = loop.time() + gap
        if not isinstance(payload, dict):
            raise PelletStoveResponseError("Invalid stove response")
        if payload.get("result") is False:
            raise PelletStoveRejectedError("Stove rejected the request")
        return payload

    async def _fetch_category_unlocked(
        self, category: int
    ) -> dict[tuple[r.Memory, int], int]:
        payload = await self._post_unlocked(
            "/ajax/get-registers",
            {
                "key": API_KEY_GET_REGISTERS,
                "category": str(category),
            },
        )
        result: dict[tuple[r.Memory, int], int] = {}
        for memory in ("ram", "eep"):
            rows = payload.get(memory, [])
            if not isinstance(rows, list):
                raise PelletStoveResponseError("Invalid register array")
            for row in rows:
                if (
                    not isinstance(row, list)
                    or len(row) < 3
                    or type(row[1]) is not int
                    or type(row[2]) is not int
                ):
                    raise PelletStoveResponseError("Invalid register row")
                mem: r.Memory = "ram" if memory == "ram" else "eep"
                result[(mem, row[1])] = row[2]
        return result

    @staticmethod
    def _decode_register(
        reg: r.Register, raw: dict[tuple[r.Memory, int], int]
    ) -> r.Value:
        try:
            value = raw[(reg.memory, reg.reg_id)]
            if reg.high_byte_reg_id is not None:
                value = r.combine_bytes(value, raw[(reg.memory, reg.high_byte_reg_id)])
        except KeyError as err:
            raise PelletStoveResponseError(f"Missing register: {reg.name}") from err
        return r.decode(reg, value)

    async def async_read_many(self, regs: Sequence[r.Register]) -> dict[str, r.Value]:
        """Fetch each distinct category once, rejecting incomplete responses."""
        raw: dict[tuple[r.Memory, int], int] = {}
        for category in dict.fromkeys(reg.category for reg in regs):
            async with self._request_lock:
                raw.update(await self._fetch_category_unlocked(category))
        return {reg.name: self._decode_register(reg, raw) for reg in regs}

    async def async_read(self, reg: r.Register) -> r.Value:
        async with self._request_lock:
            return await self._read_unlocked(reg)

    async def _read_unlocked(self, reg: r.Register) -> r.Value:
        return self._decode_register(
            reg, await self._fetch_category_unlocked(reg.category)
        )

    async def _write_unlocked(self, reg: r.Register, value: r.Value) -> r.Value:
        raw = r.encode(reg, value)
        response = await self._post_unlocked(
            "/ajax/set-register",
            {
                "key": API_KEY_SET_REGISTER,
                "memory": "0" if reg.memory == "ram" else "1",
                "regId": str(reg.reg_id),
                "value": str(raw),
            },
        )
        if response.get("result") is not True:
            raise PelletStoveResponseError("Write was not acknowledged")
        return await self._read_unlocked(reg)

    async def async_write(self, reg: r.Register, value: r.Value) -> r.Value:
        """Write and return the decoded readback."""
        async with self._request_lock:
            return await self._write_unlocked(reg, value)

    async def _toggle_unlocked(self) -> bool:
        response = await self._post_unlocked(
            "/ajax/get-registers", {"key": API_KEY_TOGGLE_POWER}
        )
        if response.get("result") is not True:
            raise PelletStoveResponseError("Toggle was not acknowledged")
        return True

    async def async_toggle_power(self) -> bool:
        """Send the raw toggle command; prefer async_set_power for controls."""
        async with self._request_lock:
            return await self._toggle_unlocked()

    async def async_set_power(self, on: bool) -> PowerCommandOutcome:
        """Toggle only when needed, judged from a read under the request lock.

        No toggle is sent for unknown states or ``TOGGLE_BLOCKED_STATES``.
        ``TOGGLED`` means the stove acknowledged the toggle; it typically
        reports the new power state a minute or more later, and the register
        keeps the old state until then. Callers must not repeat the command in
        that window: a second toggle cancels the first.

        Raises ``PelletStovePowerOutcomeUnknownError`` when the toggle was sent
        but its acknowledgement was lost or unreadable, and
        ``PelletStoveRejectedError`` when the stove explicitly rejected it.
        Other errors mean no toggle was sent.
        """
        async with self._request_lock:
            state = PowerState(int(await self._read_unlocked(r.POWER_STATE)))
            if not state.is_known or state in TOGGLE_BLOCKED_STATES:
                return PowerCommandOutcome(PowerResult.BLOCKED, state)
            if state.is_on == on:
                return PowerCommandOutcome(PowerResult.UNCHANGED, state)
            try:
                await self._toggle_unlocked()
            except PelletStoveRejectedError:
                raise
            except (PelletStoveConnectionError, PelletStoveResponseError) as err:
                raise PelletStovePowerOutcomeUnknownError(
                    "Power toggle sent without a readable acknowledgement"
                ) from err
            return PowerCommandOutcome(PowerResult.TOGGLED, state)

    async def async_set_fan_regulation(
        self,
        which: Literal["fan2", "fan3"],
        value: str,
    ) -> None:
        try:
            selected = FanRegulation(value)
        except ValueError as err:
            raise PelletStoveValueError("Invalid fan regulation") from err
        if which not in ("fan2", "fan3"):
            raise PelletStoveValueError("Unknown fan channel")
        async with self._request_lock:
            fan2, fan3 = r.unpack_fans(int(await self._read_unlocked(r.FAN_REGULATION)))
            fan2 = selected if which == "fan2" else fan2
            fan3 = selected if which == "fan3" else fan3
            if fan2 is None or fan3 is None:
                raise PelletStoveValueError("Cannot preserve unknown fan regulation")
            packed = r.pack_fans(fan2, fan3)
            await self._write_unlocked(r.FAN_REGULATION, packed)

    async def async_get_state(self, *, include_diagnostics: bool = True) -> StoveState:
        """Fetch common/preferences and optionally the slow diagnostic counters."""
        regs: tuple[r.Register, ...] = r.COMMON_REGISTERS + r.PREFERENCE_REGISTERS
        if include_diagnostics:
            regs += r.DIAGNOSTIC_REGISTERS
        values = await self.async_read_many(regs)
        power_state = PowerState(int(values["power_state"]))
        fan2, fan3 = r.unpack_fans(int(values["fan_regulation"]))
        off = power_state == PowerState.OFF or not power_state.is_known
        return StoveState(
            air_temperature=float(values["air_temperature"]),
            flue_temperature=0 if off else int(values["flue_temperature"]),
            power_state=power_state,
            current_power=0 if off else int(values["current_power"]),
            fan_speed=0 if off else int(values["fan_speed"]),
            target_temperature=int(values["target_temperature"]),
            power_level=int(values["power_level"]),
            standby_mode=bool(values["standby_mode"]),
            buzzer=bool(values["buzzer"]),
            enable_fan=bool(values["enable_fan"]),
            fan2_regulation=fan2,
            fan3_regulation=fan3,
            last_alarm=int(values["last_alarm"]) if include_diagnostics else None,
            total_hours=int(values["total_hours"]) if include_diagnostics else None,
            partial_hours=int(values["partial_hours"]) if include_diagnostics else None,
            ignition_count=int(values["ignition_count"])
            if include_diagnostics
            else None,
        )
