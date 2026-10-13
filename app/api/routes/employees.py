from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.schemas.pagination import Page, build_page
from app.services import employee_service

# Routes only: read the request, call a service, return the result.
router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeRead, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    return employee_service.create_employee(db, payload)


@router.get("", response_model=Page[EmployeeRead])
def list_employees(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department: str | None = Query(None, description="Department name (not case sensitive)"),
    q: str | None = Query(None, description="Search in name and email"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    items, total = employee_service.list_employees(
        db,
        page=page,
        size=size,
        department=department,
        q=q,
        include_inactive=include_inactive,
    )
    return build_page(items, total, page, size)


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    return employee_service.get_employee(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db)
):
    return employee_service.update_employee(db, employee_id, payload)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee_service.deactivate_employee(db, employee_id)
    return Response(status_code=204)


@router.get("/{employee_id}/team", response_model=list[EmployeeRead])
def get_team(
    employee_id: int, include_inactive: bool = False, db: Session = Depends(get_db)
):
    """Direct reports of this employee."""
    return employee_service.get_team(db, employee_id, include_inactive)
