# NestLedger Voice V5.3

- Exactly one microphone control exists, inside the AK assistant input row.
- AK self-heals its microphone control for resident, vendor, and admin shells.
- Any legacy/global/outside `.voice-mic` control is removed when AK mounts.
- Mic layout is a stable input + mic + Send row; it cannot float outside AK.
- Listening state remains red/glowing until the user explicitly stops listening by the AK mic or chat command.
- Native speech lifecycle guards remain in place to prevent overlapping start calls and repeated “already listening” spam.
- Android package includes the canonical launcher icon assets under `assets/` and the setup script regenerates native icons.
- Vendor creation now supports one or multiple trade roles (Plumber, Electrician, Carpenter, Painter, Cleaner).
