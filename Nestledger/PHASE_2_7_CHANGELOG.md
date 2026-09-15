# NestLedger Phase 2.7

## UI / typography polish
- Removed decorative italic typography across the entire interface for clearer, more readable text.
- Added a small divider between **Admin Control Room** and its supporting heading text.
- Reworked the dark-mode apartment theatre selector to match the existing charcoal/plum/lavender dark theme.
- Dark apartment blocks, seats, selected state, occupied state, legend and selection pill now use the same dark palette and contrast rules as the rest of the application.
- Bumped frontend asset cache version to `61`.
- Bumped production build marker to `PHASE-2.7-2026-09-15-01`.

## Validation
- Python syntax compilation passed.
- JavaScript syntax check passed.
- ZIP integrity check passed.
- Full Flask runtime tests were not available in the build environment because the runtime dependencies were not installed.
