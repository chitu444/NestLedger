# NestLedger Phase 2.5 — Production Readiness

## Changes
- Migration execution now rolls back the SQLAlchemy session for **any** migration exception, not only SQLAlchemy exceptions. This prevents a failed migration from poisoning a reused serverless worker transaction.
- Fixed the admin export test fixture to use the real A-1 through M-7 apartment inventory.
- Extended `scripts/verify_production.py` to verify:
  - database connectivity and zero pending migrations
  - the deployed build marker
  - the BI authentication contract (`/api/business-intelligence` must return 401 without a token)
  - existing frontend security headers
- No schema migration was added in this release, so a healthy Phase 2.4 database remains compatible.
- BI implementation and payment verification logic were intentionally left unchanged.

## Validation
- Python syntax/compile check: pass
- JavaScript syntax check: pass
- Archive file count: below 100
