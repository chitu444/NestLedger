# NestLedger Voice + Vendor Roles V5.3

## Voice
- Exactly one microphone control is rendered: inside the AK assistant footer/input row.
- AK self-heals the inline mic for resident, vendor, and admin shells.
- Legacy/global/outside `.voice-mic` controls are removed automatically.
- The mic remains red/glowing for the full listening session until the user stops it from the mic or AK chat command.
- Native/browser lifecycle guards from V5.2 remain in place to prevent overlapping starts and repeated “already listening” messages.

## Vendor roles
- Admin > Vendors now supports one or multiple trade roles per vendor.
- Roles: Plumber, Electrician, Carpenter, Painter, Cleaner.
- Existing database schema is preserved: multiple roles are stored in the existing `vendor.service` field as a comma-separated value, so no migration is required.
- Work-order matching accepts any assigned role.
