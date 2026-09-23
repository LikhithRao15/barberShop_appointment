from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.service import ServiceOut, ServiceCreate, ServiceUpdate
from app.core.deps import require_admin
from app.services import service_catalog_service

router = APIRouter(prefix="/services", tags=["Services"])


@router.get(
    "",
    response_model=List[ServiceOut],
    summary="List Services",
    description="Lists available haircut and grooming services with durations and prices.",
)
def list_services(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    return service_catalog_service.list_services(db, skip=skip, limit=limit, active_only=active_only)


@router.get(
    "/{service_id}",
    response_model=ServiceOut,
    summary="Get Service Details",
    description="Retrieves a specific service by ID.",
)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    service = service_catalog_service.get_service_by_id(db, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found.",
        )
    return service


@router.post(
    "",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Service (Admin Only)",
    description="Adds a new service to the catalog with duration and price.",
)
def create_service(
    service_in: ServiceCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service_catalog_service.create_service(db, service_in)


@router.put(
    "/{service_id}",
    response_model=ServiceOut,
    summary="Update Service (Admin Only)",
    description="Updates service name, duration, price, or active status.",
)
def update_service(
    service_id: int,
    service_in: ServiceUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = service_catalog_service.get_service_by_id(db, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found.",
        )
    return service_catalog_service.update_service(db, service, service_in)


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete/Deactivate Service (Admin Only)",
    description="Soft-deactivates a service so past appointment histories are preserved.",
)
def delete_service(
    service_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = service_catalog_service.get_service_by_id(db, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found.",
        )
    service_catalog_service.delete_service(db, service)
    return None
