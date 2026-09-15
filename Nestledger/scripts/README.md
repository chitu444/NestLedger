# NestLedger production operations

## Explicit migration runner

From the repository root, with the production `DATABASE_URL` available:

```bash
python scripts/migrate.py status
python scripts/migrate.py migrate
python scripts/migrate.py status
```

Production Vercel startup does **not** run migrations or `db.create_all()`. This separation prevents a cold-start migration failure from preventing the serverless function from loading. The runner serializes PostgreSQL migration execution with an advisory transaction lock.

## Deployment verification

After Vercel deployment and promotion to Production:

```bash
python scripts/verify_production.py https://YOUR-DEPLOYMENT.vercel.app
```

For the optional authenticated smoke test, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the shell environment. Never put production credentials in the repository or command-line arguments.

The verifier checks database connectivity/migration state, BI authentication, frontend security headers, cookie-backed admin login, and resident CSV export.
