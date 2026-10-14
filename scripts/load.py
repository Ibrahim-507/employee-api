"""Step 3: write the generated data into PostgreSQL.

SAFE TO RUN TWICE. Every insert uses "ON CONFLICT DO NOTHING" on a natural key:

    departments  -> name            roles        -> title
    employees    -> work_email      employee_roles -> (employee, role)
    salaries     -> (employee, effective_from)
    attendance   -> (employee, work_date)

A row that already exists is skipped, never changed or duplicated. Existing data
(for example employees you created by hand) is never deleted.
"""
from dataclasses import dataclass, field

from sqlalchemy import bindparam, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import (
    AttendanceRecord,
    Department,
    Employee,
    Role,
    Salary,
    employee_roles,
)
from scripts.generate import MasterData

CHUNK = 5000


@dataclass
class LoadSummary:
    inserted: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    def lines(self) -> list[str]:
        out = []
        for table in self.inserted:
            out.append(
                f"{table:<16} {self.inserted[table]:>6} new   {self.skipped[table]:>6} already there"
            )
        return out


def _insert_ignore(
    session: Session, model, rows: list[dict], conflict_columns: list[str], returning
) -> int:
    """Insert rows, skip the ones that already exist. Returns how many were new.

    `returning` is any column of the table: PostgreSQL only gives back the rows
    that were really inserted, so counting them tells us how many were new.
    """
    if not rows:
        return 0
    inserted = 0
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start : start + CHUNK]
        stmt = (
            pg_insert(model)
            .values(chunk)
            .on_conflict_do_nothing(index_elements=conflict_columns)
            .returning(returning)
        )
        inserted += len(session.execute(stmt).all())
    return inserted


def load_master_data(session: Session, data: MasterData) -> LoadSummary:
    summary = LoadSummary()

    def record(table: str, total: int, new: int) -> None:
        summary.inserted[table] = new
        summary.skipped[table] = total - new

    # --- departments and roles
    record(
        "departments", len(data.departments),
        _insert_ignore(session, Department, data.departments, ["name"], Department.id),
    )
    record(
        "roles", len(data.roles),
        _insert_ignore(session, Role, data.roles, ["title"], Role.id),
    )
    department_ids = dict(session.execute(select(Department.name, Department.id)).all())
    role_ids = dict(session.execute(select(Role.title, Role.id)).all())

    # --- employees (RETURNING tells us exactly which ones are new)
    rows = [
        {
            "first_name": e["first_name"],
            "last_name": e["last_name"],
            "work_email": e["work_email"],
            "phone": e["phone"],
            "hire_date": e["hire_date"],
            "is_active": e["is_active"],
            "department_id": department_ids[e["department"]],
        }
        for e in data.employees
    ]
    new_employee_ids: dict[str, int] = {}
    for start in range(0, len(rows), CHUNK):
        stmt = (
            pg_insert(Employee)
            .values(rows[start : start + CHUNK])
            .on_conflict_do_nothing(index_elements=["work_email"])
            .returning(Employee.id, Employee.work_email)
        )
        new_employee_ids.update({email: id_ for id_, email in session.execute(stmt).all()})
    record("employees", len(rows), len(new_employee_ids))

    employee_ids = dict(session.execute(select(Employee.work_email, Employee.id)).all())

    # --- managers: only for employees created in THIS run, so a manager someone
    # changed by hand is never overwritten.
    manager_updates = [
        {"b_id": new_employee_ids[e["work_email"]], "b_manager": employee_ids[e["manager_email"]]}
        for e in data.employees
        if e["manager_email"] and e["work_email"] in new_employee_ids
    ]
    if manager_updates:
        table = Employee.__table__  # plain table update: one UPDATE per employee
        session.execute(
            update(table)
            .where(table.c.id == bindparam("b_id"))
            .values(manager_id=bindparam("b_manager")),
            manager_updates,
        )

    # --- everything below is linked through employee_ids
    link_rows = [
        {"employee_id": employee_ids[r["work_email"]], "role_id": role_ids[r["role"]]}
        for r in data.employee_roles
    ]
    record(
        "employee_roles", len(link_rows),
        _insert_ignore(
            session, employee_roles, link_rows, ["employee_id", "role_id"],
            employee_roles.c.employee_id,
        ),
    )

    salary_rows = [
        {
            "employee_id": employee_ids[s["work_email"]],
            "monthly_salary": s["monthly_salary"],
            "currency": s["currency"],
            "effective_from": s["effective_from"],
        }
        for s in data.salaries
    ]
    record(
        "salaries", len(salary_rows),
        _insert_ignore(
            session, Salary, salary_rows, ["employee_id", "effective_from"], Salary.id
        ),
    )

    attendance_rows = [
        {
            "employee_id": employee_ids[a["work_email"]],
            "work_date": a["work_date"],
            "status": a["status"],
            "check_in": a["check_in"],
            "check_out": a["check_out"],
        }
        for a in data.attendance
    ]
    record(
        "attendance", len(attendance_rows),
        _insert_ignore(
            session, AttendanceRecord, attendance_rows, ["employee_id", "work_date"],
            AttendanceRecord.id,
        ),
    )
    return summary


def reset_all_tables(session: Session) -> None:
    """Delete EVERYTHING in the employee tables (children first)."""
    for model in (AttendanceRecord, Salary):
        session.execute(delete(model))
    session.execute(delete(employee_roles))
    session.execute(update(Employee).values(manager_id=None))
    for model in (Employee, Role, Department):
        session.execute(delete(model))
