# Employee API: Contract (v0.2, still a draft)

Base URL (local): `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`
Machine-readable contract: `docs/openapi.json` (generated from the code)
Format: JSON. Dates are `YYYY-MM-DD`. Timestamps are ISO 8601 in UTC.

> **Changed since v0.1:** the error format is now `{"error": {...}}` (see "Errors"),
> list endpoints return a page object, and `POST /departments` was added.
> `PUT /employees/{id}` was replaced by `PATCH` (send only the fields to change).

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/health` | Service is running | 200 `{"status": "ok"}` |
| POST | `/employees` | Create an employee | 201 `Employee` |
| GET | `/employees` | List employees (paged, filter, search) | 200 `Page<Employee>` |
| GET | `/employees/{id}` | One employee (inactive ones too) | 200 `Employee` |
| PATCH | `/employees/{id}` | Change some fields | 200 `Employee` |
| DELETE | `/employees/{id}` | Soft delete (`is_active` becomes false) | 204 no body |
| GET | `/employees/{id}/team` | Direct reports of this employee | 200 `[Employee]` |
| GET | `/departments` | All departments with active employee counts | 200 `[Department]` |
| POST | `/departments` | Create a department | 201 `Department` |
| GET | `/departments/{id}/employees` | Employees of one department (paged) | 200 `Page<Employee>` |

### List query parameters (`/employees` and `/departments/{id}/employees`)

| Parameter | Default | Meaning |
|---|---|---|
| `page` | 1 | Page number, starts at 1 |
| `size` | 20 | Items per page, 1 to 100 |
| `q` | none | Search in first name, last name, full name and email (not case sensitive, partial match) |
| `department` | none | Department **name**, not case sensitive (`/employees` only) |
| `include_inactive` | false | Also return deactivated employees |

All filters combine: `?department=Engineering&q=ar&page=2&size=10`.
Results are sorted by last name, then first name.

## Objects

**Employee** (response)

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `first_name`, `last_name` | string | |
| `work_email` | string | Always lowercase, unique |
| `phone` | string or null | |
| `hire_date` | date | |
| `is_active` | boolean | false after DELETE |
| `department` | `{id, name}` | |
| `manager_id` | integer or null | |
| `created_at`, `updated_at` | datetime | |

**EmployeeCreate** (POST body): `first_name`, `last_name`, `work_email`, `hire_date`,
`department_id` are required. `phone` and `manager_id` are optional.

**EmployeeUpdate** (PATCH body): any of `first_name`, `last_name`, `work_email`, `phone`,
`hire_date`, `department_id`, `manager_id`, `is_active`. Send `"manager_id": null` to remove
the manager. Other fields cannot be null.

**Page<Employee>**

```json
{"items": [Employee], "total": 57, "page": 1, "size": 20, "pages": 3}
```

`total` counts all rows that match the filters, not just this page.

**Department**: `id`, `name`, `description`, `is_active`, `employee_count` (active employees).
**DepartmentCreate**: `name` (required, unique ignoring case), `description` (optional).

## Validation rules

- `work_email` must be a valid email. It is stored in lowercase and must be unique.
- `first_name` and `last_name` must not be empty. Spaces at the ends are trimmed.
- `hire_date` must not be in the future.
- `department_id` must be an existing, active department.
- `manager_id` must be an existing, active employee. Nobody can be their own manager,
  and a manager cannot be set to someone who already reports to that employee (no loops).
- Unknown fields in the body are rejected.
- An employee with active direct reports cannot be deleted. Give the reports a new manager first.

## Errors

Every error uses the same shape:

```json
{"error": {"code": "not_found", "message": "Employee 5 not found", "details": null}}
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `not_found` | Unknown id or unknown URL |
| 405 | `method_not_allowed` | Wrong HTTP method for the URL |
| 409 | `email_already_exists` | Email is taken |
| 409 | `department_name_exists` | Department name is taken |
| 409 | `has_active_reports` | Deleting a manager who still has active reports |
| 422 | `validation_error` | Bad input. `details` lists each problem as `{field, in, message}` |
| 422 | `invalid_reference` | `department_id` or `manager_id` does not exist or is inactive |
| 422 | `invalid_manager` | Own manager, or the change would create a loop |
| 500 | `internal_error` | Unexpected server problem |

Validation error example:

```json
{"error": {"code": "validation_error", "message": "Request validation failed",
  "details": [{"field": "work_email", "in": "body", "message": "value is not a valid email address: An email address must have an @-sign."}]}}
```

## Sample data

See `data/sample_employees.json` (10 fake employees).
