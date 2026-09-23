import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal, get_db
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.deps import require_admin, require_barber, require_student
from app.services.user_service import seed_initial_admin

client = TestClient(app)

# Helper test router for testing role authorization guards
mock_rbac_router = APIRouter(prefix="/test-rbac")


@mock_rbac_router.get("/admin-only")
def handle_admin_only(user: User = Depends(require_admin)):
    return {"message": "admin ok", "user": user.username}


@mock_rbac_router.get("/barber-only")
def handle_barber_only(user: User = Depends(require_barber)):
    return {"message": "barber ok", "user": user.username}


@mock_rbac_router.get("/student-only")
def handle_student_only(user: User = Depends(require_student)):
    return {"message": "student ok", "user": user.username}


app.include_router(mock_rbac_router)


@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    """Seeds test users for auth and RBAC tests."""
    db: Session = SessionLocal()
    # Ensure admin exists
    seed_initial_admin(db)

    # Create active student
    student = db.query(User).filter(User.username == "test_student").first()
    if not student:
        student = User(
            email="student@example.com",
            username="test_student",
            full_name="Test Student",
            phone_number="555-1111",
            hashed_password=get_password_hash("Student@123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(student)

    # Create active barber
    barber = db.query(User).filter(User.username == "test_barber").first()
    if not barber:
        barber = User(
            email="barber@example.com",
            username="test_barber",
            full_name="Test Barber",
            phone_number="555-2222",
            hashed_password=get_password_hash("Barber@123"),
            role=UserRole.BARBER,
            is_active=True,
        )
        db.add(barber)

    # Create inactive user
    inactive = db.query(User).filter(User.username == "inactive_user").first()
    if not inactive:
        inactive = User(
            email="inactive@example.com",
            username="inactive_user",
            full_name="Inactive User",
            phone_number="555-3333",
            hashed_password=get_password_hash("Inactive@123"),
            role=UserRole.STUDENT,
            is_active=False,
        )
        db.add(inactive)

    db.commit()
    db.close()


def test_admin_login_with_username_success():
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["is_active"] is True


def test_admin_login_with_email_success():
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin@barberbooking.com", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "admin@barberbooking.com"


def test_login_invalid_password():
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Incorrect" in response.json()["detail"]


def test_login_nonexistent_user():
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ghost_user", "password": "SomePassword123"},
    )
    assert response.status_code == 401
    assert "Incorrect" in response.json()["detail"]


def test_login_inactive_user_forbidden():
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "inactive_user", "password": "Inactive@123"},
    )
    assert response.status_code == 403
    assert "Inactive" in response.json()["detail"]


def test_get_me_with_valid_token():
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_student", "password": "Student@123"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_student"
    assert data["role"] == "STUDENT"


def test_get_me_without_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_get_me_with_invalid_token():
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_rbac_admin_endpoint():
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

    # Admin accessing admin endpoint -> 200
    res_admin = client.get(
        "/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200

    # Student accessing admin endpoint -> 403 Forbidden
    res_student = client.get(
        "/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student.status_code == 403


def test_rbac_barber_endpoint():
    barber_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_barber", "password": "Barber@123"},
    )
    barber_token = barber_res.json()["access_token"]

    student_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_student", "password": "Student@123"},
    )
    student_token = student_res.json()["access_token"]

    # Barber accessing barber endpoint -> 200
    res_barber = client.get(
        "/test-rbac/barber-only",
        headers={"Authorization": f"Bearer {barber_token}"},
    )
    assert res_barber.status_code == 200

    # Student accessing barber endpoint -> 403
    res_student = client.get(
        "/test-rbac/barber-only",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student.status_code == 403


def test_logout_endpoint():
    student_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "test_student", "password": "Student@123"},
    )
    student_token = student_res.json()["access_token"]

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
