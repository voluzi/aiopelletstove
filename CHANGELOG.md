# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-19

### Changed

- Each client sends one request at a time and waits at least 100 ms after a read
  or 150 ms after a write or toggle before sending the next request. Polling
  cannot interleave with a command's requests.
- `async_set_power` returns a `PowerCommandOutcome` with the result and the
  power state read under the request lock.
- `async_set_power` no longer toggles in standby or alarm states, where the
  effect of the toggle is undocumented.
- `async_set_power` raises `PelletStovePowerOutcomeUnknownError` when the
  toggle was sent but its acknowledgement was lost or unreadable, and
  `PelletStoveRejectedError` (a `PelletStoveResponseError`) when the stove
  rejects a request.

## [1.0.0] - 2026-11-18

### Added

- Typed async register reads, validated writes, and power and fan controls.
- Immutable state snapshots, optional diagnostics, and specific exception types.
- Keep supported readings available when a power code, fan code, or Boolean
  reading is outside the usual range. Writes still validate their inputs.
- Block absolute power toggles for unknown power states and zero stale readings.

[1.1.0]: https://github.com/voluzi/aiopelletstove/tree/v1.1.0
[1.0.0]: https://github.com/voluzi/aiopelletstove/tree/v1.0.0
