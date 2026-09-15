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
