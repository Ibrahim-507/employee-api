from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.department import DepartmentSummary

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]


def _lowercase_email(value: str | None) -> str | None:
    return value.lower() if value else value


def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("hire_date cannot be in the future")
    return value


def _empty_phone_to_none(value: str | None) -> str | None:
    return value or None


class EmployeeCreate(BaseModel):
    """What the client sends to create an employee."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    work_email: EmailStr
    phone: Phone | None = None
    hire_date: date
    department_id: int = Field(gt=0)
    manager_id: int | None = Field(default=None, gt=0)

    _email = field_validator("work_email")(_lowercase_email)
    _hire = field_validator("hire_date")(_not_in_future)
    _phone = field_validator("phone")(_empty_phone_to_none)


class EmployeeUpdate(BaseModel):
    """PATCH body: every field is optional. Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    work_email: EmailStr | None = None
    phone: Phone | None = None
    hire_date: date | None = None
    department_id: int | None = Field(default=None, gt=0)
    manager_id: int | None = Field(default=None, gt=0)  # null = remove manager
    is_active: bool | None = None

    _email = field_validator("work_email")(_lowercase_email)
    _hire = field_validator("hire_date")(_not_in_future)
    _phone = field_validator("phone")(_empty_phone_to_none)

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self):
        # phone and manager_id may be set to null (clears them);
        # the rest must have a real value if they are sent at all.
        for name in (
            "first_name",
            "last_name",
            "work_email",
            "hire_date",
            "department_id",
            "is_active",
        ):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class EmployeeRead(BaseModel):
    """What the API returns for an employee."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    work_email: str
    phone: str | None
    hire_date: date
    is_active: bool
    department: DepartmentSummary
    manager_id: int | None
    created_at: datetime
    updated_at: datetime
