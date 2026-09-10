"""Small cross-request concurrency helpers.

PostgreSQL advisory transaction locks serialize application-level duplicate guards
that cannot be represented by a permanent UNIQUE constraint because legitimate
identical records may be created later. SQLite safely skips the PostgreSQL-specific
lock and relies on its serialized write behavior.
"""
from sqlalchemy import text

from models.db import db


def lock_fingerprint(fingerprint: str) -> None:
    key = str(fingerprint or "")[:1800]
    if db.engine.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": key},
        )
