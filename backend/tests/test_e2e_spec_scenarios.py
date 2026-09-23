from datetime import date, timedelta
import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def spec_environment():
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    # 1. Admin Login
    admin_login = client.post("/api/v1/auth/login", json={"username_or_email": "admin", "password": "Admin@123456"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Onboard Barber (e.g. Rahul Barber)
    b_res = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Expert Stylist",
            "specialties": "Haircut, Fade, Beard",
            "shop_name": "Campus Saloon 1",
            "chair_number": 1,
            "is_available_for_booking": True,
            "email": "barber.spec@example.com",
            "username": "barber_spec",
            "full_name": "Barber Master",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    barber_id = b_res.json()["id"]
    b_login = client.post("/api/v1/auth/login", json={"username_or_email": "barber_spec", "password": "Password@123"})
    barber_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # 3. Create Services: Haircut (30m) and Haircut+Shave (45m)
    s30 = client.post(
        "/api/v1/services",
        json={"name": "Haircut 30m", "duration_minutes": 30, "price": 15.00, "is_active": True},
        headers=admin_headers,
    ).json()

    s45 = client.post(
        "/api/v1/services",
        json={"name": "Haircut & Beard 45m", "duration_minutes": 45, "price": 25.00, "is_active": True},
        headers=admin_headers,
    ).json()

    # 4. Onboard 3 Students: Rahul, Akash, Suresh
    def make_student(name, uname, email, roll):
        r = client.post(
            "/api/v1/students",
            json={
                "student_id_number": roll,
                "department": "Engineering",
                "email": email,
                "username": uname,
                "full_name": name,
                "password": "Password@123",
            },
            headers=admin_headers,
        ).json()
        l = client.post("/api/v1/auth/login", json={"username_or_email": uname, "password": "Password@123"})
        return r["id"], {"Authorization": f"Bearer {l.json()['access_token']}"}

    s_rahul_id, s_rahul_hdr = make_student("Rahul", "stu_rahul", "rahul@spec.com", "SPEC-001")
    s_akash_id, s_akash_hdr = make_student("Akash", "stu_akash", "akash@spec.com", "SPEC-002")
    s_suresh_id, s_suresh_hdr = make_student("Suresh", "stu_suresh", "suresh@spec.com", "SPEC-003")

    # 5. Configure Barber Schedule for 15:00 - 18:00 (3:00 PM - 6:00 PM) on target date
    target_date = (date.today() + timedelta(days=5)).isoformat()
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
        "s30_id": s30["id"],
        "s45_id": s45["id"],
        "target_date": target_date,
        "rahul": {"id": s_rahul_id, "headers": s_rahul_hdr},
        "akash": {"id": s_akash_id, "headers": s_akash_hdr},
        "suresh": {"id": s_suresh_id, "headers": s_suresh_hdr},
    }


def test_complete_spec_scenario_fixed_appointment_and_available_now(spec_environment):
    """
    Validates the exact specification flow from Section 7, 9, 10, 12, 13:
      - Barber works 15:00 - 18:00
      - 15:30 Rahul booked
      - 16:00 Akash booked
      - 16:30 Suresh booked
      - Rahul becomes NO_SHOW
      - 15:30 becomes AVAILABLE NOW
      - Akash (16:00) and Suresh (16:30) remain strictly fixed at original times
      - Suresh books the earlier 15:30 slot
      - Akash remains at 16:00
      - Suresh physical visit: ARRIVED -> IN_SERVICE -> COMPLETED
    """
    env = spec_environment
    barber_id = env["barber_id"]
    s30_id = env["s30_id"]
    target_date = env["target_date"]
    barber_headers = env["barber_headers"]

    # 1. Book Rahul at 15:30
    res_rahul = client.post(
        "/api/v1/appointments",
        json={"barber_id": barber_id, "service_id": s30_id, "appointment_date": target_date, "start_time": "15:30:00"},
        headers=env["rahul"]["headers"],
    )
    assert res_rahul.status_code == 201
    rahul_appt_id = res_rahul.json()["id"]

    # 2. Book Akash at 16:00
    res_akash = client.post(
        "/api/v1/appointments",
        json={"barber_id": barber_id, "service_id": s30_id, "appointment_date": target_date, "start_time": "16:00:00"},
        headers=env["akash"]["headers"],
    )
    assert res_akash.status_code == 201
    akash_appt_id = res_akash.json()["id"]

    # 3. Book Suresh at 16:30
    res_suresh = client.post(
        "/api/v1/appointments",
        json={"barber_id": barber_id, "service_id": s30_id, "appointment_date": target_date, "start_time": "16:30:00"},
        headers=env["suresh"]["headers"],
    )
    assert res_suresh.status_code == 201
    suresh_appt_id = res_suresh.json()["id"]

    # 4. Rahul is marked NO_SHOW
    no_show_res = client.post(
        f"/api/v1/appointments/{rahul_appt_id}/no-show?ignore_grace_period=true",
        headers=barber_headers,
    )
    assert no_show_res.status_code == 200
    assert no_show_res.json()["status"] == "NO_SHOW"
    assert no_show_res.json()["is_available_now_slot"] is True

    # 5. Verify Fixed Appointment Principle: Akash & Suresh MUST NOT shift
    akash_check = client.get(f"/api/v1/appointments/{akash_appt_id}", headers=env["akash"]["headers"]).json()
    assert akash_check["start_time"] == "16:00:00"
    assert akash_check["end_time"] == "16:30:00"

    suresh_check = client.get(f"/api/v1/appointments/{suresh_appt_id}", headers=env["suresh"]["headers"]).json()
    assert suresh_check["start_time"] == "16:30:00"
    assert suresh_check["end_time"] == "17:00:00"

    # 6. Suresh cancels his 16:30 appointment and claims the earlier 15:30 released slot
    cancel_suresh = client.post(
        f"/api/v1/appointments/{suresh_appt_id}/cancel",
        json={"reason": "Moving to earlier released slot"},
        headers=env["suresh"]["headers"],
    )
    assert cancel_suresh.status_code == 200

    claim_suresh = client.post(
        f"/api/v1/appointments/available-now/{rahul_appt_id}/claim",
        json={"service_id": s30_id, "notes": "Suresh moved to earlier slot"},
        headers=env["suresh"]["headers"],
    )
    assert claim_suresh.status_code == 201
    suresh_new_appt_id = claim_suresh.json()["id"]
    assert claim_suresh.json()["start_time"] == "15:30:00"

    # 7. Akash at 16:00 remains strictly untouched
    akash_check2 = client.get(f"/api/v1/appointments/{akash_appt_id}", headers=env["akash"]["headers"]).json()
    assert akash_check2["start_time"] == "16:00:00"

    # 8. Physical Visit Tracking for Suresh at 15:30
    # Step a: Arrived
    arrive_res = client.post(f"/api/v1/appointments/{suresh_new_appt_id}/arrive", headers=barber_headers)
    assert arrive_res.status_code == 200
    assert arrive_res.json()["status"] == "ARRIVED"

    # Step b: In Service
    start_res = client.post(f"/api/v1/appointments/{suresh_new_appt_id}/start", headers=barber_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_SERVICE"

    # Step c: Completed
    complete_res = client.post(f"/api/v1/appointments/{suresh_new_appt_id}/complete", headers=barber_headers)
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "COMPLETED"

    # Step d: Verify Visit Record
    visit_data = client.get(f"/api/v1/visits/appointment/{suresh_new_appt_id}", headers=barber_headers).json()
    assert visit_data["arrival_time"] is not None
    assert visit_data["service_start_time"] is not None
    assert visit_data["completion_time"] is not None
    assert visit_data["actual_duration_minutes"] >= 1
