# NestLedger Voice V5.4

- AK microphone is locked into one horizontal input row: Ask AK | microphone | Send.
- No floating/global voice microphone is created.
- Web voice uses Web Speech API when supported; unsupported browsers show one clear capability message instead of pretending recognition is available.
- Android/native voice resolves the Capacitor speech plugin at runtime, checks availability, requests the correct `speechRecognition` permission, and guards against duplicate starts.
- Native lifecycle uses listeningState, segmentResults, error and readyForNextSession without repeated toast spam.
- AK spoken responses are not synthesized while recognition is actively listening, preventing the assistant from hearing its own voice as a command.
- Voice remains on until the user explicitly stops it with the AK mic or “stop listening”.
- Android launcher assets remain in the root `assets/` directory for Capacitor Assets generation.


V5.4.1 visual patch: vendor role selector now has explicit dark-theme surfaces, text, checked state, hover state, and help text so Plumber/Electrician/Carpenter/Painter/Cleaner controls no longer remain white in dark mode.
