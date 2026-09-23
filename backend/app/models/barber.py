from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Barber(Base):
    __tablename__ = "barbers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    bio = Column(Text, nullable=True)
    specialties = Column(String(255), nullable=True)
    shop_name = Column(String(150), nullable=True, default="Campus Barber Shop")
    chair_number = Column(Integer, nullable=True)
    is_available_for_booking = Column(Boolean, default=True, nullable=False)
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

    user = relationship("User", back_populates="barber_profile")
    schedules = relationship(
        "Schedule",
        back_populates="barber",
        cascade="all, delete-orphan",
    )
    blocked_periods = relationship(
        "BlockedPeriod",
        back_populates="barber",
        cascade="all, delete-orphan",
    )
    appointments = relationship(
        "Appointment",
        back_populates="barber",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Barber id={self.id} user_id={self.user_id}>"
