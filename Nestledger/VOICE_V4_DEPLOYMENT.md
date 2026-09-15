# NestLedger Voice V4 — Vercel deployment

This package is the web/Vercel version of NestLedger Voice V4.

- Voice is OFF by default.
- Type `Start listening` in AK to activate voice.
- On supported browsers, the microphone can then receive commands.
- Voice commands are handled by the deterministic NestLedger voice registry; they are not sent to an AI endpoint.
- Android native speech recognition is packaged separately in the Android-ready ZIP.

Deploy this folder as the Vercel project root. The existing `vercel.json` routes requests to `api/index.py`.
