# NestLedger Voice v5.2

- One microphone only: it lives inside the AK assistant footer. No floating/global microphone is created.
- Listening is sticky: the red mic glow remains active across browser/native recognition segments until the user says a stop command, types a stop command in AK, or clicks the AK mic.
- Duplicate native `start()` calls are guarded; an already-running recognizer is treated as a no-op instead of surfacing an “already on/listening” error.
- Native Android sessions use lifecycle events and `readyForNextSession` before restarting, plus `forceStop()` on manual stop.
- Browser `no-speech`/end events restart silently while voice is enabled. Permission/network failures are shown once and turn voice off.
- Voice transcripts remain deterministic/local and are not sent to the AI chat endpoint.
