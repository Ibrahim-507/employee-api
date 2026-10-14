# Importing every model here makes sure Alembic and SQLAlchemy "see" all tables.
from app.models.attendance import AttendanceRecord
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import Role, employee_roles
from app.models.salary import Salary

__all__ = [
    "AttendanceRecord",
    "Department",
    "Employee",
    "Role",
    "Salary",
    "employee_roles",
]
