from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Department, Employee
from app.schemas.department import DepartmentCreate, DepartmentRead


def get_department(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise NotFoundError(f"Department {department_id} not found")
    return department


def list_departments(db: Session, include_inactive: bool = False) -> list[DepartmentRead]:
    employee_count = (
        select(func.count(Employee.id))
        .where(Employee.department_id == Department.id, Employee.is_active.is_(True))
        .correlate(Department)
        .scalar_subquery()
    )
    stmt = select(Department, employee_count).order_by(Department.name)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    return [
        DepartmentRead(
            id=dept.id,
            name=dept.name,
            description=dept.description,
            is_active=dept.is_active,
            employee_count=count,
        )
        for dept, count in db.execute(stmt).all()
    ]


def create_department(db: Session, data: DepartmentCreate) -> DepartmentRead:
    exists = db.scalar(
        select(Department.id).where(func.lower(Department.name) == data.name.lower())
    )
    if exists:
        raise ConflictError(
            f"Department '{data.name}' already exists", code="department_name_exists"
        )
    department = Department(name=data.name, description=data.description)
    db.add(department)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"Department '{data.name}' already exists", code="department_name_exists"
        )
    return DepartmentRead(
        id=department.id,
        name=department.name,
        description=department.description,
        is_active=department.is_active,
        employee_count=0,
    )
