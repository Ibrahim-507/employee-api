# ER diagram: employees, departments, roles

GitHub draws this diagram automatically when you open this file.

```mermaid
erDiagram
    DEPARTMENTS ||--o{ EMPLOYEES : "has"
    EMPLOYEES   ||--o{ EMPLOYEES : "manages (manager_id)"
    EMPLOYEES   ||--o{ EMPLOYEE_ROLES : "holds"
    ROLES       ||--o{ EMPLOYEE_ROLES : "given to"
    EMPLOYEES   ||--o{ SALARIES : "is paid"
    EMPLOYEES   ||--o{ ATTENDANCE_RECORDS : "has"

    DEPARTMENTS {
        int id PK
        string name UK "required, unique"
        text description
        bool is_active "soft delete"
        timestamptz created_at
        timestamptz updated_at
    }

    ROLES {
        int id PK
        string title UK "required, unique"
        text description
        timestamptz created_at
        timestamptz updated_at
    }

    EMPLOYEES {
        int id PK
        string first_name "required"
        string last_name "required"
        string work_email UK "required, unique"
        string phone
        date hire_date "required"
        bool is_active "soft delete"
        int department_id FK "required"
        int manager_id FK "nullable, points to employees.id"
        timestamptz created_at
        timestamptz updated_at
    }

    SALARIES {
        int id PK
        int employee_id FK "required"
        numeric monthly_salary "must be > 0"
        string currency "default INR"
        date effective_from "unique per employee"
        timestamptz created_at
        timestamptz updated_at
    }

    ATTENDANCE_RECORDS {
        int id PK
        int employee_id FK "required"
        date work_date "unique per employee"
        string status "present, absent, on_leave, half_day"
        time check_in
        time check_out "must be after check_in"
        timestamptz created_at
        timestamptz updated_at
    }

    EMPLOYEE_ROLES {
        int employee_id PK, FK
        int role_id PK, FK
        timestamptz assigned_at
    }
```

## Rules enforced by the database

| Rule | How |
|---|---|
| Work email is unique and required | `UNIQUE` + `NOT NULL` on `employees.work_email` |
| Department names and role titles are unique | `UNIQUE` constraints |
| Every employee belongs to a department | `department_id NOT NULL` + foreign key |
| A department with employees cannot be hard-deleted | `ON DELETE RESTRICT` |
| Nobody is their own manager | `CHECK (manager_id <> id)` |
| A manager row that is hard-deleted does not delete their team | `ON DELETE SET NULL` on `manager_id` |
| The same role cannot be given twice to one person | composite primary key `(employee_id, role_id)` |
| An employee has one salary row per effective date | unique `(employee_id, effective_from)`, `monthly_salary > 0` |
| One attendance record per employee per day | unique `(employee_id, work_date)`; status limited to 4 values; check-out after check-in |
| Salary and attendance rows disappear if the employee row is hard-deleted | `ON DELETE CASCADE` |
| Searching by name or department is fast | indexes `ix_employees_name`, `ix_employees_department_id`, `ix_employees_manager_id` |
