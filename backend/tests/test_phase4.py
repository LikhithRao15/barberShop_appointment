from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_tokens_and_barber():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    # Admin token
    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Student token
    student_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_student", "password": "Student@123"},
    )
    student_token = student_res.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Create a test barber for schedules
    barber_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Expert in styling",
            "specialties": "Haircuts",
            "shop_name": "Campus Barber Station 1",
            "chair_number": 2,
            "is_available_for_booking": True,
            "email": "schedule_barber@example.com",
            "username": "barber_schedule_user",
            "full_name": "Schedule Barber",
            "phone_number": "555-8888",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_data = barber_res.json()
    barber_id = barber_data["id"]

    # Login as this barber
    b_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "barber_schedule_user", "password": "Password@123"},
    )
    barber_token = b_login.json()["access_token"]
    barber_headers = {"Authorization": f"Bearer {barber_token}"}

    return {
        "admin_headers": admin_headers,
        "student_headers": student_headers,
        "barber_headers": barber_headers,
        "barber_id": barber_id,
    }


def test_create_working_schedule_with_breaks(setup_tokens_and_barber):
    data = setup_tokens_and_barber
    barber_id = data["barber_id"]
    barber_headers = data["barber_headers"]

    # 1. Barber sets recurring Wednesday (day_of_week=2) schedule from 09:00 to 17:00 with lunch break 13:00-14:00
    res = client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "day_of_week": 2,  # Wednesday
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "is_day_off": False,
            "is_active": True,
            "breaks": [
                {
                    "name": "Lunch Break",
                    "start_time": "13:00:00",
                    "end_time": "14:00:00",
                }
            ],
        },
        headers=barber_headers,
    )
    assert res.status_code == 201
    res_data = res.json()
    assert res_data["barber_id"] == barber_id
    assert res_data["day_of_week"] == 2
    assert len(res_data["breaks"]) == 1
    assert res_data["breaks"][0]["name"] == "Lunch Break"


def test_schedule_validation_break_outside_hours(setup_tokens_and_barber):
    data = setup_tokens_and_barber
    barber_id = data["barber_id"]
    barber_headers = data["barber_headers"]

    # Break is 17:30 - 18:00 while shift ends at 17:00 -> 400 Bad Request
    res = client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "day_of_week": 3,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "breaks": [
                {
                    "name": "Evening Break",
                    "start_time": "17:30:00",
                    "end_time": "18:00:00",
                }
            ],
        },
        headers=barber_headers,
    )
    assert res.status_code == 400
    assert "falls outside" in res.json()["detail"] or "must fall entirely" in res.json()["detail"]


def test_schedule_validation_invalid_start_end(setup_tokens_and_barber):
    data = setup_tokens_and_barber
    barber_id = data["barber_id"]
    barber_headers = data["barber_headers"]

    # start_time >= end_time -> 422 Unprocessable Entity
    res = client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "day_of_week": 4,
            "start_time": "18:00:00",
            "end_time": "09:00:00",
        },
        headers=barber_headers,
    )
    assert res.status_code == 422


def test_blocked_period_creation_and_query(setup_tokens_and_barber):
    data = setup_tokens_and_barber
    barber_id = data["barber_id"]
    barber_headers = data["barber_headers"]

    # Barber blocks 15:00-16:00 on 2026-09-23
    res = client.post(
        "/api/v1/schedules/blocked-periods",
        json={
            "barber_id": barber_id,
            "blocked_date": "2026-09-23",
            "start_time": "15:00:00",
            "end_time": "16:00:00",
            "reason": "Equipment Maintenance",
        },
        headers=barber_headers,
    )
    assert res.status_code == 201
    assert res.json()["reason"] == "Equipment Maintenance"


def test_effective_daily_schedule_resolution(setup_tokens_and_barber):
    data = setup_tokens_and_barber
    barber_id = data["barber_id"]

    # Wednesday 2026-09-23: weekday() == 2 (Wednesday)
    res = client.get(
        f"/api/v1/schedules/barber/{barber_id}/effective-date?target_date=2026-09-23"
    )
    assert res.status_code == 200
    shift = res.json()
    assert shift["is_working"] is True
    assert shift["start_time"] == "09:00:00"
    assert shift["end_time"] == "17:00:00"
    assert len(shift["breaks"]) == 1
    assert shift["breaks"][0]["name"] == "Lunch Break"
    assert len(shift["blocked_periods"]) == 1
    assert shift["blocked_periods"][0]["reason"] == "Equipment Maintenance"

    # Non-scheduled day (e.g. Sunday 2026-09-27)
    res_sun = client.get(
        f"/api/v1/schedules/barber/{barber_id}/effective-date?target_date=2026-09-27"
    )
    assert res_sun.status_code == 200
    assert res_sun.json()["is_working"] is False
