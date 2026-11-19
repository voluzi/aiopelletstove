import asyncio

import aiohttp
import pytest
from aioresponses import CallbackResult

from aiopelletstove import (
    PelletStove,
    PelletStoveConnectionError,
    PelletStovePowerOutcomeUnknownError,
    PelletStoveRejectedError,
    PelletStoveResponseError,
    PelletStoveValueError,
    PowerResult,
    PowerState,
)
from aiopelletstove import registers as r

URL = "http://stove.example/ajax/get-registers"
SET_URL = "http://stove.example/ajax/set-register"


async def test_state_uses_one_request_per_category(http, frames):
    for category in (2, 11, 5):
        http.post(URL, payload=frames[category])
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state()
    assert state.air_temperature == 21.5
    assert state.flue_temperature == 118
    assert state.fan_speed == 860
    assert state.power_state == PowerState.RUNNING
    assert state.total_hours == 4660
    assert state.partial_hours == 266
    assert state.ignition_count == 766
    assert state.fan2_regulation.value == "2"
    assert state.fan3_regulation.value == "auto"
    calls = [call for group in http.requests.values() for call in group]
    assert [call.kwargs["data"] for call in calls] == [
        {"key": "020", "category": str(cat)} for cat in (2, 11, 5)
    ]


async def test_off_state_zeroes_stale_values(http, frames):
    frames[2]["ram"][2][2] = 0
    for cat in (2, 11):
        http.post(URL, payload=frames[cat])
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state(include_diagnostics=False)
    assert (state.current_power, state.flue_temperature, state.fan_speed) == (0, 0, 0)
    assert state.air_temperature == 21.5
    assert state.total_hours is None


@pytest.mark.parametrize("state", range(10))
@pytest.mark.parametrize("on", [True, False])
async def test_absolute_power_only_toggles_when_needed(http, state, on):
    http.post(URL, payload={"ram": [[0, 33, state]], "eep": []})
    blocked = state in {6, 7, 8, 9}
    should_toggle = not blocked and ((state in {1, 2, 3, 4, 5}) != on)
    if should_toggle:
        http.post(URL, payload={"result": True})
    async with PelletStove("stove.example") as stove:
        outcome = await stove.async_set_power(on)
    assert outcome.state == state
    assert outcome.result == (
        PowerResult.BLOCKED
        if blocked
        else PowerResult.TOGGLED
        if should_toggle
        else PowerResult.UNCHANGED
    )
    calls = [call for group in http.requests.values() for call in group]
    assert len(calls) == 1 + should_toggle
    if should_toggle:
        assert calls[-1].kwargs["data"] == {"key": "022"}


@pytest.mark.parametrize(
    "which,value,expected", [("fan2", "4", 100), ("fan3", "1", 18)]
)
async def test_fan_write_preserves_other_channel(http, which, value, expected):
    http.post(URL, payload={"ram": [], "eep": [[1, 126, 98]]})
    http.post(SET_URL, payload={"result": True})
    http.post(URL, payload={"ram": [], "eep": [[1, 126, expected]]})
    async with PelletStove("stove.example") as stove:
        await stove.async_set_fan_regulation(which, value)
    write = next(
        calls for key, calls in http.requests.items() if str(key[1]) == SET_URL
    )
    assert write[0].kwargs["data"] == {
        "key": "002",
        "memory": "1",
        "regId": "126",
        "value": str(expected),
    }


async def test_simultaneous_fan_writes_preserve_both_channels(http):
    packed = 98

    async def read(url, **kwargs):
        snapshot = packed
        await asyncio.sleep(0)
        return CallbackResult(payload={"ram": [], "eep": [[1, 126, snapshot]]})

    def write(url, **kwargs):
        nonlocal packed
        packed = int(kwargs["data"]["value"])
        return CallbackResult(payload={"result": True})

    http.post(URL, callback=read, repeat=True)
    http.post(SET_URL, callback=write, repeat=True)
    async with PelletStove("stove.example") as stove:
        await asyncio.gather(
            stove.async_set_fan_regulation("fan2", "4"),
            stove.async_set_fan_regulation("fan3", "1"),
        )
    assert packed == 20


@pytest.mark.parametrize(
    "body",
    [
        "broken",
        "[]",
        '{"result": false}',
        '{"ram": null}',
        '{"ram": [[0]]}',
        '{"ram": [[0, 1, "bad"]]}',
    ],
)
async def test_bad_responses_are_typed_errors(http, body):
    http.post(URL, body=body)
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveResponseError):
            await stove.async_read(r.AIR_TEMPERATURE)


@pytest.mark.parametrize("error", [aiohttp.ClientConnectionError(), TimeoutError()])
async def test_transport_errors(http, error):
    http.post(URL, exception=error)
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveConnectionError):
            await stove.async_read(r.AIR_TEMPERATURE)


async def test_missing_counter_high_byte_is_rejected(http):
    http.post(URL, payload={"eep": [[1, 234, 1]], "ram": []})
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveResponseError):
            await stove.async_read(r.TOTAL_HOURS)


@pytest.mark.parametrize("operation", ["write", "toggle"])
async def test_device_rejection(http, operation):
    http.post(SET_URL if operation == "write" else URL, payload={"result": False})
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveResponseError):
            if operation == "write":
                await stove.async_write(r.POWER_LEVEL, 3)
            else:
                await stove.async_toggle_power()


