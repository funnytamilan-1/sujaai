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


def test_readiness_checks_database_connection():
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected", "schema": "ready"}

def test_oversized_request_body_is_rejected_before_endpoint_processing():
    from app.config import settings

    response = client.post(
        "/api/backup/json/restore",
        content="{}",
        headers={"Content-Length": str(settings.max_request_body_bytes + 1)},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body is too large"

def test_chit_flow_and_payment_correction_audit():
    headers = owner_headers()
    # Chit records are protected; anonymous requests must be rejected.
    assert client.get("/api/chit/groups").status_code == 401
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
    receipt = client.get(f"/api/chit/payments/{payment_id}/excel", headers=headers)
    assert receipt.status_code == 200
    assert "spreadsheetml" in receipt.headers["content-type"]
    receipt_pdf = client.get(f"/api/chit/payments/{payment_id}/pdf", headers=headers)
    assert receipt_pdf.status_code == 200
    assert receipt_pdf.headers["content-type"] == "application/pdf"
    statement = client.get(f"/api/chit/members/{member.json()['id']}/statement/excel", headers=headers)
    assert statement.status_code == 200
    assert "spreadsheetml" in statement.headers["content-type"]
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
def test_json_backup_restore_only_into_empty_chit_database():
    headers = owner_headers()
    group = client.post("/api/chit/groups", headers=headers, json={
        "group_code": "BACKUP-G1", "name": "Backup Group", "chit_type": "weekly",
        "default_amount": "250.00", "start_date": "2026-02-01"
    })
    member = client.post("/api/chit/members", headers=headers, json={
        "member_code": "BACKUP-M1", "group_id": group.json()["id"], "name": "Backup Member",
        "mobile": "+918888888888", "address": "Backup address", "joining_date": "2026-02-01"
    })
    payment = client.post("/api/chit/payments", headers=headers, json={
        "member_id": member.json()["id"], "amount": "250.00",
        "paid_at": "2026-02-08T10:00:00Z", "frequency": "weekly", "notes": "Test backup"
    })
    assert payment.status_code == 201
    backup = client.get("/api/backup/json", headers=headers)
    assert backup.status_code == 200
    payload = backup.json()
    assert len(payload["groups"]) == 1
    assert len(payload["members"]) == 1
    assert len(payload["payments"]) == 1
    # Empty only the isolated test database before validating restore.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    restored = client.post("/api/backup/json/restore", headers=headers, json=payload)
    assert restored.status_code == 200
    assert restored.json()["restored"] is True
    assert client.get("/api/chit/payments", headers=headers).json()[0]["notes"] == "Test backup"

def test_period_report_and_excel_backup():
    headers = owner_headers()
    group = client.post("/api/chit/groups", headers=headers, json={
        "group_code": "REPORT-G1", "name": "Report Group", "chit_type": "daily",
        "default_amount": "100.00", "start_date": "2026-03-01"
    })
    member = client.post("/api/chit/members", headers=headers, json={
        "member_code": "REPORT-M1", "group_id": group.json()["id"], "name": "Report Member",
        "mobile": "+917777777777", "address": "Report address", "joining_date": "2026-03-01"
    })
    client.post("/api/chit/payments", headers=headers, json={
        "member_id": member.json()["id"], "amount": "100.00",
        "paid_at": "2026-03-02T08:00:00Z", "frequency": "daily"
    })
    periods = client.get("/api/chit/reports/periods?period=daily", headers=headers)
    assert periods.status_code == 200
    assert periods.json()[0]["total"] == "100.00"
    workbook = client.get("/api/backup/excel", headers=headers)
    assert workbook.status_code == 200
    assert "spreadsheetml" in workbook.headers["content-type"]
    bad_range = client.get("/api/chit/reports/summary?start=2026-03-03&end=2026-03-01", headers=headers)
    assert bad_range.status_code == 422

def test_saved_designs_persist_and_are_private_to_account():
    owner = owner_headers()
    saved = client.post("/api/designs", headers=owner, json={
        "design_type": "resume", "title": "My resume",
        "data": {"name": "Example Person", "skills": ["Python", "HTML"]}
    })
    assert saved.status_code == 201
    design_id = saved.json()["id"]
    assert client.get("/api/designs?design_type=resume", headers=owner).json()[0]["title"] == "My resume"
    updated = client.put(f"/api/designs/{design_id}", headers=owner, json={
        "title": "Updated resume", "data": {"name": "Example Person", "skills": ["Python"]}
    })
    assert updated.status_code == 200
    assert updated.json()["data"]["skills"] == ["Python"]

    created = client.post("/api/users", headers=owner, json={
        "email": "designer@example.test", "password": "long-enough-test-password", "role": "staff"
    })
    assert created.status_code == 201
    login = client.post("/api/auth/login", json={
        "email": "designer@example.test", "password": "long-enough-test-password"
    })
    staff = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/designs/{design_id}", headers=staff).status_code == 404
    assert client.put(f"/api/designs/{design_id}", headers=staff, json={"title": "Hijack"}).status_code == 404
    assert client.delete(f"/api/designs/{design_id}", headers=owner).status_code == 204
    assert client.get("/api/designs?design_type=resume", headers=owner).json() == []


def test_frontend_cors_preflight_and_error_responses_are_allowed():
    origin = "https://sujaa.vercel.app"
    response = client.options(
        "/api/chit/groups",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "content-type" in response.headers["access-control-allow-headers"].lower()

    # CORS headers must also be present on API errors, not only successful responses.
    unauthorized = client.get("/api/chit/groups", headers={"Origin": origin})
    assert unauthorized.status_code == 401
    assert unauthorized.headers["access-control-allow-origin"] == origin

    missing = client.get("/api/does-not-exist", headers={"Origin": origin})
    assert missing.status_code == 404
    assert missing.headers["access-control-allow-origin"] == origin

def test_sujaai_production_frontend_origin_is_allowed():
    origin = "https://sujaai.vercel.app"
    response = client.options(
        "/api/chit/groups",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

