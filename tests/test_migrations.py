from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.base import Base
from tests.conftest import alembic_config

TABLES = {
    "departments", "roles", "employees", "employee_roles", "salaries", "attendance_records",
}


def test_upgrade_creates_tables_and_downgrade_removes_them(engine):
    cfg = alembic_config()

    command.downgrade(cfg, "base")
    assert TABLES.isdisjoint(inspect(engine).get_table_names())

    command.upgrade(cfg, "head")
    assert TABLES <= set(inspect(engine).get_table_names())


def test_models_and_migration_are_in_sync(engine):
    """If you change a model but forget the migration, this fails."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(ctx, Base.metadata) == []
