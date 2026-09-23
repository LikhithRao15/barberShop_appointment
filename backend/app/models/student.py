from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    student_id_number = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), nullable=True)
    year_of_study = Column(Integer, nullable=True)
    hostel_or_room = Column(String(100), nullable=True)
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

    user = relationship("User", back_populates="student_profile")
    appointments = relationship(
        "Appointment",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Student id={self.id} student_id_number='{self.student_id_number}'>"
