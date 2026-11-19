import os
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production-123456789"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_PASSWORD"] = "test-only-password"
os.environ["DATABASE_URL"] = "sqlite:///./test_sujaai.db"

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def owner_headers():
    response = client.post("/api/auth/login", json={"email": "admin@example.test", "password": "test-only-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_chit_flow_and_payment_correction_audit():
    headers = owner_headers()
    assert client.get("/api/chit/groups").status_code == 200
    group = client.post("/api/chit/groups", headers=headers, json={
        "group_code": "TEST-G1", "name": "Test Group", "chit_type": "monthly",
        "default_amount": "500.00", "start_date": "2026-01-01"
    })
    assert group.status_code == 201
    member = client.post("/api/chit/members", headers=headers, json={
        "member_code": "TEST-M1", "group_id": group.json()["id"], "name": "Test Member",
        "mobile": "+919999999999", "address": "Test address", "joining_date": "2026-01-01"
    })
    assert member.status_code == 201
    payment = client.post("/api/chit/payments", headers=headers, json={
        "member_id": member.json()["id"], "amount": "500.00",
        "paid_at": "2026-01-05T10:00:00Z", "frequency": "monthly"
    })
    assert payment.status_code == 201
    payment_id = payment.json()["id"]
    corrected = client.patch(f"/api/chit/payments/{payment_id}", headers=headers, json={"amount": "450.00"})
    assert corrected.status_code == 200
    assert corrected.json()["amount"] == "450.00"
    audit = client.get("/api/audit", headers=headers)
    assert audit.status_code == 200
    assert any(row["action"] == "payment.correct" for row in audit.json())
    summary = client.get("/api/chit/reports/summary", headers=headers)
    assert summary.json()["payment_count"] == 1
    assert summary.json()["total_collection"] == "450.00"

def test_staff_cannot_access_admin_user_list():
    headers = owner_headers()
    created = client.post("/api/users", headers=headers, json={
        "email": "staff@example.test", "password": "a-long-test-password-123", "role": "staff"
    })
    assert created.status_code == 201
    login = client.post("/api/auth/login", json={
        "email": "staff@example.test", "password": "a-long-test-password-123"
    })
    assert login.status_code == 200
    staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/users", headers=staff_headers).status_code == 403

def test_staff_token_is_rejected_after_deactivation():
    headers = owner_headers()
    created = client.post("/api/users", headers=headers, json={
        "email": "inactive@example.test", "password": "another-long-test-password", "role": "staff"
    })
    account_id = created.json()["id"]
    login = client.post("/api/auth/login", json={"email": "inactive@example.test", "password": "another-long-test-password"})
    token = login.json()["access_token"]
    deactivated = client.patch(f"/api/users/{account_id}", headers=headers, json={"is_active": False})
    assert deactivated.status_code == 200
    assert client.get("/api/chit/groups", headers={"Authorization": f"Bearer {token}"}).status_code == 401