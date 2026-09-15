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
import http.cookiejar


def request(base, path, method="GET", payload=None, token=None, opener=None, idempotency_key=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if idempotency_key:
        req.add_header("Idempotency-Key", idempotency_key)
    return (opener or urllib.request).open(req, timeout=15)


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
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    def health():
        with request(base, "/api/health") as r:
            body = json.load(r)
            if body.get("status") != "ok":
                raise RuntimeError(body)
            migrations = body.get("migrations") or {}
            if migrations.get("pending", 0):
                raise RuntimeError(f"pending migrations: {migrations.get('pending')}")
            return f"build {body.get("build", "unknown")} · migrations {migrations.get("current")}/{migrations.get("latest")}"

    def bi_unauthenticated():
        # This deliberately checks the route without credentials. A healthy
        # deployment should reject it as an auth failure, not return a generic
        # 400 or a Vercel rewrite error.
        try:
            request(base, "/api/business-intelligence")
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode() or "{}")
            if exc.code != 401:
                raise RuntimeError(f"HTTP {exc.code}: {body}")
            return f"HTTP 401 · {body.get("error", {}).get("code", "AUTH_REQUIRED")}"
        raise RuntimeError("BI endpoint unexpectedly allowed an unauthenticated request")

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
    check("BI authentication contract", bi_unauthenticated, failures)
    check("frontend/security headers", frontend, failures)

    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if email and password:
        def login():
            with request(base, "/api/auth/login", "POST", {"email": email, "password": password}, opener=opener) as r:
                body = json.load(r)
                if not body.get("user"):
                    raise RuntimeError("login returned no user")
                return "admin cookie login succeeded"

        def export():
            with request(base, "/api/admin/export/residents?format=csv", opener=opener) as r:
                disposition = r.headers.get("Content-Disposition", "")
                if r.status != 200 or "attachment" not in disposition:
                    raise RuntimeError(f"HTTP {r.status}, invalid attachment response")
                return "resident CSV export succeeded"

        check("admin authentication", login, failures)
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
