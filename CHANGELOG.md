# Changelog

## 1.0.0

- Add async register reads, validated writes, power controls, and packed fan controls.
- Add immutable state, optional diagnostics, typed errors, and synthetic protocol tests.
- Preserve polls for unknown power codes, nonzero boolean values, and unsupported
  fan channels; expose unknown labels/optional fan values while keeping writes strict.
- Suppress absolute power toggles for unknown power states and zero stale readings.
