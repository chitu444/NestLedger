# NestLedger Phase 2

Build: `PHASE-2-2026-09-15-01`

## Reliability & performance hardening
- Explicit User↔Vendor one-to-one ORM relationship using `back_populates`; vendor session serialization no longer performs a per-vendor lookup.
- Reduced automatic frontend prefetching to the highest-probability next screens, avoiding a burst of 8–9 API calls after every shell render.
- Frontend API errors retain the server `X-Request-ID` and show a short reference ID in user-facing error messages when one is available.
- Static asset query versions were bumped to `v60` to force the Phase 2 frontend into browsers/Vercel caches.
- `/health` build marker changed to `PHASE-2-2026-09-15-01`.

## Intentionally unchanged
- No Neon/live database data was modified.
- No financial schema/amount-type migration was introduced.
- Razorpay flow was not altered.
- Apartment A–M × 7 rules were not changed.
- BI logic was not changed now that the deployed BI endpoint is confirmed working.


## Phase 2.1 — reliability and query efficiency

- Added PostgreSQL advisory locks around admin resident/vendor account creation to close preflight race windows.
- Kept work-order quote operations serialized by the parent work-order row lock and eager-loaded rating residents during work-order serialization to avoid per-rating lazy queries.
- Limited resident dashboard billing history to the 20 most recent bills; the dedicated Payments page remains the full history view.
- Collapsed admin dashboard role and work-order counts into grouped aggregate queries instead of separate count queries.
- Build marker updated to `PHASE-2.1-2026-09-15-01`.
