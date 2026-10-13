from datetime import date

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import Department, Employee, Role
from app.services.hierarchy_service import get_all_reports


def make_department(session, name="Engineering") -> Department:
    dept = Department(name=name)
    session.add(dept)
    session.flush()
    return dept


def make_employee(session, dept, email, manager=None, first="Test", last="User"):
    emp = Employee(
        first_name=first,
        last_name=last,
        work_email=email,
        hire_date=date(2024, 1, 15),
        department=dept,
        manager=manager,
    )
    session.add(emp)
    session.flush()
    return emp


# ---------- constraints ----------

def test_duplicate_work_email_fails(session):
    dept = make_department(session)
    make_employee(session, dept, "same@example.com")
    with pytest.raises(IntegrityError):
        make_employee(session, dept, "same@example.com")
    session.rollback()


def test_work_email_is_required(session):
    dept = make_department(session)
    session.add(
        Employee(
            first_name="No",
            last_name="Email",
            hire_date=date(2024, 1, 1),
            department=dept,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_employee_must_have_a_department(session):
    session.add(
        Employee(
            first_name="No",
            last_name="Dept",
            work_email="nodept@example.com",
            hire_date=date(2024, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_duplicate_department_name_fails(session):
    make_department(session, "HR")
    with pytest.raises(IntegrityError):
        make_department(session, "HR")
    session.rollback()


def test_duplicate_role_title_fails(session):
    session.add(Role(title="Developer"))
    session.flush()
    session.add(Role(title="Developer"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_employee_cannot_be_own_manager(session):
    dept = make_department(session)
    emp = make_employee(session, dept, "solo@example.com")
    emp.manager_id = emp.id
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_department_with_employees_cannot_be_deleted(session):
    dept = make_department(session)
    make_employee(session, dept, "stay@example.com")
    session.delete(dept)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# ---------- defaults / soft delete ----------

def test_defaults_and_timestamps(session):
    dept = make_department(session)
    emp = make_employee(session, dept, "defaults@example.com")
    session.refresh(emp)
    assert emp.is_active is True
    assert emp.created_at is not None
    assert emp.updated_at is not None


def test_soft_delete_keeps_the_row(session):
    dept = make_department(session)
    emp = make_employee(session, dept, "leaver@example.com")
    emp.is_active = False
    session.flush()
    found = session.scalar(
        select(Employee).where(Employee.work_email == "leaver@example.com")
    )
    assert found is not None
    assert found.is_active is False


# ---------- relationships ----------

def test_department_has_many_employees(session):
    dept = make_department(session)
    a = make_employee(session, dept, "a@example.com")
    b = make_employee(session, dept, "b@example.com")
    session.refresh(dept)
    assert {e.id for e in dept.employees} == {a.id, b.id}


def test_employee_can_have_many_roles(session):
    dept = make_department(session)
    emp = make_employee(session, dept, "multi@example.com")
    dev = Role(title="Developer")
    lead = Role(title="Team Lead")
    emp.roles.extend([dev, lead])
    session.flush()
    session.refresh(emp)
    assert {r.title for r in emp.roles} == {"Developer", "Team Lead"}
    assert emp in dev.employees


# ---------- manager hierarchy ----------

def test_manager_hierarchy(session):
    dept = make_department(session)
    ceo = make_employee(session, dept, "ceo@example.com")
    manager = make_employee(session, dept, "mgr@example.com", manager=ceo)
    dev1 = make_employee(session, dept, "dev1@example.com", manager=manager)
    dev2 = make_employee(session, dept, "dev2@example.com", manager=manager)
    session.refresh(manager)

    assert ceo.manager is None
    assert dev1.manager.manager is ceo
    assert {e.id for e in manager.direct_reports} == {dev1.id, dev2.id}


def test_get_all_reports_walks_the_whole_tree(session):
    dept = make_department(session)
    ceo = make_employee(session, dept, "ceo@example.com")
    manager = make_employee(session, dept, "mgr@example.com", manager=ceo)
    dev = make_employee(session, dept, "dev@example.com", manager=manager)
    outsider = make_employee(session, dept, "other@example.com")

    ids = {e.id for e in get_all_reports(session, ceo.id)}
    assert ids == {manager.id, dev.id}
    assert outsider.id not in ids
    assert get_all_reports(session, dev.id) == []


# ---------- indexes ----------

def test_search_indexes_exist(engine):
    names = {ix["name"] for ix in inspect(engine).get_indexes("employees")}
    assert "ix_employees_name" in names
    assert "ix_employees_department_id" in names
    assert "ix_employees_manager_id" in names
