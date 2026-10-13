from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: str | None = None


class DepartmentSummary(BaseModel):
    """Small version used inside an employee response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_active: bool
    employee_count: int = 0  # active employees only
