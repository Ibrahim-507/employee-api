import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import config
from scripts.generate import build_master_data, working_days
from scripts.hr_dataset import clean_hr_dataset, load_raw

FIXTURE = Path(__file__).parent / "fixtures" / "hr_sample_for_tests.csv"


@pytest.fixture(scope="module")
def clean():
    return clean_hr_dataset(load_raw(FIXTURE))[0]


@pytest.fixture(scope="module")
def data(clean):
    return build_master_data(clean, count=100, seed=42)


# ------------------------------------------------------------ repeatable

def test_same_seed_gives_exactly_the_same_data(clean, data):
    assert build_master_data(clean, count=100, seed=42) == data


def test_different_seed_gives_different_people(clean, data):
    other = build_master_data(clean, count=100, seed=7)
    assert {e["work_email"] for e in other.employees} != {e["work_email"] for e in data.employees}


def test_count_is_respected_and_capped(clean):
    assert len(build_master_data(clean, count=40).employees) == 40
    assert len(build_master_data(clean, count=10_000).employees) == len(clean)


# ------------------------------------------------------------ believable

def test_names_emails_and_phones_look_real(data):
    forbidden = ("test", "lorem", "dummy", "sample", "asdf", "qwerty", "xxx")
    for e in data.employees:
        for name in (e["first_name"], e["last_name"]):
            assert re.fullmatch(r"[A-Za-z][A-Za-z'’ .-]*", name), name
            assert not any(w in name.lower() for w in forbidden)
        assert re.fullmatch(r"[a-z]+\.[a-z]+\d*@example\.com", e["work_email"]), e["work_email"]
        assert not any(w in e["work_email"] for w in forbidden)
        assert re.fullmatch(r"\+91 [6-9]\d{4} \d{5}", e["phone"]), e["phone"]


def test_emails_and_phones_are_unique(data):
    emails = [e["work_email"] for e in data.employees]
    phones = [e["phone"] for e in data.employees]
    assert len(set(emails)) == len(emails)
    assert len(set(phones)) == len(phones)


def test_email_domain_can_be_changed(clean):
    other = build_master_data(clean, count=20, email_domain="corp.in")
    assert all(e["work_email"].endswith("@corp.in") for e in other.employees)


def test_hire_dates_are_in_the_past(data):
    assert all(e["hire_date"] <= config.REFERENCE_DATE for e in data.employees)


def test_people_who_left_are_inactive(data):
    assert any(not e["is_active"] for e in data.employees)
    assert any(e["is_active"] for e in data.employees)


# ------------------------------------------------------------ linked

def test_every_child_row_belongs_to_a_real_employee(data):
    emails = {e["work_email"] for e in data.employees}
    for table in (data.employee_roles, data.salaries, data.attendance):
        assert table and {row["work_email"] for row in table} <= emails
    managers = {e["manager_email"] for e in data.employees if e["manager_email"]}
    assert managers <= emails


def test_departments_and_roles_cover_every_employee(data):
    departments = {d["name"] for d in data.departments}
    roles = {r["title"] for r in data.roles}
    assert {e["department"] for e in data.employees} <= departments
    assert {r["role"] for r in data.employee_roles} <= roles


def test_managers_make_a_valid_hierarchy(data):
    by_email = {e["work_email"]: e for e in data.employees}
    assert any(e["manager_email"] for e in data.employees)
    for e in data.employees:
        if not e["manager_email"]:
            continue
        boss = by_email[e["manager_email"]]
        assert boss["is_active"]
        assert boss["department"] == e["department"]
        assert boss["job_level"] > e["job_level"]
        # follow the chain upwards: it must end (no loops)
        seen, current = set(), e
        while current["manager_email"]:
            assert current["work_email"] not in seen
            seen.add(current["work_email"])
            current = by_email[current["manager_email"]]


def test_people_with_a_team_get_the_team_lead_role(data):
    managers = {e["manager_email"] for e in data.employees if e["manager_email"]}
    leads = {r["work_email"] for r in data.employee_roles if r["role"] == config.TEAM_LEAD_ROLE}
    assert leads == managers


def test_everyone_has_their_own_job_role(data):
    own = {(r["work_email"], r["role"]) for r in data.employee_roles}
    assert all((e["work_email"], e["job_role"]) in own for e in data.employees)


# ------------------------------------------------------------ salaries

def test_salary_history_is_valid(data):
    by_email = {e["work_email"]: e for e in data.employees}
    history: dict[str, list] = {}
    for s in data.salaries:
        history.setdefault(s["work_email"], []).append(s)
        assert s["monthly_salary"] > 0
        assert s["currency"] == "INR"
        assert by_email[s["work_email"]]["hire_date"] <= s["effective_from"] <= config.REFERENCE_DATE
    assert set(history) == set(by_email)            # everyone has a salary
    for rows in history.values():
        rows.sort(key=lambda r: r["effective_from"])
        amounts = [r["monthly_salary"] for r in rows]
        assert amounts == sorted(amounts)           # raises only go up
        assert len({r["effective_from"] for r in rows}) == len(rows)


def test_current_salary_comes_from_the_dataset_income(data):
    e = data.employees[0]
    latest = max(
        (s for s in data.salaries if s["work_email"] == e["work_email"]),
        key=lambda s: s["effective_from"],
    )
    expected = round(e["monthly_income"] * config.INCOME_SCALE_TO_INR / 500) * 500
    assert latest["monthly_salary"] == expected


# ------------------------------------------------------------ attendance

def test_attendance_follows_the_rules(data):
    by_email = {e["work_email"]: e for e in data.employees}
    weekdays = set(working_days(config.ATTENDANCE_START, config.ATTENDANCE_END))
    seen = set()
    for a in data.attendance:
        e = by_email[a["work_email"]]
        assert e["is_active"]                                  # people who left have none
        assert a["work_date"] in weekdays                      # no weekends, inside the period
        assert a["work_date"] >= e["hire_date"]                # not before they joined
        assert a["status"] in {"present", "absent", "on_leave", "half_day"}
        key = (a["work_email"], a["work_date"])
        assert key not in seen                                 # one record per person per day
        seen.add(key)
        if a["status"] in ("present", "half_day"):
            assert a["check_in"] and a["check_out"] and a["check_out"] > a["check_in"]
        else:
            assert a["check_in"] is None and a["check_out"] is None


def test_attendance_has_a_believable_mix(data):
    counts = Counter(a["status"] for a in data.attendance)
    total = sum(counts.values())
    assert counts["present"] / total > 0.8
    assert counts["on_leave"] > 0 and counts["half_day"] > 0 and counts["absent"] > 0


def test_working_days_skips_weekends():
    days = working_days(config.ATTENDANCE_START, config.ATTENDANCE_START + timedelta(days=13))
    assert len(days) == 10 and all(d.weekday() < 5 for d in days)
