# NestLedger Full-Stack

Flask + SQLite/PostgreSQL + JWT + Razorpay apartment management application.

## Features

- Resident and vendor registration; admin account is seeded from environment variables.
- Role-based JWT authentication.
- Resident maintenance bills, payment history and receipts.
- Razorpay Standard Checkout with server-side signature verification.
- Vendor job board and work-order workflow.
- Admin residents, vendors, expenses, notices and dashboard metrics.
- Responsive frontend served by Flask.
- Health endpoint for deployment checks.

## Local run

1. Open a terminal in `NestLedger/backend`.
2. Create/activate a virtual environment.
3. Install dependencies:
   `python -m pip install -r requirements.txt`
4. Copy `.env.example` to `.env`.
5. Set strong `SECRET_KEY` and `JWT_SECRET_KEY` values for anything beyond local testing.
6. Add Razorpay **test** keys only when you want to test payments.
7. Run:
   `python app.py`
8. Open `http://127.0.0.1:5000`.

## Production / Render

Use PostgreSQL by setting `DATABASE_URL` to the PostgreSQL connection string.

Recommended start command from the `backend` directory:

`gunicorn app:app`

If your Render service root is the repository root, use:

`cd backend && gunicorn app:app`

The included `psycopg` dependency allows SQLAlchemy to connect to PostgreSQL.

## Default admin

For local demo use:

- Email: `admin@nestledger.com`
- Password: `Admin@123`

For deployment, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the environment and use a strong password.

## Razorpay

The backend refuses to create an order until `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are configured. Use Razorpay Test Mode first. Never expose the secret key in frontend code.

For reliable payment reconciliation, set a separate `RAZORPAY_WEBHOOK_SECRET` and configure a public HTTPS webhook at `/api/payments/webhook`. Subscribe to `payment.captured`, `payment.failed`, and `order.paid`. The application verifies the Razorpay webhook signature against the raw request body and de-duplicates events by Razorpay event ID.

## New features (this upgrade)

- **Centralized validation** (`backend/utils/validators.py`): email, Indian phone, password, required text, date, amount, status — reused across `auth`, `complaints`, `work_orders`, `admin`, `notices` instead of duplicated regexes.
- **Signup cleanup**: vendors can never have an `apartment` stored (enforced server-side even if sent directly via API); admin is not publicly selectable.
- **Live financial dashboard**: `GET /api/dashboard` (admin role) now returns a `financials` block — total billed, collected, pending, expenses, balance, collection rate (zero-bill safe).
- **Vendor work-order lifecycle**: job board split into Open / Waiting to Start / In Progress / Completed / Cancelled-Withdrawn. New `PATCH /api/work-orders/<id>/withdraw` lets a vendor withdraw from an accepted/in-progress job; it returns to the open board.
- **Vendor performance analytics**: `GET /api/admin/vendor-performance` — a documented, non-AI score (50% completion rate, 30% on-time completion, 20% cancellation rate) plus completed/cancelled/active job counts and average completion time.
- **Real-time complaint tracking**: `Complaint.updated_at` (added via a safe additive migration, no data loss) + a resident-facing status timeline (Open → In Progress → Resolved → Closed).
- **Live notifications**: new `Notification` model and `backend/routes/notifications.py` (`GET /api/notifications`, `PATCH /api/notifications/<id>/read`, `PATCH /api/notifications/read-all`). Notifications are created exactly once, at the moment of the real event (payment verified, work-order accepted/withdrawn/completed, complaint status change, new notice, new job posted) — never on every poll.
- **Six-language UI** (`frontend/js/i18n.js`): English, Tamil, Malayalam, Kannada, Telugu, Hindi. Centralized `translations` dictionary + `t(key)` helper, language selector in the sidebar, persisted via `localStorage` and restored on reload. English is the fallback for any missing key. Core chrome (nav, dashboard, auth, job board, notifications, financial overview) is translated; some deeper/legacy strings in `app.js` remain English-only and are good candidates for a follow-up pass.
- **Voice navigation** (`frontend/js/voice.js`): browser-native `SpeechRecognition`/`SpeechSynthesis` only, no paid API. Large, always-visible mic button. Commands (go to dashboard/payments/complaints/notices/maintenance, log out, read my dues, help) are recognized in all six languages via a `commands` phrase map, not if/else chains. Shows a friendly message if the browser doesn't support speech.
- **Frontend field-level validation**: `fieldError()`/`clearFieldErrors()` helpers; registration now shows inline errors under each field instead of only a toast.
- **Bug fix**: the frontend was calling `/payments/payments/...` (a doubled path segment) for both bill and vendor payments, which didn't match any real backend route — this silently broke the "pay vendor" flow. Fixed to call the actual `/payments/create-order`, `/payments/work-order/create-order`, and `/payments/verify` routes.

### Supported languages
English, Tamil, Malayalam, Kannada, Telugu, Hindi (language codes: `en`, `ta`, `ml`, `kn`, `te`, `hi`).

### Voice browser compatibility
Voice navigation requires a browser with `SpeechRecognition`/`webkitSpeechRecognition` (Chrome, Edge; not supported in Firefox or most non-Chromium mobile browsers). Unsupported browsers see a toast message and the rest of the app is unaffected.

### Database migration
`backend/app.py` runs `run_safe_migrations()` on every boot: it adds `Complaint.updated_at` via an additive `ALTER TABLE` if the column doesn't already exist yet, and backfills it from `created_at`. No table is ever dropped or recreated. A pre-upgrade backup was taken at `backend/database/nestledger_backup_before_upgrade.db` before any schema change was made.

### New API endpoints
- `GET /api/notifications`, `PATCH /api/notifications/<id>/read`, `PATCH /api/notifications/read-all`
- `PATCH /api/work-orders/<id>/withdraw`
- `GET /api/admin/vendor-performance`

### Remaining limitations
- Translation coverage focuses on the main navigation, dashboard, auth, job board, and notification UI; some deeper legacy strings in `app.js` (a few modal labels, table headers) are still English-only.
- Voice command matching is phrase-based (substring match); it does not do full natural-language understanding, and works best with the example phrasings documented in `frontend/js/voice.js`.
- Vendor performance's "on-time completion" relies on parsing the free-text `due_date` field (e.g. "10 Sep 2026"); due dates in unrecognized formats are excluded from the on-time calculation rather than guessed.
- Admins can assign maintenance bills from the Payments screen with resident, billing month, amount, due date and description. Duplicate bills for the same resident/month are rejected.
- Work-request vendor payments create Razorpay Orders tied to the exact work order and vendor, verify the payment server-side, and reconcile asynchronously through Razorpay webhooks.
- The "Cancelled / Withdrawn" job-board column only shows resident-cancelled orders; vendor withdrawals return a job to "Open" per the documented business rule rather than marking it cancelled.

### Exact command to run the project
```
cd Nestledger/backend
pip install -r requirements.txt
python app.py
```
Then open `Nestledger/frontend/index.html` (serve the `frontend` folder as static files, e.g. `python -m http.server` from within it, with the backend running on the port your frontend expects).
