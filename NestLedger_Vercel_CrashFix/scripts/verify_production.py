#!/usr/bin/env python3
"""Production smoke verifier for a deployed NestLedger instance.

Usage:
  python scripts/verify_production.py https://your-domain.vercel.app

Optional admin smoke test:
  set ADMIN_EMAIL and ADMIN_PASSWORD in the environment before running.
"""
import json
import os
import sys
import urllib.error
import urllib.request


def request(base, path, method="GET", payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(req, timeout=15)


def check(name, fn, failures):
    try:
        result = fn()
        print(f"[OK]   {name}{(': ' + result) if result else ''}")
    except Exception as exc:
        failures.append(name)
        print(f"[FAIL] {name}: {exc}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/verify_production.py https://your-domain", file=sys.stderr)
        return 2
    base = sys.argv[1].rstrip("/")
    failures = []
    token_box = {}

    def health():
        with request(base, "/api/health") as r:
            body = json.load(r)
            if body.get("status") != "ok":
                raise RuntimeError(body)
            return f"migrations {body['migrations']['current']}/{body['migrations']['latest']}"

    def frontend():
        with request(base, "/") as r:
            if r.status != 200:
                raise RuntimeError(f"HTTP {r.status}")
            headers = {k.lower(): v for k, v in r.headers.items()}
            missing = [h for h in ("x-content-type-options", "x-frame-options", "content-security-policy") if h not in headers]
            if missing:
                raise RuntimeError("missing security headers: " + ", ".join(missing))
            return "HTTP 200 + security headers"

    check("health/database/migrations", health, failures)
    check("frontend/security headers", frontend, failures)

    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if email and password:
        def login():
            with request(base, "/api/auth/login", "POST", {"email": email, "password": password}) as r:
                body = json.load(r)
                token_box["token"] = body.get("token")
                if not token_box["token"]:
                    raise RuntimeError("login returned no token")
                return "admin login succeeded"

        def export():
            with request(base, "/api/admin/export/residents?format=csv", token=token_box["token"]) as r:
                disposition = r.headers.get("Content-Disposition", "")
                if r.status != 200 or "attachment" not in disposition:
                    raise RuntimeError(f"HTTP {r.status}, invalid attachment response")
                return "resident CSV export succeeded"

        check("admin authentication", login, failures)
        if token_box.get("token"):
            check("admin resident CSV export", export, failures)
    else:
        print("[SKIP] admin auth/export smoke test (set ADMIN_EMAIL + ADMIN_PASSWORD to enable)")

    if failures:
        print(f"\nProduction verification failed: {len(failures)} check(s).")
        return 1
    print("\nProduction verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
