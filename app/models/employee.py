from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.department import Department
from app.models.mixins import TimestampMixin
from app.models.role import Role, employee_roles


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        # Fast search by name (last name first, then first name).
        Index("ix_employees_name", "last_name", "first_name"),
        # Nobody can be their own manager.
        CheckConstraint("manager_id <> id", name="not_own_manager"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    work_email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(30))
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Soft delete: set to False instead of erasing the row.
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )

    # Many employees -> one department. RESTRICT = a department that still
    # has employees cannot be hard-deleted.
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Self-reference: points to another row in the SAME table.
    # NULL means "no manager" (e.g. the CEO). If a manager row is ever
    # hard-deleted, their reports keep existing with manager_id = NULL.
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )

    department: Mapped[Department] = relationship(back_populates="employees")

    # remote_side tells SQLAlchemy that "id" is the parent side of the link.
    manager: Mapped[Employee | None] = relationship(
        remote_side=[id], back_populates="direct_reports"
    )
    direct_reports: Mapped[list[Employee]] = relationship(back_populates="manager")

    # Many-to-many through employee_roles.
    roles: Mapped[list[Role]] = relationship(
        secondary=employee_roles, back_populates="employees"
    )

    def __repr__(self) -> str:
        return f"Employee(id={self.id}, email={self.work_email!r})"
