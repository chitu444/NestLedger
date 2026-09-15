#!/usr/bin/env python3
"""Dependency-free static release checks for NestLedger Phase 3."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
checks = []

def check(name, ok, detail=''):
    checks.append((name, bool(ok), detail))

app = (ROOT/'backend/app.py').read_text()
mig = (ROOT/'backend/utils/migrations.py').read_text()
api = (ROOT/'frontend/js/core/api.js').read_text()
state = (ROOT/'frontend/js/core/state.js').read_text()
index = (ROOT/'frontend/index.html').read_text()

check('Phase 3 build marker', 'PHASE-3-2026-09-15-01' in app)
check('Production startup does not create schema', 'if not is_production and os.getenv("RUN_DB_CREATE_ALL_ON_STARTUP"' in app)
check('Production startup does not migrate schema', 'if not is_production and os.getenv("RUN_MIGRATIONS_ON_STARTUP"' in app)
check('Migration latest is 11', '(11, "add_auth_rate_limit"' in mig)
check('Migration status is read-only', 'def migration_status()' in mig and '_ensure_table()' not in mig[mig.index('def migration_status():'):mig.index('def _migration_lock():')])
check('Idempotency support exists', (ROOT/'backend/utils/idempotency.py').exists() and 'Idempotency-Key' in api)
check('Apartment inventory support exists', (ROOT/'backend/models/apartment_slot.py').exists() and 'claim_apartment' in (ROOT/'backend/utils/apartments.py').read_text())
check('Cookie auth enabled', 'JWT_TOKEN_LOCATION=["cookies", "headers"]' in app and 'JWT_COOKIE_HTTPONLY=True' in app)
check('No JWT/profile localStorage', 'nestledgerToken' not in state and 'nestledgerUser' not in state)
check('Strict script CSP', "script-src 'self' 'unsafe-inline'" not in app)
check('Strict style CSP', "style-src 'self' 'unsafe-inline'" not in app)
check('No inline event/style attributes', 'onclick="' not in ''.join(p.read_text(errors='ignore') for p in (ROOT/'frontend').rglob('*') if p.is_file()) and 'style="' not in ''.join(p.read_text(errors='ignore') for p in (ROOT/'frontend').rglob('*') if p.is_file()))
check('Frontend modularized', all((ROOT/'frontend/js'/x).exists() for x in ('app-core.js','app-pages.js','app-bi.js')) and 'app.js?v=' not in index)
check('Download helper has no undefined isGet reference', 'if (isGet && options.pageSeq' not in api)

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('[OK]   ' if ok else '[FAIL] ')+name+(f' — {detail}' if detail else ''))
print(f'\nPhase 3 static checks: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
