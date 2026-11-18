# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-18

### Added

- Typed async register reads, validated writes, and power and fan controls.
- Immutable state snapshots, optional diagnostics, and specific exception types.
- Keep supported readings available when a power code, fan code, or Boolean
  reading is outside the usual range. Writes still validate their inputs.
- Block absolute power toggles for unknown power states and zero stale readings.

[1.0.0]: https://github.com/voluzi/aiopelletstove/tree/v1.0.0
