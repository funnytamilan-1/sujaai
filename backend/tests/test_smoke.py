import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-123456789")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.test")
os.environ.setdefault("ADMIN_PASSWORD", "test-only-password")

from fastapi.testclient import TestClient
from app.main import app

def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
