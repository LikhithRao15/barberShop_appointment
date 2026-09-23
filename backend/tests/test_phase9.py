import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_phase9_data():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create normal student
    stu_res = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "ROLL-P9-01",
            "department": "Civil",
            "email": "p9.student@example.com",
            "username": "p9_student",
            "full_name": "Phase9 Student",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    stu_login = client.post("/api/v1/auth/login", json={"username_or_email": "p9_student", "password": "Password@123"})
    student_headers = {"Authorization": f"Bearer {stu_login.json()['access_token']}"}

    # Create a test barber
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Phase 9 Barber",
            "specialties": "Fades",
            "shop_name": "Main Shop",
            "chair_number": 6,
            "is_available_for_booking": False,
            "email": "p9.barber@example.com",
            "username": "p9_barber",
            "full_name": "Phase9 Barber",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]

    return {
        "admin_headers": admin_headers,
        "student_headers": student_headers,
        "barber_id": barber_id,
        "student_user_id": stu_res.json()["user_id"],
    }


def test_admin_dashboard_and_rules(setup_phase9_data):
    d = setup_phase9_data
    admin_headers = d["admin_headers"]
    student_headers = d["student_headers"]

    # 1. Non-admin accessing admin dashboard -> 403 Forbidden
    res_unauth = client.get("/api/v1/admin/dashboard/stats", headers=student_headers)
    assert res_unauth.status_code == 403

    # 2. Admin accessing dashboard stats -> 200 OK
    res_stats = client.get("/api/v1/admin/dashboard/stats", headers=admin_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_users"] >= 1
    assert "BOOKED" in stats["appointments_by_status"]

    # 3. System rules
    res_rules = client.get("/api/v1/admin/system/rules", headers=admin_headers)
    assert res_rules.status_code == 200
    rules = res_rules.json()
    assert rules["cancellation_cutoff_minutes"] == 60
    assert rules["no_show_grace_period_minutes"] == 10


def test_admin_user_deactivation_and_reactivation(setup_phase9_data):
    d = setup_phase9_data
    admin_headers = d["admin_headers"]
    student_user_id = d["student_user_id"]

    # 1. Deactivate student user
    res_deact = client.put(
        f"/api/v1/admin/users/{student_user_id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["is_active"] is False

    # 2. Attempt login as deactivated user -> 403 Forbidden
    login_attempt = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "p9_student", "password": "Password@123"},
    )
    assert login_attempt.status_code == 403
    assert "Inactive" in login_attempt.json()["detail"]

    # 3. Reactivate user
    res_react = client.put(
        f"/api/v1/admin/users/{student_user_id}/status",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert res_react.status_code == 200
    assert res_react.json()["is_active"] is True

    # 4. Login succeeds after reactivation
    login_success = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "p9_student", "password": "Password@123"},
    )
    assert login_success.status_code == 200


def test_batch_import_students(setup_phase9_data):
    d = setup_phase9_data
    admin_headers = d["admin_headers"]

    import_payload = {
        "students": [
            {
                "student_id_number": "BATCH-001",
                "department": "Mechanical",
                "year_of_study": 1,
                "email": "batch1@example.com",
                "username": "batch_stu_1",
                "full_name": "Batch Student One",
                "password": "Password@123",
            },
            {
                "student_id_number": "BATCH-002",
                "department": "Electrical",
                "year_of_study": 2,
                "email": "batch2@example.com",
                "username": "batch_stu_2",
                "full_name": "Batch Student Two",
                "password": "Password@123",
            },
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=import_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_requested"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0


def test_barber_approval_toggle(setup_phase9_data):
    d = setup_phase9_data
    admin_headers = d["admin_headers"]
    barber_id = d["barber_id"]

    # Approve barber
    res_approve = client.put(
        f"/api/v1/admin/barbers/{barber_id}/approve",
        json={"is_available_for_booking": True},
        headers=admin_headers,
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["is_available_for_booking"] is True
