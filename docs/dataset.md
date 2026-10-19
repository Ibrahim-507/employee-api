# Master dataset: source, cleaning, generation, exports

This is the shared dataset for all domains (Full Stack, AI/ML, Data, Payroll and others).
Everyone gets exactly the same data by running one command.

## 1. Source dataset (Kaggle)

| | |
|---|---|
| Name | IBM HR Analytics Employee Attrition & Performance |
| Page | https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset |
| File | `WA_Fn-UseC_-HR-Employee-Attrition.csv` (1,470 rows, 35 columns) |
| Nature | A **fictional** dataset made by IBM data scientists. It contains no real people. |
| License | As shown on the Kaggle page (checked 14 Oct 2026): Database: Open Database License (ODbL) v1.0, https://opendatacommons.org/licenses/odbl/1-0/ ; Contents: Database Contents License (DbCL) v1.0, https://opendatacommons.org/licenses/dbcl/1-0/ . The raw file is not re-hosted in this repository; download it from the Kaggle page above. |

**How to get it**

1. Log in at kaggle.com, open the page above, and click **Download**.
2. Unzip it and save the CSV as `data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv`.
   The file is ignored by Git on purpose (see `.gitignore`).

## 2. What we take from it, and what we clean

We use 9 of its 35 columns: `Age, Attrition, Department, Gender, JobLevel, JobRole,
MonthlyIncome, OverTime, YearsAtCompany`.

| Cleaning step | Why |
|---|---|
| Drop `EmployeeNumber`, `EmployeeCount`, `Over18`, `StandardHours` | Row identifiers and constant columns |
| Remove duplicate rows (ignoring the row number) | Same person twice |
| Trim text, convert numbers, remove rows with missing values | Clean types |
| Remove invalid rows: age outside 18-65, job level outside 1-5, income <= 0, unknown gender/department, bad Yes/No values | Bad data |
| Fix tenure that is longer than (age - 18) | Nobody works before 18 |
| Rename columns to `snake_case`; `Attrition` and `OverTime` become true/false | Easy to use |

The command prints a cleaning report every time it runs.

**Mapping to our tables**

| Dataset | Our table |
|---|---|
| `Department` (Research & Development, Sales, Human Resources) | `departments.name` (same names) |
| `JobRole` (for example Sales Executive, Research Scientist) | `roles.title`, linked through `employee_roles` |
| `JobLevel` | Used to build the manager hierarchy (not stored) |
| `Attrition = Yes` | `employees.is_active = false` |
| `MonthlyIncome` | `salaries.monthly_salary` (see below) |
| `YearsAtCompany` | Decides `employees.hire_date` |
| `Gender` | Decides whether Faker picks a female or male first name (not stored) |
| `OverTime` | Later check-out times in attendance (not stored) |

## 3. What Faker generates (fixed seed)

Seed **42**, 300 employees by default. Same seed gives identical data on every machine.

- **Names:** Indian names (Faker `en_IN`), matching the dataset's gender.
- **Work email:** `first.last@example.com`. `example.com` is a domain reserved for examples,
  so no real person can receive these emails. A number is added if two people share a name.
- **Phone:** `+91 XXXXX XXXXX`, unique.
- **Hire date:** counted back from the fixed date **2026-09-30**, using `YearsAtCompany`.
- **Manager:** a person reports to an active person one job level higher in the same
  department. People with a team also get the extra role `Team Lead`.
- **Salary:** the dataset's `MonthlyIncome` times 20 (only to make the amounts look like
  Indian salaries, **not an exchange rate**), rounded to 500, in INR. History: one row at the
  hire date and one raise (6 to 12 percent) on each work anniversary.
- **Attendance:** every weekday from 2026-07-01 to 2026-09-30, only for active employees, and
  only from their hire date. About 91 percent present, plus leave blocks of 1 to 3 days, half
  days and a few absences. People marked with overtime check out later.

## 4. Linking rules

Every salary and attendance row has an `employee_id` that points to a real employee
(foreign key). The database also enforces one salary per employee per effective date, one
attendance row per employee per day, and no negative salaries.

## 5. Commands

Run these inside the `api` container (with `docker compose up` running):

```bash
docker compose exec api alembic upgrade head      # create the tables (once)
docker compose exec api python -m scripts.seed    # fill the database
docker compose exec api python -m scripts.export_csv   # write the CSV files
```

Seed options: `--count 300`, `--seed 42`, `--source path/to/file.csv`,
`--email-domain example.com`, and `--reset --yes` (deletes all employee data first).

**Running the seed twice is safe.** Each row is inserted with "do nothing if it already
exists", using these keys: department name, role title, work email, (employee, role),
(employee, effective date) and (employee, work date). Existing rows are never changed or
duplicated, and nothing is deleted unless you use `--reset --yes`.
The whole seed runs in one transaction: it completes fully or saves nothing.

## 6. CSV files (`data/exports/`)

All files are UTF-8 with a BOM, so Excel opens them correctly.

**employees.csv:** `employee_id, first_name, last_name, work_email, phone, hire_date,
department, roles, manager_id, manager_email, is_active` (several roles are joined with `; `)

**salaries.csv:** `salary_id, employee_id, work_email, monthly_salary, currency, effective_from`

**attendance.csv:** `attendance_id, employee_id, work_email, work_date, status, check_in, check_out`
(`status` is one of `present`, `absent`, `on_leave`, `half_day`)

Join the files on `employee_id`.
