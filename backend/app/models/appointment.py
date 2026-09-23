import enum
from sqlalchemy import Column, Integer, String, Boolean, Date, Time, DateTime, Enum, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from app.database import Base


class AppointmentStatus(str, enum.Enum):
    BOOKED = "BOOKED"
    ARRIVED = "ARRIVED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    barber_id = Column(
        Integer,
        ForeignKey("barbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id = Column(
        Integer,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(
        Enum(AppointmentStatus, name="appointment_status_enum", create_type=False),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        index=True,
    )
    notes = Column(String(500), nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    no_show_at = Column(DateTime(timezone=True), nullable=True)
    is_available_now_slot = Column(Boolean, default=False, nullable=False)
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

    student = relationship("Student", back_populates="appointments")
    barber = relationship("Barber", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    visit = relationship(
        "Visit",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_appointments_barber_date_status",
            "barber_id",
            "appointment_date",
            "status",
        ),
        Index(
            "ix_appointments_student_date_status",
            "student_id",
            "appointment_date",
            "status",
        ),
    )

    def __repr__(self):
        return (
            f"<Appointment id={self.id} barber_id={self.barber_id} "
            f"student_id={self.student_id} date={self.appointment_date} "
            f"{self.start_time}-{self.end_time} status={self.status}>"
        )
