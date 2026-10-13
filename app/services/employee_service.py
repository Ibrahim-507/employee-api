from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Department, Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.hierarchy_service import get_all_reports


# ---------------------------------------------------------------- helpers

def _escape_like(text: str) -> str:
    """Make % and _ in the search text match literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _ensure_email_free(db: Session, email: str, exclude_id: int | None = None) -> None:
    stmt = select(Employee.id).where(func.lower(Employee.work_email) == email.lower())
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError(
            f"An employee with email '{email}' already exists",
            code="email_already_exists",
        )


def _ensure_department_usable(db: Session, department_id: int) -> None:
    department = db.get(Department, department_id)
    if department is None or not department.is_active:
        raise BusinessRuleError(
            f"Department {department_id} does not exist or is inactive",
            code="invalid_reference",
            details=[{"field": "department_id", "message": "unknown department"}],
        )


def _ensure_manager_usable(db: Session, employee: Employee | None, manager_id: int) -> None:
    if employee is not None and manager_id == employee.id:
        raise BusinessRuleError(
            "An employee cannot be their own manager", code="invalid_manager"
        )
    manager = db.get(Employee, manager_id)
    if manager is None or not manager.is_active:
        raise BusinessRuleError(
            f"Manager {manager_id} does not exist or is inactive",
            code="invalid_reference",
            details=[{"field": "manager_id", "message": "unknown manager"}],
        )
    if employee is not None:
        below = {e.id for e in get_all_reports(db, employee.id)}
        if manager_id in below:
            raise BusinessRuleError(
                "This would create a loop: the new manager already reports "
                "(directly or indirectly) to this employee",
                code="invalid_manager",
            )


# ---------------------------------------------------------------- reads

def get_employee(db: Session, employee_id: int) -> Employee:
    stmt = (
        select(Employee)
        .options(joinedload(Employee.department))
        .where(Employee.id == employee_id)
        .execution_options(populate_existing=True)  # always read fresh values
    )
    employee = db.scalars(stmt).first()
    if employee is None:
        raise NotFoundError(f"Employee {employee_id} not found")
    return employee


def list_employees(
    db: Session,
    *,
    page: int,
    size: int,
    department: str | None = None,
    department_id: int | None = None,
    q: str | None = None,
    include_inactive: bool = False,
) -> tuple[list[Employee], int]:
    """Filters, search and pagination all combine (they are ANDed together)."""
    conditions = []
    if not include_inactive:
        conditions.append(Employee.is_active.is_(True))
    if department_id is not None:
        conditions.append(Employee.department_id == department_id)
    if department and department.strip():
        conditions.append(
            Employee.department.has(
                func.lower(Department.name) == department.strip().lower()
            )
        )
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        full_name = func.concat(Employee.first_name, " ", Employee.last_name)
        conditions.append(
            or_(
                Employee.first_name.ilike(pattern, escape="\\"),
                Employee.last_name.ilike(pattern, escape="\\"),
                Employee.work_email.ilike(pattern, escape="\\"),
                full_name.ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(Employee).where(*conditions)) or 0
    stmt = (
        select(Employee)
        .options(joinedload(Employee.department))
        .where(*conditions)
        .order_by(Employee.last_name, Employee.first_name, Employee.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(db.scalars(stmt).unique()), total


def get_team(db: Session, employee_id: int, include_inactive: bool = False) -> list[Employee]:
    """Direct reports of one manager."""
    get_employee(db, employee_id)  # 404 if the manager does not exist
    conditions = [Employee.manager_id == employee_id]
    if not include_inactive:
        conditions.append(Employee.is_active.is_(True))
    stmt = (
        select(Employee)
        .options(joinedload(Employee.department))
        .where(*conditions)
        .order_by(Employee.last_name, Employee.first_name, Employee.id)
    )
    return list(db.scalars(stmt).unique())


# ---------------------------------------------------------------- writes

def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    _ensure_email_free(db, data.work_email)
    _ensure_department_usable(db, data.department_id)
    if data.manager_id is not None:
        _ensure_manager_usable(db, None, data.manager_id)

    employee = Employee(**data.model_dump())
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:  # two requests with the same email at the same moment
        db.rollback()
        raise ConflictError(
            f"An employee with email '{data.work_email}' already exists",
            code="email_already_exists",
        )
    return get_employee(db, employee.id)


def update_employee(db: Session, employee_id: int, data: EmployeeUpdate) -> Employee:
    employee = get_employee(db, employee_id)
    changes = data.model_dump(exclude_unset=True)  # only what the client sent

    if "work_email" in changes:
        _ensure_email_free(db, changes["work_email"], exclude_id=employee.id)
    if "department_id" in changes:
        _ensure_department_usable(db, changes["department_id"])
    if changes.get("manager_id") is not None:
        _ensure_manager_usable(db, employee, changes["manager_id"])

    for field, value in changes.items():
        setattr(employee, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not save the changes", code="conflict")
    return get_employee(db, employee_id)


def deactivate_employee(db: Session, employee_id: int) -> None:
    """Soft delete: the row stays, is_active becomes False."""
    employee = get_employee(db, employee_id)
    if not employee.is_active:
        return  # already inactive: deleting twice is fine
    active_reports = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.manager_id == employee.id, Employee.is_active.is_(True))
    )
    if active_reports:
        raise ConflictError(
            f"Employee still has {active_reports} active direct report(s). "
            "Give them a new manager first.",
            code="has_active_reports",
        )
    employee.is_active = False
    db.commit()
