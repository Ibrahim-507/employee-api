# Employee API

A layered FastAPI service with PostgreSQL, run by Docker Compose.

## Project layout

```
app/
  main.py            # creates the FastAPI app
  core/config.py     # settings loaded from environment variables
  api/               # routes (HTTP layer: receive request, return response)
  services/          # business logic
  models/            # database models (added in Task 2)
  schemas/           # request/response shapes (pydantic)
tests/               # pytest tests
docs/api-contract.md # draft API contract for other teams
data/sample_employees.json # 10 fake employees
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

## Run tests (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

## Notes
- Inside Docker the database host is `db` (the service name), not `localhost`.
- Never commit `.env`. Only `.env.example` is committed.
