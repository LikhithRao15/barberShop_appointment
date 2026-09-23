from fastapi import APIRouter, status, Response
from app.config import settings
from app.database import check_db_connection

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="System and Database Health Check",
    status_code=status.HTTP_200_OK,
)
def health_check(response: Response):
    """
    Checks the status of the API server and the underlying PostgreSQL database.
    Returns 200 OK if both are operational, or 503 SERVICE UNAVAILABLE if DB is unreachable.
    """
    db_connected = check_db_connection()
    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "database": "unreachable",
        }

    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected",
    }
