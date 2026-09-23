from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_phase6_data():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create Barber "Ramesh"
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Expert Barber",
            "specialties": "Haircuts",
            "shop_name": "Main Saloon",
            "chair_number": 3,
            "is_available_for_booking": True,
            "email": "ramesh.barber@example.com",
            "username": "ramesh_barber",
            "full_name": "Ramesh Barber",
            "phone_number": "555-3300",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]

    # Login as Barber Ramesh
    b_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ramesh_barber", "password": "Password@123"},
    )
    barber_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # 2. Create 30-min Service
    srv_res = client.post(
        "/api/v1/services",
        json={
            "name": "Phase6 Haircut 30m",
            "description": "Standard Haircut",
            "duration_minutes": 30,
            "price": 20.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    service_id = srv_res.json()["id"]

    # 3. Create 3 Students: Rahul, Akash, Suresh
    def create_stu(name, uname, email, roll):
        r = client.post(
            "/api/v1/students",
            json={
                "student_id_number": roll,
                "department": "CSE",
                "email": email,
                "username": uname,
                "full_name": name,
                "password": "Password@123",
            },
            headers=admin_headers,
        )
        l = client.post("/api/v1/auth/login", json={"username_or_email": uname, "password": "Password@123"})
        return r.json()["id"], {"Authorization": f"Bearer {l.json()['access_token']}"}

    rahul_id, rahul_headers = create_stu("Rahul", "rahul_p6", "rahul_p6@example.com", "ROLL-001")
    akash_id, akash_headers = create_stu("Akash", "akash_p6", "akash_p6@example.com", "ROLL-002")
    suresh_id, suresh_headers = create_stu("Suresh", "suresh_p6", "suresh_p6@example.com", "ROLL-003")

    # 4. Configure Schedule for tomorrow (to test advance cancellation safely)
    target_date = (date.today() + timedelta(days=2)).isoformat()
    client.post(
        "/api/v1/schedules",
        json={
            "barber_id": barber_id,
            "schedule_date": target_date,
            "start_time": "15:00:00",
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
        "barber_id": barber_id,
        "service_id": service_id,
        "target_date": target_date,
        "rahul": {"id": rahul_id, "headers": rahul_headers},
        "akash": {"id": akash_id, "headers": akash_headers},
        "suresh": {"id": suresh_id, "headers": suresh_headers},
    }


def test_fixed_appointment_principle_on_no_show_and_available_now(setup_phase6_data):
    """
    Spec Scenario:
      15:30 Rahul
      16:00 Akash
      16:30 Suresh

      Rahul becomes NO_SHOW:
      15:30 becomes AVAILABLE NOW
      Akash (16:00) and Suresh (16:30) MUST remain at their original times.
    """
    d = setup_phase6_data
    barber_id = d["barber_id"]
    service_id = d["service_id"]
    target_date = d["target_date"]
    barber_headers = d["barber_headers"]

    # 1. Book Rahul at 15:30
    res_rahul = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_id,
            "appointment_date": target_date,
            "start_time": "15:30:00",
        },
        headers=d["rahul"]["headers"],
    )
    assert res_rahul.status_code == 201
    rahul_appt_id = res_rahul.json()["id"]

    # 2. Book Akash at 16:00
    res_akash = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_id,
            "appointment_date": target_date,
            "start_time": "16:00:00",
        },
        headers=d["akash"]["headers"],
    )
    assert res_akash.status_code == 201
    akash_appt_id = res_akash.json()["id"]

    # 3. Book Suresh at 16:30
    res_suresh = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_id,
            "appointment_date": target_date,
            "start_time": "16:30:00",
        },
        headers=d["suresh"]["headers"],
    )
    assert res_suresh.status_code == 201
    suresh_appt_id = res_suresh.json()["id"]

    # 4. Barber marks Rahul as NO_SHOW (with ignore_grace_period=true for future date testing)
    res_noshow = client.post(
        f"/api/v1/appointments/{rahul_appt_id}/no-show?ignore_grace_period=true",
        json={"notes": "Student did not show up"},
        headers=barber_headers,
    )
    assert res_noshow.status_code == 200
    assert res_noshow.json()["status"] == "NO_SHOW"
    assert res_noshow.json()["is_available_now_slot"] is True

    # 5. VERIFY FIXED APPOINTMENT PRINCIPLE: Akash and Suresh MUST NOT shift!
    check_akash = client.get(f"/api/v1/appointments/{akash_appt_id}", headers=d["akash"]["headers"])
    assert check_akash.json()["start_time"] == "16:00:00"
    assert check_akash.json()["end_time"] == "16:30:00"
    assert check_akash.json()["status"] == "BOOKED"

    check_suresh = client.get(f"/api/v1/appointments/{suresh_appt_id}", headers=d["suresh"]["headers"])
    assert check_suresh.json()["start_time"] == "16:30:00"
    assert check_suresh.json()["end_time"] == "17:00:00"
    assert check_suresh.json()["status"] == "BOOKED"

    # 6. Check Available Now list shows the 15:30 released slot
    res_avail_now = client.get(
        f"/api/v1/appointments/available-now?target_date={target_date}&barber_id={barber_id}"
    )
    assert res_avail_now.status_code == 200
    avail_now_slots = res_avail_now.json()
    assert len(avail_now_slots) == 1
    assert avail_now_slots[0]["start_time"] == "15:30:00"
    assert avail_now_slots[0]["released_appointment_id"] == rahul_appt_id

    # 7. Another student books the Available Now slot (15:30)
    # Create fourth student "Vikrant"
    res_vik = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "ROLL-004",
            "department": "ECE",
            "email": "vikrant@example.com",
            "username": "vikrant_p6",
            "full_name": "Vikrant",
            "password": "Password@123",
        },
        headers=d["admin_headers"],
    )
    vik_l = client.post("/api/v1/auth/login", json={"username_or_email": "vikrant_p6", "password": "Password@123"})
    vik_headers = {"Authorization": f"Bearer {vik_l.json()['access_token']}"}

    claim_res = client.post(
        f"/api/v1/appointments/available-now/{rahul_appt_id}/claim",
        json={"service_id": service_id, "notes": "Claimed released slot"},
        headers=vik_headers,
    )
    assert claim_res.status_code == 201
    assert claim_res.json()["start_time"] == "15:30:00"
    assert claim_res.json()["student"]["id"] == res_vik.json()["id"]

    # 8. VERIFY AGAIN: Akash at 16:00 and Suresh at 16:30 remain completely untouched!
    check_akash2 = client.get(f"/api/v1/appointments/{akash_appt_id}", headers=d["akash"]["headers"])
    assert check_akash2.json()["start_time"] == "16:00:00"

    check_suresh2 = client.get(f"/api/v1/appointments/{suresh_appt_id}", headers=d["suresh"]["headers"])
    assert check_suresh2.json()["start_time"] == "16:30:00"


def test_cancellation_flow(setup_phase6_data):
    d = setup_phase6_data
    barber_id = d["barber_id"]
    service_id = d["service_id"]
    target_date = d["target_date"]
    akash_headers = d["akash"]["headers"]

    # Book a new appointment for Akash at 17:00
    book_res = client.post(
        "/api/v1/appointments",
        json={
            "barber_id": barber_id,
            "service_id": service_id,
            "appointment_date": target_date,
            "start_time": "17:00:00",
        },
        headers=akash_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]

    # Akash cancels his appointment in advance (more than 60 mins before)
    cancel_res = client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"reason": "Lab class rescheduled"},
        headers=akash_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["cancellation_reason"] == "Lab class rescheduled"
    assert cancel_res.json()["is_available_now_slot"] is True
