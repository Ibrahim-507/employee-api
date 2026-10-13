from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import Employee

# Association table: one row = "this employee holds this role".
# The pair (employee_id, role_id) is the primary key, so the same role
# cannot be given to the same employee twice.
employee_roles = Table(
    "employee_roles",
    Base.metadata,
    Column(
        "employee_id",
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    employees: Mapped[list[Employee]] = relationship(
        secondary=employee_roles, back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"Role(id={self.id}, title={self.title!r})"
