from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Visit(Base):
    """
    Tracks the physical in-shop visit execution separately from the booking record.
    """
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    service_start_time = Column(DateTime(timezone=True), nullable=True)
    completion_time = Column(DateTime(timezone=True), nullable=True)
    actual_duration_minutes = Column(Integer, nullable=True)
    visit_notes = Column(Text, nullable=True)
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

    appointment = relationship("Appointment", back_populates="visit")

    def __repr__(self):
        return (
            f"<Visit id={self.id} appointment_id={self.appointment_id} "
            f"arrived={self.arrival_time} started={self.service_start_time} "
            f"completed={self.completion_time}>"
        )
