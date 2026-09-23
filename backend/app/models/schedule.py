from sqlalchemy import Column, Integer, String, Boolean, Date, Time, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Schedule(Base):
    """
    Defines working hours for a barber.
    Can be a recurring weekly schedule (day_of_week 0=Monday..6=Sunday)
    or a specific date override (schedule_date is set).
    """
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    barber_id = Column(
        Integer,
        ForeignKey("barbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # If schedule_date is set, it overrides the recurring day_of_week schedule
    schedule_date = Column(Date, nullable=True, index=True)
    # 0 = Monday, 1 = Tuesday, ..., 6 = Sunday
    day_of_week = Column(Integer, nullable=True, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_day_off = Column(Boolean, default=False, nullable=False)
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

    barber = relationship("Barber", back_populates="schedules")
    breaks = relationship(
        "ScheduleBreak",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleBreak.start_time",
    )

    def __repr__(self):
        return (
            f"<Schedule id={self.id} barber_id={self.barber_id} "
            f"date={self.schedule_date} dow={self.day_of_week} "
            f"{self.start_time}-{self.end_time}>"
        )


class ScheduleBreak(Base):
    """
    Defines regular or specific break periods within a working schedule (e.g. Lunch).
    """
    __tablename__ = "schedule_breaks"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer,
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, default="Break")
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    schedule = relationship("Schedule", back_populates="breaks")

    def __repr__(self):
        return f"<ScheduleBreak {self.name} {self.start_time}-{self.end_time}>"


class BlockedPeriod(Base):
    """
    Ad-hoc or emergency blocked periods for a barber on a specific date.
    (e.g., Chair maintenance, urgent leave, power outage).
    """
    __tablename__ = "blocked_periods"

    id = Column(Integer, primary_key=True, index=True)
    barber_id = Column(
        Integer,
        ForeignKey("barbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blocked_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    reason = Column(String(255), nullable=True, default="Unavailable")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    barber = relationship("Barber", back_populates="blocked_periods")

    def __repr__(self):
        return (
            f"<BlockedPeriod barber_id={self.barber_id} date={self.blocked_date} "
            f"{self.start_time}-{self.end_time}>"
        )
