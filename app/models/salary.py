from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import Employee


class Salary(TimestampMixin, Base):
    """One row = "from this date, the employee earns this much per month".

    An employee has several rows over time (salary history). The row with the
    latest effective_from date is the current salary.
    """

    __tablename__ = "salaries"
    __table_args__ = (
        UniqueConstraint("employee_id", "effective_from", name="uq_salaries_employee_effective_from"),
        CheckConstraint("monthly_salary > 0", name="positive_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default="INR", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="salaries")
