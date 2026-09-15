# NestLedger production operations

## Migration runner

From the repository root, with the production `DATABASE_URL` available:

```bash
python scripts/migrate.py status
python scripts/migrate.py migrate
python scripts/migrate.py status
```

The runner uses the same versioned migrations as the application and serializes migration execution on PostgreSQL with an advisory transaction lock.

## Deployment verification

After Vercel deployment:

```bash
python scripts/verify_production.py https://YOUR-DEPLOYMENT.vercel.app
```

For the optional authenticated smoke test, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the shell environment. Never put production credentials in the repository or command-line arguments.

The verifier checks the health/database/migration probe, frontend HTTP response, security headers, admin login, and a resident CSV export.
