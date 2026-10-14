from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import Employee

ATTENDANCE_STATUSES = ("present", "absent", "on_leave", "half_day")


class AttendanceRecord(TimestampMixin, Base):
    """One row per employee per working day."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        # An employee can have only one record per day.
        UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_work_date"),
        CheckConstraint(
            "status IN ('present', 'absent', 'on_leave', 'half_day')", name="valid_status"
        ),
        CheckConstraint(
            "check_in IS NULL OR check_out IS NULL OR check_out > check_in",
            name="checkout_after_checkin",
        ),
        Index("ix_attendance_records_work_date", "work_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    check_in: Mapped[time | None] = mapped_column(Time)
    check_out: Mapped[time | None] = mapped_column(Time)

    employee: Mapped[Employee] = relationship(back_populates="attendance_records")
