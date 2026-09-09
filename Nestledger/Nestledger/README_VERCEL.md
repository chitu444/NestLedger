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
