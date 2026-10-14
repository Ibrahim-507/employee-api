import csv
from pathlib import Path

import pytest

from scripts.export_csv import export_all
from scripts.generate import build_master_data
from scripts.hr_dataset import clean_hr_dataset, load_raw
from scripts.load import load_master_data

FIXTURE = Path(__file__).parent / "fixtures" / "hr_sample_for_tests.csv"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def exported(session, tmp_path):
    clean, _ = clean_hr_dataset(load_raw(FIXTURE))
    data = build_master_data(clean, count=60, seed=42)
    load_master_data(session, data)
    counts = export_all(session, tmp_path)
    return data, counts, tmp_path


def test_three_files_with_the_right_number_of_rows(exported):
    data, counts, out = exported
    assert counts == {
        "employees": len(data.employees),
        "salaries": len(data.salaries),
        "attendance": len(data.attendance),
    }
    for name, rows in counts.items():
        assert len(read_csv(out / f"{name}.csv")) == rows


def test_files_open_in_excel(exported):
    _, _, out = exported
    for name in ("employees", "salaries", "attendance"):
        assert (out / f"{name}.csv").read_bytes().startswith(b"\xef\xbb\xbf")  # UTF-8 BOM


def test_headers(exported):
    _, _, out = exported
    assert list(read_csv(out / "employees.csv")[0]) == [
        "employee_id", "first_name", "last_name", "work_email", "phone", "hire_date",
        "department", "roles", "manager_id", "manager_email", "is_active",
    ]
    assert list(read_csv(out / "salaries.csv")[0]) == [
        "salary_id", "employee_id", "work_email", "monthly_salary", "currency", "effective_from",
    ]
    assert list(read_csv(out / "attendance.csv")[0]) == [
        "attendance_id", "employee_id", "work_email", "work_date", "status", "check_in", "check_out",
    ]


def test_ids_are_whole_numbers_and_files_link_up(exported):
    _, _, out = exported
    employees = read_csv(out / "employees.csv")
    ids = {r["employee_id"] for r in employees}
    assert all(i.isdigit() for i in ids)
    assert all(r["manager_id"] == "" or r["manager_id"] in ids for r in employees)  # no "12.0"
    for name in ("salaries", "attendance"):
        assert {r["employee_id"] for r in read_csv(out / f"{name}.csv")} <= ids
    # employee_id and work_email agree between files
    email_of = {r["employee_id"]: r["work_email"] for r in employees}
    for r in read_csv(out / "attendance.csv")[:200]:
        assert email_of[r["employee_id"]] == r["work_email"]


def test_values_are_formatted_for_people(exported):
    _, _, out = exported
    salary = read_csv(out / "salaries.csv")[0]
    assert salary["monthly_salary"].count(".") == 1 and len(salary["monthly_salary"].split(".")[1]) == 2
    assert salary["currency"] == "INR"
    emp = read_csv(out / "employees.csv")[0]
    assert emp["is_active"] in ("True", "False")
    assert len(emp["hire_date"]) == 10                       # 2020-01-31
    row = next(r for r in read_csv(out / "attendance.csv") if r["status"] == "present")
    assert len(row["check_in"]) == 8                         # 09:05:00


def test_export_creates_the_folder(session, tmp_path):
    target = tmp_path / "new" / "folder"
    export_all(session, target)
    assert (target / "employees.csv").exists()
