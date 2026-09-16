# NestLedger Voice V5.6

- Final AK layout contract: input -> microphone -> Send, with the microphone inside the AK footer row for resident, vendor and admin.
- Added an AK theme observer and explicit dark/light classes so theme changes apply to the entire assistant, not only the surrounding page.
- Removed any stale external voice buttons during every AK mount.
- Added native Android segmented-session lifecycle handling and safer permanent-error handling to avoid restart/toast loops.
- Preserved deterministic local voice commands; transcripts are not sent to the AI chat endpoint.
- Asset/cache version bumped to v=409.
