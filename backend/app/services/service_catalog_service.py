import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate

logger = logging.getLogger(__name__)


def get_service_by_id(db: Session, service_id: int) -> Optional[Service]:
    return db.query(Service).filter(Service.id == service_id).first()


def get_service_by_name(db: Session, name: str) -> Optional[Service]:
    return db.query(Service).filter(Service.name == name.strip()).first()


def list_services(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> List[Service]:
    query = db.query(Service)
    if active_only:
        query = query.filter(Service.is_active == True)
    return query.offset(skip).limit(limit).all()


def create_service(db: Session, service_in: ServiceCreate) -> Service:
    existing = get_service_by_name(db, service_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A service named '{service_in.name}' already exists.",
        )

    service = Service(
        name=service_in.name.strip(),
        description=service_in.description.strip() if service_in.description else None,
        duration_minutes=service_in.duration_minutes,
        price=service_in.price,
        is_active=service_in.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def update_service(db: Session, service: Service, service_in: ServiceUpdate) -> Service:
    if service_in.name and service_in.name.strip() != service.name:
        existing = get_service_by_name(db, service_in.name)
        if existing and existing.id != service.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A service named '{service_in.name}' already exists.",
            )
        service.name = service_in.name.strip()

    if service_in.description is not None:
        service.description = service_in.description.strip() if service_in.description else None
    if service_in.duration_minutes is not None:
        service.duration_minutes = service_in.duration_minutes
    if service_in.price is not None:
        service.price = service_in.price
    if service_in.is_active is not None:
        service.is_active = service_in.is_active

    db.commit()
    db.refresh(service)
    return service


def delete_service(db: Session, service: Service) -> None:
    # Soft delete / deactivation to preserve appointment historical records
    service.is_active = False
    db.commit()
    db.refresh(service)
