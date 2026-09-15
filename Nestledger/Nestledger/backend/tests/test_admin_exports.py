import os
import unittest

# These tests are intended to run in an environment with backend requirements installed.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("ADMIN_EMAIL", "test-admin@nestledger.local")
os.environ.setdefault("ADMIN_PASSWORD", "TestAdmin@123")

from app import app
from models.db import db
from models.user import User
from models.payment import Payment


class AdminExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        cls.ctx = app.app_context()
        cls.ctx.push()
        db.drop_all()
        db.create_all()
        admin = User(name="Admin", email="test-admin@nestledger.local", role="admin")
        admin.set_password("TestAdmin@123")
        resident = User(name="Resident One", email="resident@example.com", role="resident", apartment="A-101", phone="9999999999")
        resident.set_password("Resident@123")
        db.session.add_all([admin, resident])
        db.session.flush()
        db.session.add(Payment(user_id=resident.id, amount=2500, description="Maintenance", status="paid", payment_type="maintenance"))
        db.session.commit()
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.ctx.pop()

    def _token(self):
        response = self.client.post("/api/auth/login", json={"email": "test-admin@nestledger.local", "password": "TestAdmin@123"})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    def test_csv_exports(self):
        token = self._token()
        for resource, header in (("residents", "Name"), ("payments", "Resident"), ("expenses", "Category")):
            response = self.client.get(f"/api/admin/export/{resource}?format=csv", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 200)
            self.assertIn(header.encode(), response.data)
            self.assertIn("attachment", response.headers.get("Content-Disposition", ""))

    def test_xlsx_payment_export(self):
        token = self._token()
        response = self.client.get("/api/admin/export/payments?format=xlsx", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_export_is_admin_only(self):
        response = self.client.get("/api/admin/export/payments?format=csv")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
