#!/usr/bin/env python3
"""Explicit NestLedger production migration runner.

Usage:
  python scripts/migrate.py status
  python scripts/migrate.py migrate

Set DATABASE_URL and the normal production secrets in the environment first.
This script disables the automatic startup runner so the migration action is explicit.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "0"
os.environ["RUN_DB_CREATE_ALL_ON_STARTUP"] = "0"
os.environ["RUN_ADMIN_SEED_ON_STARTUP"] = "0"

from app import app  # noqa: E402
from models.db import db  # noqa: E402
import models  # noqa: F401,E402  # ensure every model is registered for explicit local SQLite bootstrap
from sqlalchemy import inspect  # noqa: E402
from utils.migrations import migration_status, run_migrations  # noqa: E402


def main():
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    with app.app_context():
        if command == "status":
            print(migration_status())
            return 0
        if command == "migrate":
            # A brand-new local SQLite database has no legacy/base schema. Bootstrap
            # that empty database here (explicitly), never from production app startup.
            # PostgreSQL/Neon remains migration-only and is never auto-created here.
            if db.engine.dialect.name == "sqlite":
                tables = set(inspect(db.engine).get_table_names())
                if not tables:
                    db.create_all()
                elif "user" not in tables:
                    print(
                        "Refusing to bootstrap a non-empty SQLite database that is missing the user table.",
                        file=sys.stderr,
                    )
                    return 1
            result = run_migrations()
            print(f"NestLedger migrations: {result['current']}/{result['latest']} applied")
            if result["pending"]:
                print("Pending:", result["pending"])
                return 2
            return 0
        print("Usage: python scripts/migrate.py [status|migrate]", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
