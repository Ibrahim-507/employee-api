import os

from sqlalchemy.engine import make_url

# ---------------------------------------------------------------
# Tests use their OWN database ("<name>_test") so they can never
# touch your real data. This must run BEFORE the app is imported.
#   - inside Docker: DATABASE_URL comes from .env (host "db")
#   - on your PC:    falls back to localhost (the db port is published)
# ---------------------------------------------------------------
_base_url = make_url(
    os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/employees"
    )
)
_test_url = _base_url.set(database=f"{_base_url.database}_test")
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def alembic_config() -> Config:
    return Config("alembic.ini")


def _create_test_database_if_missing() -> None:
    admin = create_engine(
        _test_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": _test_url.database},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    """Build the schema from scratch by running the real migrations."""
    _create_test_database_if_missing()
    command.upgrade(alembic_config(), "head")
    engine = create_engine(_test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """A session whose changes are rolled back after every test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()
