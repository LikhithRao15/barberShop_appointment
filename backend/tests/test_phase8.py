from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_phase8_data():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create Barber "Sameer"
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Stylist Sameer",
            "specialties": "Haircuts",
            "shop_name": "Saloon Chair 5",
            "chair_number": 5,
            "is_available_for_booking": True,
            "email": "sameer.barber@example.com",
            "username": "sameer_p8",
            "full_name": "Sameer Barber",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]
    b_login = client.post("/api/v1/auth/login", json={"username_or_email": "sameer_p8", "password": "Password@123"})
    barber_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # 2. Create Service
    srv_res = client.post(
        "/api/v1/services",
        json={
            "name": "Phase8 Haircut",
            "description": "Standard cut",
            "duration_minutes": 30,
            "price": 20.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    service_id = srv_res.json()["id"]

    # 3. Create Student "Rohan"
    s_res = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "ROLL-NOTIF-01",
            "department": "Mechanical",
            "email": "rohan.student@example.com",
            "username": "rohan_p8",
            "full_name": "Rohan Verma",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    s_login = client.post("/api/v1/auth/login", json={"username_or_email": "rohan_p8", "password": "Password@123"})
    student_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    # 4. Schedule for tomorrow
    target_date = (date.today() + timedelta(days=4)).isoformat()
    client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "schedule_date": target_date,
            "start_time": "14:00:00",
            "end_time": "18:00:00",
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


def test_notification_triggers_on_appointment_events(setup_phase8_data):
    d = setup_phase8_data
    student_headers = d["student_headers"]
    barber_headers = d["barber_headers"]

    # 1. Book appointment -> triggers BOOKING_CONFIRMATION to both Student and Barber
    book_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": d["barber_id"],
            "service_id": d["service_id"],
            "appointment_date": d["target_date"],
            "start_time": "14:00:00",
        },
        headers=student_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]

    # Check student notifications
    stu_notifs = client.get("/api/v1/notifications", headers=student_headers).json()
    assert len(stu_notifs) >= 1
    assert any(n["notification_type"] == "BOOKING_CONFIRMATION" for n in stu_notifs)

    # Check barber notifications
    barb_notifs = client.get("/api/v1/notifications", headers=barber_headers).json()
    assert len(barb_notifs) >= 1
    assert any(n["notification_type"] == "BOOKING_CONFIRMATION" for n in barb_notifs)

    # 2. Check unread count
    unread_res = client.get("/api/v1/notifications/unread-count", headers=student_headers)
    assert unread_res.status_code == 200
    assert unread_res.json()["unread_count"] >= 1

    # 3. Mark single notification as read
    notif_id = stu_notifs[0]["id"]
    read_res = client.put(f"/api/v1/notifications/{notif_id}/read", headers=student_headers)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

    # 4. Mark all as read
    all_read = client.put("/api/v1/notifications/read-all", headers=student_headers)
    assert all_read.status_code == 200

    unread_after = client.get("/api/v1/notifications/unread-count", headers=student_headers)
    assert unread_after.json()["unread_count"] == 0

    # 5. Cancel appointment -> triggers CANCELLATION notification
    cancel_res = client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"reason": "Change of plans"},
        headers=student_headers,
    )
    assert cancel_res.status_code == 200

    stu_notifs_after = client.get("/api/v1/notifications", headers=student_headers).json()
    assert any(n["notification_type"] == "CANCELLATION" for n in stu_notifs_after)
