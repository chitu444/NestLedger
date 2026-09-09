import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, current_app, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from models.db import db
from models.user import User
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.complaints import complaints_bp
from routes.chatbot import chatbot_bp
from routes.dashboard import dashboard_bp
from routes.invoices import invoices_bp
from routes.notices import notices_bp
from routes.notifications import notifications_bp
from routes.payments import payments_bp
from routes.reports import reports_bp
from routes.vendors import vendors_bp
from routes.work_orders import workorders_bp


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

load_dotenv(BASE_DIR / ".env")


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        db_path = BASE_DIR / "database" / "nestledger.db"
        return f"sqlite:///{db_path.as_posix()}"
    # Support legacy PostgreSQL URLs returned by some hosting providers.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

app_env = os.getenv("APP_ENV", "development").lower()
secret_key = os.getenv("SECRET_KEY", "nestledger-dev-secret")
jwt_secret_key = os.getenv("JWT_SECRET_KEY", "nestledger-dev-jwt-secret")

if app_env == "production" and (
    secret_key == "nestledger-dev-secret"
    or jwt_secret_key == "nestledger-dev-jwt-secret"
):
    raise RuntimeError("Set SECRET_KEY and JWT_SECRET_KEY before production deployment.")

if app_env == "production" and (
    not os.getenv("ADMIN_EMAIL", "").strip()
    or not os.getenv("ADMIN_PASSWORD", "")
):
    raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD before production deployment.")

app.config.update(
    SECRET_KEY=secret_key,
    JWT_SECRET_KEY=jwt_secret_key,
    SQLALCHEMY_DATABASE_URI=database_url(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=4),
    JWT_DECODE_LEEWAY=10,
    RAZORPAY_KEY_ID=os.getenv("RAZORPAY_KEY_ID", ""),
    RAZORPAY_KEY_SECRET=os.getenv("RAZORPAY_KEY_SECRET", ""),
    RAZORPAY_WEBHOOK_SECRET=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
)

# CORS is opt-in. Same-origin Vercel/Flask deployments do not need it.
cors_origins = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins:
    CORS(app, origins=[x.strip() for x in cors_origins.split(",") if x.strip()],
         supports_credentials=False, max_age=86400)
db.init_app(app)
JWTManager(app)

for blueprint in (
    auth_bp,
    dashboard_bp,
    payments_bp,
    complaints_bp,
    chatbot_bp,
    admin_bp,
    workorders_bp,
    reports_bp,
    notices_bp,
    invoices_bp,
    notifications_bp,
    vendors_bp,
):
    app.register_blueprint(blueprint, url_prefix="/api")


from utils.migrations import run_migrations

def seed_admin() -> None:
    """Create the demo/admin account only when it does not already exist."""
    email = os.getenv("ADMIN_EMAIL", "admin@nestledger.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "Admin@123")
    admin = User.query.filter_by(email=email).first()

    if admin is None:
        admin = User(
            name=os.getenv("ADMIN_NAME", "NestLedger Admin"),
            email=email,
            role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()


with app.app_context():
    (BASE_DIR / "database").mkdir(parents=True, exist_ok=True)
    db.create_all()
    run_migrations()
    seed_admin()


@app.after_request
def security_and_cache_headers(response):
    """Apply small, deployment-safe HTTP hardening and static caching."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), payment=(self), usb=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; connect-src 'self' https://api.razorpay.com https://checkout.razorpay.com https://generativelanguage.googleapis.com; "
        "frame-src https://api.razorpay.com https://checkout.razorpay.com; object-src 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif response.content_type and (response.content_type.startswith("text/css") or response.content_type.startswith("application/javascript")):
        response.headers.setdefault("Cache-Control", "public, max-age=3600, stale-while-revalidate=86400")
    return response


@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith("/api/"):
        return {"ok": False, "error": {"code": "BAD_REQUEST", "message": "The request could not be processed."}}, 400
    return error


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return {"ok": False, "error": {"code": "NOT_FOUND", "message": "The requested resource was not found."}}, 404
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(405)
def method_not_allowed(error):
    if request.path.startswith("/api/"):
        return {"ok": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "This method is not allowed for the requested resource."}}, 405
    return error


@app.errorhandler(413)
def request_too_large(error):
    return ({"ok": False, "error": {"code": "PAYLOAD_TOO_LARGE", "message": "The request body is too large."}}, 413)


@app.errorhandler(500)
def internal_server_error(error):
    # Never leak a Flask HTML error page to the SPA. Log the traceback server-side
    # and return a predictable JSON error so the frontend can show a useful message.
    current_app.logger.exception("Unhandled API/server exception")
    if request.path.startswith("/api/"):
        return {"ok": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": "The server could not complete this request. Please try again."}}, 500
    return error


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.get("/api/<path:missing>")
def api_not_found(missing: str):
    return {"error": "API endpoint not found"}, 404


@app.get("/<path:path>")
def static_files(path: str):
    # send_from_directory prevents unsafe path traversal.
    requested = FRONTEND_DIR / path
    if requested.is_file():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
