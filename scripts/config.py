"""Settings for the seed pipeline. Change them here, not inside the logic."""
from datetime import date
from pathlib import Path

# The Kaggle file this pipeline expects (see docs/dataset.md).
DEFAULT_SOURCE = Path("data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv")
DEFAULT_EXPORT_DIR = Path("data/exports")

DEFAULT_SEED = 42
DEFAULT_COUNT = 300
DEFAULT_EMAIL_DOMAIN = "example.com"  # reserved by RFC 2606: no real person owns it

# "Today" for the generated data. It is FIXED so everyone gets identical data
# no matter which day they run the seed.
REFERENCE_DATE = date(2026, 9, 30)
ATTENDANCE_START = date(2026, 7, 1)   # attendance covers Jul, Aug, Sep 2026
ATTENDANCE_END = REFERENCE_DATE

# The dataset's MonthlyIncome is in dollars. We multiply by a fixed factor so
# salaries look like Indian monthly salaries. This is NOT a market exchange rate.
INCOME_SCALE_TO_INR = 20
SALARY_ROUNDING = 500
CURRENCY = "INR"

# dataset department  ->  department name in OUR departments table
DEPARTMENT_MAP = {
    "Research & Development": "Research & Development",
    "Sales": "Sales",
    "Human Resources": "Human Resources",
}

# Extra role given to every person who has direct reports (shows many roles per person).
TEAM_LEAD_ROLE = "Team Lead"
