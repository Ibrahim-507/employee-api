# Importing every model here makes sure Alembic and SQLAlchemy "see" all tables.
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import Role, employee_roles

__all__ = ["Department", "Employee", "Role", "employee_roles"]
