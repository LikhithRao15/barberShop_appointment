import concurrent.futures
from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_booking_data():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create Barber "Deepak Cuts"
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Senior Hair Stylist",
            "specialties": "Styling & Beard",
            "shop_name": "Campus Saloon Chair 1",
            "chair_number": 1,
            "is_available_for_booking": True,
            "email": "deepak.barber@example.com",
            "username": "deepak_barber",
            "full_name": "Deepak Barber",
            "phone_number": "555-0011",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]

    # 2. Create Service "Standard Haircut" (30 min) and "Premium Styling" (45 min)
    s30_res = client.post(
        "/api/v1/services",
        json={
            "name": "Standard Haircut 30m",
            "description": "30 min cut",
            "duration_minutes": 30,
            "price": 20.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    service_30_id = s30_res.json()["id"]

    s45_res = client.post(
        "/api/v1/services",
        json={
            "name": "Premium Styling 45m",
            "description": "45 min cut and style",
            "duration_minutes": 45,
            "price": 35.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    service_45_id = s45_res.json()["id"]

    # 3. Create Student 1 "Akash"
    stu1_res = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "STU-AKASH-101",
            "department": "Mechanical",
            "year_of_study": 2,
            "email": "akash@example.com",
            "username": "akash_user",
            "full_name": "Akash Kumar",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    stu1_id = stu1_res.json()["id"]

    # Student 1 Login
    l1 = client.post("/api/v1/auth/login", json={"username_or_email": "akash_user", "password": "Password@123"})
    stu1_headers = {"Authorization": f"Bearer {l1.json()['access_token']}"}

    # 4. Create Student 2 "Suresh"
    stu2_res = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "STU-SURESH-102",
            "department": "Civil",
            "year_of_study": 3,
            "email": "suresh@example.com",
            "username": "suresh_user",
            "full_name": "Suresh Raina",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    stu2_id = stu2_res.json()["id"]

    # Student 2 Login
    l2 = client.post("/api/v1/auth/login", json={"username_or_email": "suresh_user", "password": "Password@123"})
    stu2_headers = {"Authorization": f"Bearer {l2.json()['access_token']}"}

    # 5. Set Barber Schedule for 2026-09-24 (Thursday): 15:00 - 18:00 with Break 16:30 - 17:00
    # Day of week for 2026-09-24 is 3 (Thursday)
    client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "schedule_date": "2026-09-24",
            "start_time": "15:00:00",
            "end_time": "18:00:00",
            "is_day_off": False,
            "is_active": True,
            "breaks": [
                {
                    "name": "Tea Break",
                    "start_time": "16:30:00",
                    "end_time": "17:00:00",
                }
            ],
        },
        headers=admin_headers,
    )

    return {
        "admin_headers": admin_headers,
        "stu1_headers": stu1_headers,
        "stu2_headers": stu2_headers,
        "barber_id": barber_id,
        "service_30_id": service_30_id,
        "service_45_id": service_45_id,
        "stu1_id": stu1_id,
        "stu2_id": stu2_id,
    }


def test_availability_engine_with_breaks_and_durations(setup_booking_data):
    data = setup_booking_data
    barber_id = data["barber_id"]
    service_30_id = data["service_30_id"]
    service_45_id = data["service_45_id"]

    # 1. 30-min service availability for 2026-09-24 (Shift: 15:00-18:00, Break: 16:30-17:00)
    # Available 30m slots should include: 15:00-15:30, 15:15-15:45, 15:30-16:00, 15:45-16:15, 16:00-16:30, 17:00-17:30, 17:15-17:45, 17:30-18:00
    # And NO slot should touch 16:30-17:00!
    res_avail30 = client.get(
        f"/api/v1/appointments/availability?barber_id={barber_id}&service_id={service_30_id}&target_date=2026-09-24"
    )
    assert res_avail30.status_code == 200
    slots30 = res_avail30.json()["available_slots"]
    assert len(slots30) > 0

    # Ensure no slot overlaps with 16:30 - 17:00
    for s in slots30:
        start = s["start_time"]
        end = s["end_time"]
        assert not (start < "17:00:00" and end > "16:30:00")

    # 2. 45-min service availability
    # Notice: 16:00-16:45 would overlap with break 16:30-17:00, so 16:00 is NOT available for 45-min service!
    res_avail45 = client.get(
        f"/api/v1/appointments/availability?barber_id={barber_id}&service_id={service_45_id}&target_date=2026-09-24"
    )
    assert res_avail45.status_code == 200
    slots45 = res_avail45.json()["available_slots"]
    start_times_45 = [s["start_time"] for s in slots45]
    assert "16:00:00" not in start_times_45
    assert "15:00:00" in start_times_45
    assert "17:00:00" in start_times_45


def test_successful_booking_and_ownership(setup_booking_data):
    data = setup_booking_data
    barber_id = data["barber_id"]
    service_30_id = data["service_30_id"]
    stu1_headers = data["stu1_headers"]
    stu2_headers = data["stu2_headers"]

    # Student 1 books 15:00 - 15:30 on 2026-09-24
    book_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_30_id,
            "appointment_date": "2026-09-24",
            "start_time": "15:00:00",
            "notes": "First haircut of semester",
        },
        headers=stu1_headers,
    )
    assert book_res.status_code == 201
    appt = book_res.json()
    appt_id = appt["id"]
    assert appt["start_time"] == "15:00:00"
    assert appt["end_time"] == "15:30:00"
    assert appt["status"] == "BOOKED"

    # Student 1 views own appointment
    get_res = client.get(f"/api/v1/appointments/{appt_id}", headers=stu1_headers)
    assert get_res.status_code == 200

    # Student 2 tries to view Student 1's appointment -> 403 Forbidden
    unauth_res = client.get(f"/api/v1/appointments/{appt_id}", headers=stu2_headers)
    assert unauth_res.status_code == 403


