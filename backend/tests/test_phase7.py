from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_phase7_data():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Barber 1
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Specialist Barber",
            "specialties": "Haircuts & Styling",
            "shop_name": "Saloon Chair 4",
            "chair_number": 4,
            "is_available_for_booking": True,
            "email": "karthik.barber@example.com",
            "username": "karthik_barber",
            "full_name": "Karthik Barber",
            "phone_number": "555-4400",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]

    # Login Barber 1
    b_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "karthik_barber", "password": "Password@123"},
    )
    barber_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Create Service
    srv_res = client.post(
        "/api/v1/services",
        json={
            "name": "Phase7 Haircut",
            "description": "Standard Haircut",
            "duration_minutes": 30,
            "price": 25.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    service_id = srv_res.json()["id"]

    # Create Student
    s_res = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "ROLL-VISIT-01",
            "department": "IT",
            "email": "manoj.student@example.com",
            "username": "manoj_p7",
            "full_name": "Manoj Kumar",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    s_login = client.post("/api/v1/auth/login", json={"username_or_email": "manoj_p7", "password": "Password@123"})
    student_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    # Set Schedule for Barber
    target_date = (date.today() + timedelta(days=3)).isoformat()
    client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "schedule_date": target_date,
            "start_time": "10:00:00",
            "end_time": "14:00:00",
            "is_day_off": False,
            "is_active": True,
            "breaks": [],
        },
        headers=admin_headers,
    )

    return {
        "admin_headers": admin_headers,
        "barber_headers": barber_headers,
        "student_headers": student_headers,
        "barber_id": barber_id,
        "service_id": service_id,
        "target_date": target_date,
    }


def test_valid_visit_lifecycle_progression(setup_phase7_data):
    d = setup_phase7_data
    barber_headers = d["barber_headers"]
    student_headers = d["student_headers"]

    # 1. Book appointment at 10:00
    book_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": d["barber_id"],
            "service_id": d["service_id"],
            "appointment_date": d["target_date"],
            "start_time": "10:00:00",
            "notes": "Testing visit lifecycle",
        },
        headers=student_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]
    assert book_res.json()["status"] == "BOOKED"

    # 2. Transition 1: BOOKED -> ARRIVED
    arrive_res = client.post(
        f"/api/v1/appointments/{appt_id}/arrive",
        json={"notes": "Student arrived in waiting area"},
        headers=barber_headers,
    )
    assert arrive_res.status_code == 200
    assert arrive_res.json()["status"] == "ARRIVED"

    # Verify visit record
    v_res = client.get(f"/api/v1/visits/appointment/{appt_id}", headers=barber_headers)
    assert v_res.status_code == 200
    visit_data = v_res.json()
    assert visit_data["arrival_time"] is not None
    assert visit_data["service_start_time"] is None
    assert visit_data["completion_time"] is None

    # 3. Transition 2: ARRIVED -> IN_SERVICE
    start_res = client.post(
        f"/api/v1/appointments/{appt_id}/start",
        json={"notes": "Seated in chair #4"},
        headers=barber_headers,
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_SERVICE"

    # Verify visit start time recorded
    v_res2 = client.get(f"/api/v1/visits/appointment/{appt_id}", headers=barber_headers)
    assert v_res2.json()["service_start_time"] is not None

    # 4. Transition 3: IN_SERVICE -> COMPLETED
    complete_res = client.post(
        f"/api/v1/appointments/{appt_id}/complete",
        json={"notes": "Haircut and styling finished"},
        headers=barber_headers,
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "COMPLETED"

    # Verify visit completion time recorded and duration computed
    v_res3 = client.get(f"/api/v1/visits/appointment/{appt_id}", headers=barber_headers)
    assert v_res3.json()["completion_time"] is not None
    assert v_res3.json()["actual_duration_minutes"] >= 1


def test_invalid_status_transitions_rejected(setup_phase7_data):
    d = setup_phase7_data
    barber_headers = d["barber_headers"]
    student_headers = d["student_headers"]

    # 1. Book fresh appointment at 11:00
    book_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": d["barber_id"],
            "service_id": d["service_id"],
            "appointment_date": d["target_date"],
            "start_time": "11:00:00",
        },
        headers=student_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]

    # 2. Cannot jump directly from BOOKED to IN_SERVICE without ARRIVED -> 400
    invalid_start = client.post(
        f"/api/v1/appointments/{appt_id}/start",
        headers=barber_headers,
    )
    assert invalid_start.status_code == 400
    assert "ARRIVED" in invalid_start.json()["detail"]

    # 3. Cannot jump directly from BOOKED to COMPLETED -> 400
    invalid_complete = client.post(
        f"/api/v1/appointments/{appt_id}/complete",
        headers=barber_headers,
    )
    assert invalid_complete.status_code == 400
    assert "IN_SERVICE" in invalid_complete.json()["detail"]

    # 4. Student cannot trigger barber visit actions -> 403 Forbidden
    student_action = client.post(
        f"/api/v1/appointments/{appt_id}/arrive",
        headers=student_headers,
    )
    assert student_action.status_code == 403
