# NestLedger Final Audit

This package was re-audited from the current deployed ZIP.

Checks/fixes included:
- Apartment availability route compatibility (`/api/auth/apartments` plus legacy alias).
- A–M, 1–7 apartment validation and uniqueness hardening.
- Normalization of legacy apartment whitespace/casing before uniqueness enforcement.
- Duplicate-submit guards and PostgreSQL advisory transaction locks for work orders, notices, expenses, and maintenance bills.
- Fixed notification badge placement outside the bell and corrected hidden-panel outside-click handling.
- Fixed notice submission response handling.
- Added login/registration/rating submit locks.
- Prevented page-load stale-response handling from turning successful POST/PUT/PATCH/DELETE requests into false failures.
- Voice assistant remains continuous/restarting while enabled and now exposes a visible `Listening…` status in the AK header.
- Frontend asset/version references checked.
- JavaScript syntax and Python compilation checked.
- Generated Python caches removed from the release package.

A live Flask integration suite could not be executed in this isolated audit environment because the Flask runtime dependencies are not installed here. Static, syntax, route, asset, and package-integrity checks were performed instead.
