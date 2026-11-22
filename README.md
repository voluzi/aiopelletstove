# aiopelletstove

[![PyPI version](https://img.shields.io/pypi/v/aiopelletstove)](https://pypi.org/project/aiopelletstove/)
[![Python versions](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB)](https://pypi.org/project/aiopelletstove/)
[![Latest GitHub release](https://img.shields.io/github/v/release/voluzi/aiopelletstove)](https://github.com/voluzi/aiopelletstove/releases/latest)
[![CI](https://github.com/voluzi/aiopelletstove/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/voluzi/aiopelletstove/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A typed asyncio client for reading and controlling Wi-Fi pellet stoves over
the local Micronova-style HTTP register interface. Read a complete stove state,
write individual settings, or use the higher level power and fan controls.

## Install

```sh
python -m pip install aiopelletstove
```

## Quick start

Set `PELLET_STOVE_HOST` to your stove's local hostname or address before
running the example.

```python
import asyncio
import os

from aiopelletstove import PelletStove, StoveState


async def read_stove() -> StoveState:
    async with PelletStove(os.environ["PELLET_STOVE_HOST"]) as stove:
        return await stove.async_get_state()


state = asyncio.run(read_stove())
print(f"Room temperature: {state.air_temperature:.1f} °C")
print(f"Power state: {state.power_state.label}")
```

## API

| API | Purpose |
| --- | --- |
| `PelletStove(host, *, session=None, timeout=5.0)` | Create a client for a hostname or address with optional port. |
| `async_get_state(include_diagnostics=True)` | Read common status and preferences into an immutable `StoveState`. Set `include_diagnostics=False` to skip alarm and usage counters; those fields will be `None`. |
| `async_read(register)`, `async_read_many(registers)` | Read and decode registers. Batch reads issue one request per register category. |
| `async_write(register, value)` | Validate and write a register, then return the decoded readback. |
| `async_set_power(on)` | Toggle only when the reported state requires it and return a `PowerCommandOutcome` (`toggled`, `unchanged`, or `blocked`, plus the state read under the request lock). Unknown states and `TOGGLE_BLOCKED_STATES` (final cleaning, standby, alarms) block toggles. The stove typically reports the new power state a minute or more after a toggle and keeps the old state until then, so do not repeat the command in that window: a second toggle cancels the first. `PelletStovePowerOutcomeUnknownError` means the toggle was sent without a readable acknowledgement. |
| `async_toggle_power()` | Send the raw toggle command. Prefer `async_set_power` when you know the desired state. |
| `async_set_fan_regulation(channel, value)` | Set `fan2` or `fan3` to `off`, `1`–`5`, or `auto` while preserving the other channel. |
| `async_close()` | Close the client-owned session. The async context manager also closes it. |

Register definitions and encoding helpers live in
[`aiopelletstove.registers`](src/aiopelletstove/registers.py).
The caller remains responsible for an injected `aiohttp.ClientSession`.
Each client sends one request at a time, with an idle gap of at least 100 ms
after a read and 150 ms after a write or power toggle. Polling cannot interrupt
a command's sequence of requests. Use one client per stove to share the queue.

Unknown power codes retain their integer value with a label of
`unknown_<code>` and `is_known=False`. The enum reports both active heating and
ashpan cleaning as `on`. Off and unknown states zero stale power, flue
temperature, and fan speed. A fan channel with an unsupported code is `None`;
the client refuses a write that would overwrite an unknown setting on the
other channel.

## Errors

| Error | Meaning |
| --- | --- |
| `PelletStoveError` | Base class for client and protocol errors |
| `PelletStoveConnectionError` | HTTP transport failure or timeout |
| `PelletStoveResponseError` | Malformed, incomplete, or rejected response |
| `PelletStoveRejectedError` | Explicit rejection by the stove; a `PelletStoveResponseError` |
| `PelletStovePowerOutcomeUnknownError` | A power toggle was sent but its acknowledgement was lost or unreadable |
| `PelletStoveReadOnlyError` | Attempted write to a read-only register |
| `PelletStoveValueError` | Invalid host or unsupported or out-of-range input; also a `ValueError` |

## Compatibility

Requires Python **3.11 or later** and `aiohttp>=3.9,<4`. CI tests Python 3.11,
3.12, 3.13, and 3.14. The package includes type information.

The stove's Wi-Fi module and firmware must expose the local HTTP form API
and the RAM and EEPROM registers defined in this package. Compatibility
depends on the register layout; the package does not verify models by name.
Requests use plain HTTP with no login handshake or internal retries. A
timeout applies to each request, so operations spanning several categories
can take longer than one timeout.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and test instructions,
[CHANGELOG.md](CHANGELOG.md) for release notes, and [SECURITY.md](SECURITY.md)
for private vulnerability reporting.

## License

[MIT](LICENSE).
