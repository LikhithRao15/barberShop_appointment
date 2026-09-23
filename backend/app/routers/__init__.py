from fastapi import APIRouter
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.students import router as students_router
from app.routers.barbers import router as barbers_router
from app.routers.services import router as services_router
from app.routers.schedules import router as schedules_router
from app.routers.appointments import router as appointments_router
from app.routers.visits import router as visits_router
from app.routers.notifications import router as notifications_router
from app.routers.admin import router as admin_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(students_router)
api_router.include_router(barbers_router)
api_router.include_router(services_router)
api_router.include_router(schedules_router)
api_router.include_router(appointments_router)
api_router.include_router(visits_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_router)

__all__ = [
    "api_router",
    "health_router",
    "auth_router",
    "students_router",
    "barbers_router",
    "services_router",
    "schedules_router",
    "appointments_router",
    "visits_router",
    "notifications_router",
    "admin_router",
]
