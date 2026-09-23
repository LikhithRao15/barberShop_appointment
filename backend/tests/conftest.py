import pytest
from sqlalchemy import text
from app.database import engine, SessionLocal
from app.services.user_service import seed_initial_admin


@pytest.fixture(scope="session", autouse=True)
def clean_database_before_tests():
    """Cleans test database and seeds initial admin before running test session."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE notifications, visits, appointments, blocked_periods, "
                "schedule_breaks, schedules, students, barbers, services, users RESTART IDENTITY CASCADE;"
            )
        )
        conn.commit()

    db = SessionLocal()
    seed_initial_admin(db)
    db.close()
    yield
