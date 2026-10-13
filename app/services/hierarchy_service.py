from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee


def get_all_reports(session: Session, manager_id: int) -> list[Employee]:
    """Everyone below a manager, at any depth (reports of reports...).

    Uses a recursive CTE: the database walks down the tree for us.
    """
    tree = (
        select(Employee.id)
        .where(Employee.manager_id == manager_id)
        .cte(name="tree", recursive=True)
    )
    tree = tree.union_all(
        select(Employee.id).where(Employee.manager_id == tree.c.id)
    )
    stmt = (
        select(Employee)
        .where(Employee.id.in_(select(tree.c.id)))
        .order_by(Employee.id)
    )
    return list(session.scalars(stmt))
