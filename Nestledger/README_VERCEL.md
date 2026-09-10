# NestLedger — Vercel deployment

## Vercel
1. Import this repository into Vercel.
2. Vercel should detect `api/index.py` as the Python function.
3. Add the production environment variables listed below.
4. Deploy.

## Required environment variables
- `APP_ENV=production`
- `DATABASE_URL=<PostgreSQL connection string>`
- `SECRET_KEY=<long random value>`
- `JWT_SECRET_KEY=<different long random value>`
- `ADMIN_EMAIL=<admin email>`
- `ADMIN_PASSWORD=<admin password>`
- `ADMIN_NAME=NestLedger Admin`
- `RAZORPAY_KEY_ID=<optional until payments are enabled>`
- `RAZORPAY_KEY_SECRET=<optional until payments are enabled>`
- `RAZORPAY_WEBHOOK_SECRET=<optional until webhooks are enabled>`

The Flask application is exported as `app` from `api/index.py`. The frontend is served by Flask and API routes remain under `/api/...`.

Use PostgreSQL in production. Do not rely on the local SQLite database on Vercel.

## Razorpay production checks

For a new Razorpay merchant account, generate the correct **Live** or **Test** keys from the Razorpay Dashboard and keep the secret only in Vercel environment variables. Live API keys require the website/app details to be verified by Razorpay; Test keys can be generated without website verification. After deployment, an admin can call `GET /api/payments/health` while signed in to verify that Vercel can authenticate to Razorpay's Orders API without creating a payment.

NestLedger also handles an `authorized` Razorpay payment by attempting a server-side capture before marking the local bill/payment as paid. This prevents a manual-capture or late-authorisation state from looking like a successful payment in the UI. Razorpay still recommends configuring automatic capture for normal Orders API integrations.

## Voice navigation

Voice navigation uses the browser SpeechRecognition API. The UI now reports the actual recognition lifecycle instead of showing `Listening…` before the browser has started recognition. Network, microphone, permission, no-speech, and unsupported-browser states are surfaced explicitly. Chrome/Edge are recommended for the web voice feature; browsers without SpeechRecognition should not display a false listening state.