async def test_injected_session_remains_open(http, frames):
    http.post(URL, payload=frames[2])
    async with aiohttp.ClientSession() as session:
        async with PelletStove("stove.example", session=session) as stove:
            assert await stove.async_read(r.TARGET_TEMPERATURE) == 23
        assert not session.closed


@pytest.mark.parametrize(
    "register,value,raw", [(r.TARGET_TEMPERATURE, 24, 24), (r.STANDBY_MODE, False, 0)]
)
async def test_write_returns_confirmed_readback(http, register, value, raw):
    http.post(SET_URL, payload={"result": True})
    http.post(URL, payload={"ram": [], "eep": [[1, register.reg_id, raw]]})
    async with PelletStove("stove.example") as stove:
        assert await stove.async_write(register, value) == value
    write_calls = next(
        calls for key, calls in http.requests.items() if str(key[1]) == SET_URL
    )
    assert write_calls[0].kwargs["data"]["value"] == str(raw)


async def test_concurrent_power_commands_serialise_when_readback_is_immediate(http):
    # The real stove keeps the old state for a minute or more after a toggle;
    # callers must suppress repeats in that window (see async_set_power).
    state = 0
    toggles = 0

    async def respond(url, **kwargs):
        nonlocal state, toggles
        await asyncio.sleep(0)
        if kwargs["data"]["key"] == "022":
            toggles += 1
            state = 3
            return CallbackResult(payload={"result": True})
        return CallbackResult(payload={"ram": [[0, 33, state]], "eep": []})

    http.post(URL, callback=respond, repeat=True)
    async with PelletStove("stove.example") as stove:
        await asyncio.gather(stove.async_set_power(True), stove.async_set_power(True))
    assert toggles == 1


async def test_http_status_failure(http):
    http.post(URL, status=503)
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveConnectionError):
            await stove.async_read(r.POWER_STATE)


@pytest.mark.parametrize("raw", [-1, 10, 42])
@pytest.mark.parametrize("on", [False, True])
async def test_unknown_power_state_never_auto_toggles(http, raw, on):
    http.post(URL, payload={"ram": [[0, 33, raw]], "eep": []})
    async with PelletStove("stove.example") as stove:
        outcome = await stove.async_set_power(on)
    assert outcome.result == PowerResult.BLOCKED
    calls = [call for group in http.requests.values() for call in group]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "host", ["http://stove.example", "stove.example/path", "", "stove.example:invalid"]
)
def test_invalid_host_is_rejected(host):
    with pytest.raises(PelletStoveValueError):
        PelletStove(host)


async def test_unknown_power_state_preserves_poll(http, frames):
    frames[2]["ram"][2][2] = 42
    for category in (2, 11):
        http.post(URL, payload=frames[category])
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state(include_diagnostics=False)
    assert state.power_state.label == "unknown_42"
    assert not state.power_state.is_on
    assert (state.current_power, state.flue_temperature, state.fan_speed) == (0, 0, 0)
    assert state.air_temperature == 21.5


@pytest.mark.parametrize(
    "raw,fan2,fan3", [(103, None, "auto"), (114, "2", None), (119, None, None)]
)
async def test_unknown_fan_channels_preserve_poll(http, frames, raw, fan2, fan3):
    frames[11]["eep"][3][2] = raw
    for category in (2, 11):
        http.post(URL, payload=frames[category])
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state(include_diagnostics=False)
    assert state.fan2_regulation == fan2
    assert state.fan3_regulation == fan3
    assert state.power_state == PowerState.RUNNING
    assert state.air_temperature == 21.5


async def test_nonzero_boolean_preserves_poll(http, frames):
    frames[11]["eep"][1][2] = 2
    for category in (2, 11):
        http.post(URL, payload=frames[category])
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state(include_diagnostics=False)
    assert state.buzzer is True
    assert state.air_temperature == 21.5


@pytest.mark.parametrize("which,raw", [("fan2", 114), ("fan3", 103)])
async def test_fan_write_rejects_unknown_other_channel(http, which, raw):
    http.post(URL, payload={"ram": [], "eep": [[1, 126, raw]]})
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveValueError):
            await stove.async_set_fan_regulation(which, "4")
    assert all(str(key[1]) != SET_URL for key in http.requests)


@pytest.mark.parametrize(
    "toggle_reply",
    [
        {"exception": aiohttp.ClientConnectionError()},
        {"body": "not json"},
        {"payload": {"ok": 1}},
    ],
)
async def test_lost_toggle_acknowledgement_is_unknown_outcome(http, toggle_reply):
    http.post(URL, payload={"ram": [[0, 33, 0]], "eep": []})
    http.post(URL, **toggle_reply)
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStovePowerOutcomeUnknownError):
            await stove.async_set_power(True)


async def test_rejected_toggle_is_not_unknown_outcome(http):
    http.post(URL, payload={"ram": [[0, 33, 0]], "eep": []})
    http.post(URL, payload={"result": False})
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveRejectedError):
            await stove.async_set_power(True)


async def test_failed_power_read_sends_no_toggle(http):
    http.post(URL, exception=aiohttp.ClientConnectionError())
    async with PelletStove("stove.example") as stove:
        with pytest.raises(PelletStoveConnectionError):
            await stove.async_set_power(True)
    calls = [call for group in http.requests.values() for call in group]
    assert len(calls) == 1
