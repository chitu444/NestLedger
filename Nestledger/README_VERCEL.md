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

## Production migration + verification

The release includes an explicit migration runner and a post-deployment smoke verifier.

### 1. Run migrations against production PostgreSQL

From the repository root, using the production `DATABASE_URL` and normal production environment variables:

```bash
python scripts/migrate.py status
python scripts/migrate.py migrate
python scripts/migrate.py status
```

The runner is safe to repeat. PostgreSQL migrations are serialized with a transaction-scoped advisory lock, and applied versions are recorded in `schema_migrations`.

### 2. Deploy the same commit to Vercel

Deploy only after the migration command reports the latest version as applied. The application also performs a startup migration check as a safety net.

### 3. Verify the live deployment

```bash
python scripts/verify_production.py https://YOUR-DEPLOYMENT.vercel.app
```

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the shell environment if you want the verifier to also test admin login and a real resident CSV export. Credentials are never accepted as command-line arguments.

The health probe returns `503` while migrations are pending, so an incomplete schema cannot silently present itself as ready.
