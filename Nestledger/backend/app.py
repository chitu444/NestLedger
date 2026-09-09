import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, send_from_directory
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

app.config.update(
    SECRET_KEY=secret_key,
    JWT_SECRET_KEY=jwt_secret_key,
    SQLALCHEMY_DATABASE_URI=database_url(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    RAZORPAY_KEY_ID=os.getenv("RAZORPAY_KEY_ID", ""),
    RAZORPAY_KEY_SECRET=os.getenv("RAZORPAY_KEY_SECRET", ""),
    RAZORPAY_WEBHOOK_SECRET=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
)

# Optional CORS for a separately hosted frontend.
cors_origins = os.getenv("CORS_ORIGINS", "*")
CORS(app, origins=[x.strip() for x in cors_origins.split(",")] if cors_origins != "*" else "*")
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


def run_safe_migrations() -> None:
    """Apply additive schema upgrades for existing databases.

    ``create_all`` creates missing tables but does not add new columns to an
    existing table. Keep migrations additive so an existing deployment can be
    upgraded without deleting its data.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    if "complaint" in existing_tables:
        complaint_columns = {c["name"] for c in inspector.get_columns("complaint")}
        if "updated_at" not in complaint_columns:
            db.session.execute(text("ALTER TABLE complaint ADD COLUMN updated_at TIMESTAMP"))
            db.session.execute(text("UPDATE complaint SET updated_at = created_at"))

    # Older NestLedger databases have a vendor table without user_id.  The
    # column is required to link admin-created vendors to their login account.
    if "vendor" in existing_tables:
        vendor_columns = {c["name"] for c in inspector.get_columns("vendor")}
        if "user_id" not in vendor_columns:
            db.session.execute(text("ALTER TABLE vendor ADD COLUMN user_id INTEGER"))
            db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vendor_user_id ON vendor (user_id)"))

    if "maintenance_bill" in existing_tables:
        bill_columns = {c["name"] for c in inspector.get_columns("maintenance_bill")}
        if "assigned_by_id" not in bill_columns:
            db.session.execute(text("ALTER TABLE maintenance_bill ADD COLUMN assigned_by_id INTEGER"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_maintenance_bill_assigned_by_id ON maintenance_bill (assigned_by_id)"))

    db.session.commit()


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
    run_safe_migrations()
    seed_admin()


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


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
