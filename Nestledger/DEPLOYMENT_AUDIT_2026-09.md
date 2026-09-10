# NestLedger deployment audit — September 2026

## Vercel / Razorpay

- Razorpay secrets remain backend-only.
- Order creation validates INR amounts and configured maximums.
- Payment verification validates HMAC signature, order ownership, amount, currency and captured state.
- Authorized payments are now captured server-side before local payment/bill state is marked paid. This handles manual-capture and late-authorisation cases.
- `payment.authorized` webhooks attempt the same server-side capture and never mark a payment paid unless Razorpay confirms `captured`.
- Webhook signatures and event-id deduplication remain enforced.
- Admin-only `GET /api/payments/health` verifies Razorpay credentials against the Orders API without creating a payment. It reports only non-secret configuration state.
- Razorpay Live keys still require the Razorpay onboarding/website verification conditions described in the official docs.

## Voice navigation

- 79 canonical voice intents remain registered with unique IDs.
- Continuous recognition is retained on supported browsers.
- The UI no longer claims `Listening…` before the browser recognition engine fires `onstart`.
- Interim speech is surfaced as `Heard: ...`; final speech is routed through the deterministic intent engine.
- `network`, microphone, permission and unsupported-browser failures now stop the false listening state and show an actionable message.
- `no-speech` remains recoverable and restarts recognition.
- The web voice implementation remains based on the browser SpeechRecognition API. Browsers that do not expose SpeechRecognition cannot provide voice navigation without a native/remote speech provider.

## Apartment inventory

- Resident inventory remains A-1 through M-7 (91 apartments).
- Public apartment availability supports both `/api/auth/apartments` and `/api/apartments` for compatibility.
- Stored resident apartment codes are normalized before uniqueness enforcement.
- PostgreSQL uniqueness and A-M inventory validation remain enforced.

## Static verification

- Python compilation: passed.
- JavaScript syntax checks: passed.
- Voice intent count: 79.
- Voice intent IDs: unique.
- No Android/Capacitor/Gradle files are included in the Vercel deployment package.
- Generated Python/pytest caches are excluded from the release package.
