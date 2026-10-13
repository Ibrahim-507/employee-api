from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.department import DepartmentCreate, DepartmentRead
from app.schemas.employee import EmployeeRead
from app.schemas.pagination import Page, build_page
from app.services import department_service, employee_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(include_inactive: bool = False, db: Session = Depends(get_db)):
    return department_service.list_departments(db, include_inactive)


@router.post("", response_model=DepartmentRead, status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    return department_service.create_department(db, payload)


@router.get("/{department_id}/employees", response_model=Page[EmployeeRead])
def list_department_employees(
    department_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Search in name and email"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    department_service.get_department(db, department_id)  # 404 if missing
    items, total = employee_service.list_employees(
        db,
        page=page,
        size=size,
        department_id=department_id,
        q=q,
        include_inactive=include_inactive,
    )
    return build_page(items, total, page, size)
