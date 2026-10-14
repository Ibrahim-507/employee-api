from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.models import AttendanceRecord, Department, Employee, Role, Salary, employee_roles
from scripts.generate import build_master_data
from scripts.hr_dataset import clean_hr_dataset, load_raw
from scripts.load import load_master_data, reset_all_tables
from scripts.seed import main as seed_main

FIXTURE = Path(__file__).parent / "fixtures" / "hr_sample_for_tests.csv"


@pytest.fixture(scope="module")
def data():
    clean, _ = clean_hr_dataset(load_raw(FIXTURE))
    return build_master_data(clean, count=60, seed=42)


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def all_counts(session) -> dict:
    return {
        "departments": count(session, Department),
        "roles": count(session, Role),
        "employees": count(session, Employee),
        "employee_roles": count(session, employee_roles),
        "salaries": count(session, Salary),
        "attendance": count(session, AttendanceRecord),
    }


def test_seed_fills_an_empty_database(session, data):
    summary = load_master_data(session, data)
    counts = all_counts(session)
    assert counts == {
        "departments": len(data.departments),
        "roles": len(data.roles),
        "employees": len(data.employees),
        "employee_roles": len(data.employee_roles),
        "salaries": len(data.salaries),
        "attendance": len(data.attendance),
    }
    assert summary.inserted["employees"] == len(data.employees)
    assert all(v == 0 for v in summary.skipped.values())


def test_running_twice_creates_no_duplicates(session, data):
    load_master_data(session, data)
    before = all_counts(session)

    second = load_master_data(session, data)

    assert all_counts(session) == before
    assert all(v == 0 for v in second.inserted.values())
    assert second.skipped["employees"] == len(data.employees)


def test_data_in_the_database_is_linked(session, data):
    load_master_data(session, data)
    orphans = session.execute(text("""
        SELECT (SELECT count(*) FROM salaries s LEFT JOIN employees e ON e.id = s.employee_id
                 WHERE e.id IS NULL)
             + (SELECT count(*) FROM attendance_records a LEFT JOIN employees e ON e.id = a.employee_id
                 WHERE e.id IS NULL)
    """)).scalar()
    assert orphans == 0

    with_manager = count(session, Employee) - session.scalar(
        select(func.count()).select_from(Employee).where(Employee.manager_id.is_(None))
    )
    assert with_manager == sum(1 for e in data.employees if e["manager_email"])

    # managers are in the same department and active
    bad = session.execute(text("""
        SELECT count(*) FROM employees e JOIN employees m ON m.id = e.manager_id
         WHERE m.department_id <> e.department_id OR m.is_active = false
    """)).scalar()
    assert bad == 0


def test_existing_rows_are_never_changed_or_duplicated(session, data):
    """Someone already created a department and one employee by hand."""
    first = data.employees[0]
    dept = Department(name=first["department"], description="Created by hand")
    session.add(dept)
    session.flush()
    manual = Employee(
        first_name="Manual", last_name="Entry", work_email=first["work_email"],
        hire_date=date(2020, 1, 1), department_id=dept.id, is_active=False,
    )
    session.add(manual)
    session.flush()

    summary = load_master_data(session, data)

    assert count(session, Employee) == len(data.employees)       # no duplicate email
    assert summary.skipped["employees"] == 1
    session.refresh(manual)
    assert manual.first_name == "Manual" and manual.is_active is False
    assert manual.manager_id is None        # the manager of an existing row is left alone
    session.refresh(dept)
    assert dept.description == "Created by hand"
    names = session.scalars(select(Department.name)).all()
    assert len(names) == len(set(names))


def test_reset_deletes_everything(session, data):
    load_master_data(session, data)
    reset_all_tables(session)
    assert all(v == 0 for v in all_counts(session).values())
    load_master_data(session, data)                 # and it can be seeded again
    assert count(session, Employee) == len(data.employees)


# ------------------------------------------------------------ the command itself

def wipe(engine):
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE attendance_records, salaries, employee_roles, employees, roles, "
            "departments RESTART IDENTITY CASCADE"
        ))


def test_seed_command_twice_on_a_clean_database(engine, capsys):
    wipe(engine)
    args = ["--source", str(FIXTURE), "--count", "50"]
    try:
        assert seed_main(args) == 0
        with engine.connect() as conn:
            first = conn.execute(text(
                "SELECT (SELECT count(*) FROM employees), (SELECT count(*) FROM salaries), "
                "(SELECT count(*) FROM attendance_records)"
            )).one()
        assert first[0] == 50 and first[1] > 50 and first[2] > 1000

        assert seed_main(args) == 0
        with engine.connect() as conn:
            second = conn.execute(text(
                "SELECT (SELECT count(*) FROM employees), (SELECT count(*) FROM salaries), "
                "(SELECT count(*) FROM attendance_records)"
            )).one()
        assert tuple(second) == tuple(first)
        assert "0 new" in capsys.readouterr().out
    finally:
        wipe(engine)


def test_seed_command_with_a_missing_file_fails_clearly(capsys):
    assert seed_main(["--source", "no/such/file.csv"]) == 2
    assert "Kaggle" in capsys.readouterr().out


def test_reset_needs_confirmation(engine, capsys):
    assert seed_main(["--source", str(FIXTURE), "--reset"]) == 2
    assert "--yes" in capsys.readouterr().out
