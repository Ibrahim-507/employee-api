"""Export the data to CSV files:

    python -m scripts.export_csv                # writes into data/exports/
    python -m scripts.export_csv --out some/dir

Files: employees.csv, salaries.csv, attendance.csv
They are saved as UTF-8 with a BOM, so Excel opens them correctly.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from scripts import config

QUERIES = {
    "employees": """
        SELECT e.id AS employee_id,
               e.first_name, e.last_name, e.work_email, e.phone, e.hire_date,
               d.name AS department,
               (SELECT string_agg(r.title, '; ' ORDER BY r.title)
                  FROM employee_roles er JOIN roles r ON r.id = er.role_id
                 WHERE er.employee_id = e.id) AS roles,
               e.manager_id,
               m.work_email AS manager_email,
               e.is_active
          FROM employees e
          JOIN departments d ON d.id = e.department_id
          LEFT JOIN employees m ON m.id = e.manager_id
         ORDER BY e.id
    """,
    "salaries": """
        SELECT s.id AS salary_id, s.employee_id, e.work_email,
               s.monthly_salary, s.currency, s.effective_from
          FROM salaries s JOIN employees e ON e.id = s.employee_id
         ORDER BY s.employee_id, s.effective_from
    """,
    "attendance": """
        SELECT a.id AS attendance_id, a.employee_id, e.work_email,
               a.work_date, a.status, a.check_in, a.check_out
          FROM attendance_records a JOIN employees e ON e.id = a.employee_id
         ORDER BY a.work_date, a.employee_id
    """,
}


def export_all(session: Session, out_dir: Path) -> dict[str, int]:
    """Write the three CSV files. Returns how many rows each file has."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, query in QUERIES.items():
        frame = pd.read_sql_query(text(query), session.connection())
        if "manager_id" in frame.columns:   # whole numbers, empty when there is no manager
            frame["manager_id"] = frame["manager_id"].astype("Int64")
        frame.to_csv(
            out_dir / f"{name}.csv", index=False, encoding="utf-8-sig", float_format="%.2f"
        )
        counts[name] = len(frame)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.export_csv", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=config.DEFAULT_EXPORT_DIR)
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        counts = export_all(session, args.out)
    for name, rows in counts.items():
        print(f"{args.out / (name + '.csv')}: {rows} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
