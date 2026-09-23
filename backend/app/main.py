import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import check_db_connection, SessionLocal
from app.routers.health import router as health_router
from app.routers import api_router
from app.services.user_service import seed_initial_admin

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Starting up Barber Shop Appointment & Visit Management System API...")
    db_ok = check_db_connection()
    if db_ok:
        logger.info("Successfully established connection to PostgreSQL database.")
        try:
            db = SessionLocal()
            seed_initial_admin(db)
            db.close()
        except Exception as e:
            logger.error(f"Error while running startup seeders: {e}")
    else:
        logger.warning(
            "Failed to connect to PostgreSQL database on startup. Please verify database availability."
        )
    yield
    logger.info("Shutting down Barber Shop Appointment & Visit Management System API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-ready backend for the Barber Shop Appointment & Visit Management System. "
        "Enforces deterministic availability, fixed appointments, and separated visit tracking."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to configured client domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level health check endpoint for container probes
app.include_router(health_router)

# Versioned API routes under /api/v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_PREFIX,
    }
