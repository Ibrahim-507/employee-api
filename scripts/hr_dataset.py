"""Step 1: read the Kaggle HR file and clean it with pandas."""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from scripts.config import DEPARTMENT_MAP


class DatasetError(Exception):
    """The input file is missing or not the dataset we expect."""


# Columns we need from the Kaggle file. Everything else is ignored.
REQUIRED_COLUMNS = [
    "Age", "Attrition", "Department", "Gender", "JobLevel", "JobRole",
    "MonthlyIncome", "OverTime", "YearsAtCompany",
]
# Columns that identify a row or never change. We never keep them.
DROPPED_IDENTIFIER_COLUMNS = ["EmployeeNumber", "EmployeeCount", "Over18", "StandardHours"]

RENAME = {
    "Age": "age", "Attrition": "attrition", "Department": "department",
    "Gender": "gender", "JobLevel": "job_level", "JobRole": "job_role",
    "MonthlyIncome": "monthly_income", "OverTime": "overtime",
    "YearsAtCompany": "years_at_company",
}
NUMBER_COLUMNS = ["Age", "JobLevel", "MonthlyIncome", "YearsAtCompany"]
TEXT_COLUMNS = ["Attrition", "Department", "Gender", "JobRole", "OverTime"]


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    duplicates_removed: int = 0
    missing_values_removed: int = 0
    invalid_rows_removed: int = 0
    years_clamped: int = 0
    dropped_columns: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [
            f"rows read:               {self.rows_in}",
            f"duplicates removed:      {self.duplicates_removed}",
            f"rows with missing data:  {self.missing_values_removed}",
            f"rows with invalid data:  {self.invalid_rows_removed}",
            f"tenure fixed (age rule): {self.years_clamped}",
            f"identifier columns dropped: {', '.join(self.dropped_columns) or 'none'}",
            f"rows kept:               {self.rows_out}",
        ]


def load_raw(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise DatasetError(
            f"Dataset file not found: {path}\n"
            "Download 'IBM HR Analytics Employee Attrition & Performance' from Kaggle\n"
            "and save the CSV there. Steps are in docs/dataset.md."
        )
    try:
        return pd.read_csv(path)
    except Exception as exc:  # unreadable or not a CSV
        raise DatasetError(f"Could not read {path} as a CSV file: {exc}") from exc


def clean_hr_dataset(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Return (clean table, report). The input table is not changed."""
    report = CleaningReport(rows_in=len(raw))

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise DatasetError(
            "This file does not look like the IBM HR dataset. "
            f"Missing columns: {', '.join(missing)}"
        )

    df = raw.copy()
    report.dropped_columns = [c for c in DROPPED_IDENTIFIER_COLUMNS if c in df.columns]

    # Same person data repeated in another row (ignoring the row number)?
    before = len(df)
    df = df.drop_duplicates(subset=[c for c in df.columns if c != "EmployeeNumber"])
    report.duplicates_removed = before - len(df)

    # Keep only the columns we use: identifiers and constant columns disappear here.
    df = df[REQUIRED_COLUMNS].copy()

    for col in TEXT_COLUMNS:
        df[col] = df[col].astype("string").str.strip()
        df[col] = df[col].replace("", pd.NA)
    for col in NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before = len(df)
    df = df.dropna()
    report.missing_values_removed = before - len(df)

    valid = (
        df["Age"].between(18, 65)
        & df["JobLevel"].between(1, 5)
        & (df["MonthlyIncome"] > 0)
        & (df["YearsAtCompany"] >= 0)
        & df["Gender"].isin(["Male", "Female"])
        & df["Attrition"].isin(["Yes", "No"])
        & df["OverTime"].isin(["Yes", "No"])
        & df["Department"].isin(DEPARTMENT_MAP)
    )
    report.invalid_rows_removed = int((~valid).sum())
    df = df[valid].copy()

    # Nobody can have worked longer than (age - 18) years.
    max_years = df["Age"] - 18
    too_long = df["YearsAtCompany"] > max_years
    report.years_clamped = int(too_long.sum())
    df.loc[too_long, "YearsAtCompany"] = max_years[too_long]

    for col in ("Age", "JobLevel", "MonthlyIncome", "YearsAtCompany"):
        df[col] = df[col].astype(int)
    df = df.rename(columns=RENAME)
    df["attrition"] = (df["attrition"] == "Yes").astype(bool)
    df["overtime"] = (df["overtime"] == "Yes").astype(bool)
    df["department"] = df["department"].map(DEPARTMENT_MAP)
    df = df.astype({"gender": str, "job_role": str, "department": str})
    df = df.reset_index(drop=True)

    report.rows_out = len(df)
    if df.empty:
        raise DatasetError("No usable rows are left after cleaning.")
    return df, report
