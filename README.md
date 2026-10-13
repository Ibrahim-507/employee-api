# Employee API

A layered FastAPI service with PostgreSQL, run by Docker Compose.

## Project layout

```
app/
  main.py              # creates the FastAPI app
  core/config.py       # settings loaded from environment variables
  api/                 # routes (HTTP layer)
  services/            # business logic (e.g. hierarchy_service.py)
  models/              # SQLAlchemy tables as Python classes (Task 2)
  schemas/             # request/response shapes (pydantic)
  db/                  # Base class and database session
alembic/               # database migrations
tests/                 # pytest tests
docs/api-contract.md   # draft API contract for other teams
docs/er-diagram.md     # ER diagram of the database
data/sample_employees.json
```

## Prerequisites
Python 3.12, Git, Docker (with Docker Compose).

## Run with Docker (one command)

```bash
cp .env.example .env        # then edit SECRET_KEY
docker compose up --build
```

- API: http://localhost:8000
- Health: http://localhost:8000/health
- Auto docs: http://localhost:8000/docs

Stop with `Ctrl+C`, then `docker compose down` (add `-v` to also delete DB data).

## Database and migrations (Task 2)

With `docker compose up` running, open a second terminal in the project folder:

```bash
# build the schema (creates the tables)
docker compose exec api alembic upgrade head

# check which version the database is at
docker compose exec api alembic current

# roll back everything (drops the tables)
docker compose exec api alembic downgrade base

# after changing a model, create a new migration, then review the file!
docker compose exec api alembic revision --autogenerate -m "describe the change"
```

To look inside the database:

```bash
docker compose exec db psql -U postgres -d employees -c "\dt"
docker compose exec db psql -U postgres -d employees -c "\d employees"
```

The ER diagram is in `docs/er-diagram.md`.

## Run tests

Tests use a separate database called `employees_test`, so your real data is never touched.
The test run builds that database from scratch by running the real migrations.

```bash
docker compose exec api pytest
```

You can also run them on your PC (the db container must be running):

```bash
pip install -r requirements-dev.txt
pytest
```

## Design decisions

### One role or many roles per person?

**Decision: an employee can have many roles** (many-to-many through the `employee_roles` table).

Reason: *(rewrite this in your own words before submitting)* real people hold more than
one role at once, for example "Developer" and "Team Lead", or someone covering for
another team. A single `role_id` column would force us to pick one and lose the rest.
With a separate `employee_roles` table, adding a second role is just one new row, and no
table changes are needed later when payroll or leave needs to look at all roles.
The trade-off is one extra table and a slightly more complex query. Teams that need
exactly one "main" role can add an `is_primary` flag to `employee_roles` later.

### Soft delete
Employees and departments have `is_active`. We mark them inactive instead of erasing
the row, so history (leave, payroll) keeps pointing at a real record.

### Manager hierarchy
`employees.manager_id` points to another row in the same table. `NULL` means no manager
(for example the top person). `get_all_reports()` in `app/services/hierarchy_service.py`
finds a manager's whole team at any depth using a recursive query.

### Email
Emails are unique at the database level. Task 3 (the API) should store them in
lowercase so `A@x.com` and `a@x.com` are treated as the same person.

## API (Task 3)

Open http://localhost:8000/docs to try every endpoint. The full contract is in
`docs/api-contract.md` and `docs/openapi.json`.

| Method | Path | What it does |
|---|---|---|
| POST | `/departments` | Create a department (do this first, employees need one) |
| GET | `/departments` | List departments with employee counts |
| GET | `/departments/{id}/employees` | Employees of a department (paged) |
| POST | `/employees` | Create an employee |
| GET | `/employees` | List: `?page=1&size=20&department=Engineering&q=ada` |
| GET | `/employees/{id}` | One employee |
| PATCH | `/employees/{id}` | Change some fields |
| DELETE | `/employees/{id}` | Soft delete (sets `is_active` to false) |
| GET | `/employees/{id}/team` | Direct reports |

Errors always look like `{"error": {"code": ..., "message": ..., "details": ...}}`.

### How the code is layered

```
route (app/api/routes)      reads the request, calls a service, returns the result
  -> service (app/services) all rules: unique email, loop check, soft delete, search
    -> model (app/models)   tables
schemas (app/schemas)       the shapes of requests and responses (validation lives here)
errors (app/core/errors.py) one error format for the whole API
```

### Design decisions
- **PATCH, not PUT:** the client sends only the fields that change.
- **Soft delete:** DELETE sets `is_active=false`. Lists hide inactive people unless
  `include_inactive=true`. A manager with active reports cannot be deleted.
- **Search:** `q` matches first name, last name, full name and email, ignoring case.
  `%` and `_` in the search text are treated as normal characters.
- **Pages:** every page response includes `total` and `pages`, so screens can draw page numbers.

## Notes
- Inside Docker the database host is `db` (the service name), not `localhost`.
- Never commit `.env`. Only `.env.example` is committed.
