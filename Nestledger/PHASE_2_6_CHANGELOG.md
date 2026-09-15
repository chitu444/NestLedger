# NestLedger Phase 2.6 — Financial Integrity + Database Hardening

- Bumped the build marker to `PHASE-2.6-2026-09-15-01`.
- Financial amount columns now use `Numeric(12,2)` in the ORM.
- Added migration 6 for PostgreSQL exact two-decimal storage, with validation before conversion.
- SQLite skips in-place type conversion because SQLite cannot safely alter an existing column type; application validation remains authoritative.
- API serialization rounds stored amounts to two decimals while preserving the existing numeric JSON contract.
- Updated migration documentation through migration 6.

## Validation
- Python compilation passed.
- JavaScript syntax checks passed.
- ZIP integrity passed.
- Full Flask runtime tests were unavailable because Flask dependencies are not installed in this build environment.
