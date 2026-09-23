import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.services.user_service import seed_initial_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def auth_tokens():
    """Returns auth tokens for admin, student, and barber."""
    db: Session = SessionLocal()
    seed_initial_admin(db)
    db.close()

    # Admin token
    admin_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    admin_token = admin_res.json()["access_token"]

    # Student token
    student_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_student", "password": "Student@123"},
    )
    student_token = student_res.json()["access_token"]

    # Barber token
    barber_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_barber", "password": "Barber@123"},
    )
    barber_token = barber_res.json()["access_token"]

    return {
        "admin": admin_token,
        "student": student_token,
        "barber": barber_token,
    }


def test_create_and_manage_service(auth_tokens):
    admin_headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    student_headers = {"Authorization": f"Bearer {auth_tokens['student']}"}

    # 1. Non-admin attempting to create a service -> 403 Forbidden
    res_unauth = client.post(
        "/api/v1/services",
        json={
            "name": "Classic Haircut",
            "description": "Standard haircut and neck trim",
            "duration_minutes": 30,
            "price": 15.00,
            "is_active": True,
        },
        headers=student_headers,
    )
    assert res_unauth.status_code == 403

    # 2. Admin creating a valid service -> 201 Created
    res_create = client.post(
        "/api/v1/services",
        json={
            "name": "Classic Haircut",
            "description": "Standard haircut and neck trim",
            "duration_minutes": 30,
            "price": 15.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert res_create.status_code == 201
    service_id = res_create.json()["id"]
    assert res_create.json()["duration_minutes"] == 30
    assert float(res_create.json()["price"]) == 15.0

    # 3. Create another service (Beard Trim 15 min)
    res_beard = client.post(
        "/api/v1/services",
        json={
            "name": "Beard Grooming",
            "description": "Precision beard trim and oiling",
            "duration_minutes": 15,
            "price": 10.00,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert res_beard.status_code == 201

    # 4. Public / Authenticated listing of services
    res_list = client.get("/api/v1/services")
    assert res_list.status_code == 200
    services = res_list.json()
    assert len(services) >= 2
    names = [s["name"] for s in services]
    assert "Classic Haircut" in names
    assert "Beard Grooming" in names

    # 5. Get service by ID
    res_get = client.get(f"/api/v1/services/{service_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Classic Haircut"

    # 6. Admin updating service
    res_update = client.put(
        f"/api/v1/services/{service_id}",
        json={"duration_minutes": 35, "price": 18.00},
        headers=admin_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["duration_minutes"] == 35


def test_create_and_manage_student(auth_tokens):
    admin_headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}

    # 1. Admin onboarding a student with new credentials
    res_create = client.post(
        "/api/v1/students",
        json={
            "student_id_number": "STU-2026-001",
            "department": "Computer Science",
            "year_of_study": 3,
            "hostel_or_room": "Hostel B, Room 204",
            "email": "rahul.sharma@example.com",
            "username": "rahul_s",
            "full_name": "Rahul Sharma",
            "phone_number": "555-4444",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    assert res_create.status_code == 201
    data = res_create.json()
    assert data["student_id_number"] == "STU-2026-001"
    assert data["user"]["username"] == "rahul_s"

    # 2. Login as the newly created student
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "rahul_s", "password": "Password@123"},
    )
    assert login_res.status_code == 200
    rahul_token = login_res.json()["access_token"]
    rahul_headers = {"Authorization": f"Bearer {rahul_token}"}

    # 3. Student accessing /students/me
    res_me = client.get("/api/v1/students/me", headers=rahul_headers)
    assert res_me.status_code == 200
    assert res_me.json()["student_id_number"] == "STU-2026-001"
    assert res_me.json()["department"] == "Computer Science"

    # 4. Student updating their own profile
    res_upd = client.put(
        "/api/v1/students/me",
        json={"hostel_or_room": "Hostel B, Room 310", "phone_number": "555-9999"},
        headers=rahul_headers,
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["hostel_or_room"] == "Hostel B, Room 310"


def test_create_and_manage_barber(auth_tokens):
    admin_headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}

    # 1. Admin onboarding a barber with new credentials
    res_create = client.post(
        "/api/v1/barbers",
        json={
            "bio": "Master barber with 8 years of styling experience",
            "specialties": "Fades, Beard Styling, Scissor Cuts",
            "shop_name": "Main Campus Saloon",
            "chair_number": 1,
            "is_available_for_booking": True,
            "email": "vikram.barber@example.com",
            "username": "vikram_cuts",
            "full_name": "Vikram Singh",
            "phone_number": "555-7777",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    assert res_create.status_code == 201
    barber_id = res_create.json()["id"]
    assert res_create.json()["chair_number"] == 1

    # 2. Login as the newly created barber
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "vikram_cuts", "password": "Password@123"},
    )
    assert login_res.status_code == 200
    vikram_token = login_res.json()["access_token"]
    vikram_headers = {"Authorization": f"Bearer {vikram_token}"}

    # 3. Barber accessing /barbers/me
    res_me = client.get("/api/v1/barbers/me", headers=vikram_headers)
    assert res_me.status_code == 200
    assert res_me.json()["specialties"] == "Fades, Beard Styling, Scissor Cuts"

    # 4. Public / Student listing barbers
    res_list = client.get("/api/v1/barbers")
    assert res_list.status_code == 200
    barbers = res_list.json()
    assert len(barbers) >= 1
    assert any(b["id"] == barber_id for b in barbers)
