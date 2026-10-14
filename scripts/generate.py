"""Step 2: turn the clean table into linked fake records (no database here).

Everything is created from one seed, so the same seed always gives the same data.
Every row refers to an employee by work email, which is how rows stay linked.
"""
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pandas as pd
from faker import Faker

from scripts import config


@dataclass
class MasterData:
    departments: list[dict] = field(default_factory=list)
    roles: list[dict] = field(default_factory=list)
    employees: list[dict] = field(default_factory=list)
    employee_roles: list[dict] = field(default_factory=list)   # {work_email, role}
    salaries: list[dict] = field(default_factory=list)         # {work_email, ...}
    attendance: list[dict] = field(default_factory=list)       # {work_email, ...}


def _email_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def working_days(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:  # Monday to Friday
            days.append(day)
        day += timedelta(days=1)
    return days


def _make_people(df: pd.DataFrame, rng: random.Random, fake: Faker, domain: str) -> list[dict]:
    people, used_emails, used_phones = [], set(), set()
    for row in df.itertuples(index=False):
        first = fake.first_name_female() if row.gender == "Female" else fake.first_name_male()
        last = fake.last_name()

        base = f"{_email_name(first)}.{_email_name(last)}"
        email, n = f"{base}@{domain}", 1
        while email in used_emails:  # two people with the same name
            n += 1
            email = f"{base}{n}@{domain}"
        used_emails.add(email)

        while True:
            phone = (
                f"+91 {rng.choice('6789')}{fake.numerify('####')} {fake.numerify('#####')}"
            )
            if phone not in used_phones:
                used_phones.add(phone)
                break

        hire_date = config.REFERENCE_DATE - timedelta(
            days=int(row.years_at_company) * 365 + rng.randint(0, 364)
        )
        people.append(
            {
                "first_name": first,
                "last_name": last,
                "work_email": email,
                "phone": phone,
                "hire_date": hire_date,
                "department": row.department,
                "job_role": row.job_role,
                "job_level": int(row.job_level),
                "is_active": not bool(row.attrition),   # people who left are inactive
                "monthly_income": int(row.monthly_income),
                "years_at_company": int(row.years_at_company),
                "overtime": bool(row.overtime),
                "manager_email": None,
            }
        )
    return people


def _assign_managers(people: list[dict], rng: random.Random) -> None:
    """Level-N people report to someone active, one level up, in their department.

    A manager always has a higher job level, so loops are impossible.
    """
    for person in people:
        candidates = [
            p for p in people
            if p["is_active"]
            and p["department"] == person["department"]
            and p["job_level"] > person["job_level"]
        ]
        if not candidates:
            continue  # top of the department: no manager
        next_level = min(p["job_level"] for p in candidates)
        pool = [p for p in candidates if p["job_level"] == next_level]
        person["manager_email"] = rng.choice(pool)["work_email"]


def _make_salaries(people: list[dict], rng: random.Random) -> list[dict]:
    rows = []
    for p in people:
        current = _round_to(p["monthly_income"] * config.INCOME_SCALE_TO_INR, config.SALARY_ROUNDING)
        revisions = p["years_at_company"]               # one raise per work anniversary
        raises = [rng.uniform(1.06, 1.12) for _ in range(revisions)]
        amounts = [current]
        for r in reversed(raises):                      # walk back to the starting salary
            amounts.append(_round_to(amounts[-1] / r, 100))
        amounts.reverse()                               # oldest first
        for i, amount in enumerate(amounts):
            rows.append(
                {
                    "work_email": p["work_email"],
                    "monthly_salary": Decimal(amount).quantize(Decimal("0.01")),
                    "currency": config.CURRENCY,
                    "effective_from": p["hire_date"] + timedelta(days=365 * i),
                }
            )
    return rows


def _make_attendance(people: list[dict], rng: random.Random) -> list[dict]:
    """Only people who still work here get attendance, and only after they joined."""
    days = working_days(config.ATTENDANCE_START, config.ATTENDANCE_END)
    rows = []
    for p in people:
        if not p["is_active"]:
            continue
        leave_days_left = 0
        for day in days:
            if day < p["hire_date"]:
                continue
            if leave_days_left == 0 and rng.random() < 0.02:   # a leave starts
                leave_days_left = rng.randint(1, 3)
            if leave_days_left > 0:
                leave_days_left -= 1
                rows.append(_attendance_row(p, day, "on_leave", None, None))
                continue
            roll = rng.random()
            if roll < 0.015:
                rows.append(_attendance_row(p, day, "absent", None, None))
                continue
            in_minutes = int(min(max(rng.gauss(9 * 60, 20), 8 * 60 + 15), 10 * 60 + 30))
            check_in = datetime.combine(day, time(in_minutes // 60, in_minutes % 60))
            if roll < 0.055:                                    # half day
                check_out = check_in + timedelta(hours=rng.uniform(4, 5))
                status = "half_day"
            else:
                hours = rng.uniform(8.5, 9.5)
                if p["overtime"] and rng.random() < 0.5:
                    hours += rng.uniform(1, 2)
                check_out = check_in + timedelta(hours=hours)
                status = "present"
            rows.append(
                _attendance_row(
                    p, day, status,
                    check_in.time().replace(second=0, microsecond=0),
                    check_out.time().replace(second=0, microsecond=0),
                )
            )
    return rows


def _attendance_row(p: dict, day: date, status: str, check_in, check_out) -> dict:
    return {
        "work_email": p["work_email"],
        "work_date": day,
        "status": status,
        "check_in": check_in,
        "check_out": check_out,
    }


def build_master_data(
    clean: pd.DataFrame,
    *,
    count: int = config.DEFAULT_COUNT,
    seed: int = config.DEFAULT_SEED,
    email_domain: str = config.DEFAULT_EMAIL_DOMAIN,
) -> MasterData:
    """Pure function: same inputs always give exactly the same output."""
    sample = clean.sample(n=min(count, len(clean)), random_state=seed)
    sample = sample.sort_values(["department", "job_level", "job_role"], kind="stable")
    sample = sample.reset_index(drop=True)

    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    people = _make_people(sample, rng, fake, email_domain)
    _assign_managers(people, rng)

    data = MasterData()
    data.departments = [{"name": name} for name in sorted({p["department"] for p in people})]
    role_titles = sorted({p["job_role"] for p in people})
    managers = {p["manager_email"] for p in people if p["manager_email"]}
    if managers and config.TEAM_LEAD_ROLE not in role_titles:
        role_titles.append(config.TEAM_LEAD_ROLE)
    data.roles = [{"title": t} for t in role_titles]
    data.employees = people
    for p in people:
        data.employee_roles.append({"work_email": p["work_email"], "role": p["job_role"]})
        if p["work_email"] in managers:
            data.employee_roles.append(
                {"work_email": p["work_email"], "role": config.TEAM_LEAD_ROLE}
            )
    data.salaries = _make_salaries(people, rng)
    data.attendance = _make_attendance(people, rng)
    return data