def test_booking_validation_outside_hours_and_breaks(setup_booking_data):
    data = setup_booking_data
    barber_id = data["barber_id"]
    service_30_id = data["service_30_id"]
    stu2_headers = data["stu2_headers"]

    # 1. Booking outside working hours (e.g. 14:00 before 15:00 shift) -> 400
    res_outside = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_30_id,
            "appointment_date": "2026-09-24",
            "start_time": "14:00:00",
        },
        headers=stu2_headers,
    )
    assert res_outside.status_code == 400
    assert "working hours" in res_outside.json()["detail"]

    # 2. Booking during configured break (16:30 - 17:00) -> 400
    res_break = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_30_id,
            "appointment_date": "2026-09-24",
            "start_time": "16:30:00",
        },
        headers=stu2_headers,
    )
    assert res_break.status_code == 400
    assert "break" in res_break.json()["detail"]


def test_double_booking_prevention(setup_booking_data):
    data = setup_booking_data
    barber_id = data["barber_id"]
    service_30_id = data["service_30_id"]
    stu2_headers = data["stu2_headers"]

    # Student 1 already booked 15:00-15:30. Student 2 tries to book 15:00-15:30 -> 409 Conflict
    conflict_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_30_id,
            "appointment_date": "2026-09-24",
            "start_time": "15:00:00",
        },
        headers=stu2_headers,
    )
    assert conflict_res.status_code == 409
    assert "no longer available" in conflict_res.json()["detail"]


def test_concurrent_booking_race_condition(setup_booking_data):
    """
    Simulates two students submitting booking requests for the exact same slot concurrently.
    Guarantees that exactly one request succeeds (201) and the other fails safely (409).
    """
    data = setup_booking_data
    barber_id = data["barber_id"]
    service_30_id = data["service_30_id"]
    stu1_headers = data["stu1_headers"]
    stu2_headers = data["stu2_headers"]

    # Target slot: 17:00 - 17:30
    payload = {
        "barber_id": barber_id,
        "service_id": service_30_id,
        "appointment_date": "2026-09-24",
        "start_time": "17:00:00",
    }

    results = []

    def make_booking(headers):
        # Create separate client to simulate separate HTTP clients
        c = TestClient(app)
        return c.post("/api/v1/appointments", json=payload, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(make_booking, stu1_headers)
        f2 = executor.submit(make_booking, stu2_headers)
        res1 = f1.result()
        res2 = f2.result()
        results = [res1.status_code, res2.status_code]

    assert 201 in results, "At least one concurrent booking must succeed"
    assert 409 in results, "The duplicate concurrent booking must be rejected with 409 Conflict"
