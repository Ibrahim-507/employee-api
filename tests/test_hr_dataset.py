from pathlib import Path

import pandas as pd
import pytest

from scripts.hr_dataset import DatasetError, clean_hr_dataset, load_raw

FIXTURE = Path(__file__).parent / "fixtures" / "hr_sample_for_tests.csv"


def raw() -> pd.DataFrame:
    return pd.read_csv(FIXTURE)


def test_clean_fixture_keeps_every_row_and_drops_identifiers():
    clean, report = clean_hr_dataset(raw())
    assert report.rows_in == report.rows_out == len(clean) == 150
    assert report.dropped_columns == ["EmployeeNumber", "EmployeeCount", "Over18", "StandardHours"]
    assert list(clean.columns) == [
        "age", "attrition", "department", "gender", "job_level", "job_role",
        "monthly_income", "overtime", "years_at_company",
    ]
    assert clean["attrition"].dtype == bool and clean["overtime"].dtype == bool


def test_departments_are_mapped_to_our_department_names():
    clean, _ = clean_hr_dataset(raw())
    assert set(clean["department"]) <= {"Research & Development", "Sales", "Human Resources"}


def test_duplicates_are_removed_even_with_a_different_row_number():
    df = raw()
    copy = df.iloc[[0]].copy()
    copy["EmployeeNumber"] = 99999
    clean, report = clean_hr_dataset(pd.concat([df, copy], ignore_index=True))
    assert report.duplicates_removed == 1
    assert len(clean) == 150


def test_rows_with_missing_values_are_removed():
    df = raw()
    df.loc[3, "Department"] = None
    df.loc[4, "MonthlyIncome"] = None
    clean, report = clean_hr_dataset(df)
    assert report.missing_values_removed == 2
    assert len(clean) == 148


@pytest.mark.parametrize(
    "column, bad_value",
    [
        ("MonthlyIncome", -5),
        ("MonthlyIncome", 0),
        ("Age", 15),
        ("Age", 99),
        ("JobLevel", 9),
        ("Gender", "Other"),
        ("Attrition", "Maybe"),
        ("Department", "Space Travel"),
    ],
)
def test_invalid_rows_are_removed(column, bad_value):
    df = raw()
    df.loc[0, column] = bad_value
    clean, report = clean_hr_dataset(df)
    assert report.invalid_rows_removed == 1
    assert len(clean) == 149


def test_text_is_trimmed():
    df = raw()
    df.loc[0, "Department"] = "  Sales  "
    clean, report = clean_hr_dataset(df)
    assert report.invalid_rows_removed == 0
    assert len(clean) == 150


def test_tenure_cannot_be_longer_than_working_life():
    df = raw()
    df.loc[0, ["Age", "YearsAtCompany"]] = [20, 10]
    clean, report = clean_hr_dataset(df)
    assert report.years_clamped == 1
    assert (clean["years_at_company"] <= clean["age"] - 18).all()


def test_does_not_change_the_input_table():
    df = raw()
    before = df.copy()
    clean_hr_dataset(df)
    pd.testing.assert_frame_equal(df, before)


def test_wrong_file_is_rejected_with_a_clear_message():
    with pytest.raises(DatasetError, match="Missing columns"):
        clean_hr_dataset(pd.DataFrame({"Name": ["a"], "Salary": [1]}))


def test_everything_invalid_is_an_error():
    df = raw()
    df["MonthlyIncome"] = -1
    with pytest.raises(DatasetError, match="No usable rows"):
        clean_hr_dataset(df)


def test_missing_file_tells_the_user_how_to_get_it(tmp_path):
    with pytest.raises(DatasetError, match="Kaggle"):
        load_raw(tmp_path / "nope.csv")
