from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)  # Crucial scheduling parameter!
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointments = relationship(
        "Appointment",
        back_populates="service",
        passive_deletes=False,
    )

    def __repr__(self):
        return f"<Service id={self.id} name='{self.name}' duration={self.duration_minutes}m price={self.price}>"
