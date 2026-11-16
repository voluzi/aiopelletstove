# aiopelletstove

Typed, asyncio-native HTTP register client for Wi-Fi pellet stoves using the
Micronova-style RAM/EEPROM interface. Python 3.11 or newer; MIT licensed.

```python
import asyncio
from aiopelletstove import PelletStove
from aiopelletstove.registers import TARGET_TEMPERATURE


async def main():
    async with PelletStove("stove.example") as stove:
        state = await stove.async_get_state()
        print(state.air_temperature)
        await stove.async_write(TARGET_TEMPERATURE, 23)


asyncio.run(main())
```

The example hostname is reserved for documentation. Supply your own host at
runtime. Requests use plain HTTP form posts, a five-second timeout, and no
internal retries. The register interface does not use a login handshake.

Pass `session=` to reuse an aiohttp session. The caller owns injected sessions;
the client closes its own session with `async_close()` or an async context manager.
`async_read` / `async_read_many` decode registers and group reads by category.
`async_write` validates bounds/read-only status and returns the decoded readback.
`async_set_power(on)` reads the current state and only toggles when needed;
final cleaning blocks toggles. `async_toggle_power()` is the raw toggle command.
`async_set_fan_regulation("fan2", "auto")` preserves the other packed fan channel.
Commands are serialized within each client, including read-modify-write sequences.
Other clients controlling the same stove cannot participate in that lock.

`StoveState` is immutable. OFF zeroes stale power, flue temperature, and fan speed.
Power labels preserve the legacy protocol (`on` for running/ashpan cleaning).
Use `async_get_state(include_diagnostics=False)` for fast polling; its optional
counter fields are `None`. Callers retain prior diagnostics and fetch them on a
slower cadence. Common and preference categories are always fetched.

Errors derive from `PelletStoveError`: connection/timeouts, invalid/rejected
responses, read-only writes, and invalid values have distinct exception types.
The library ships `py.typed`; register and encoding helpers are public in
`aiopelletstove.registers`.

## Development

```sh
python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --strict src
.venv/bin/pytest -q
.venv/bin/python -m build
```

Tests use invented register frames and intercepted HTTP requests; no device is
needed. Development dependencies limit aiohttp to below 3.14 while aioresponses
adapts to its changed response constructor; the runtime dependency supports aiohttp 3.x. Tagged `v*` releases build a wheel/sdist and use PyPI trusted publishing.
Before publishing, confirm package name availability and configure the PyPI
project, GitHub environment `pypi`, and OIDC publisher. No publishing is needed
for local development.
