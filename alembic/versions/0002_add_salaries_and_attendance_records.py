"""add salaries and attendance records

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 15:42:52.542167
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('attendance_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('check_in', sa.Time(), nullable=True),
    sa.Column('check_out', sa.Time(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('present', 'absent', 'on_leave', 'half_day')", name=op.f('ck_attendance_records_valid_status')),
    sa.CheckConstraint('check_in IS NULL OR check_out IS NULL OR check_out > check_in', name=op.f('ck_attendance_records_checkout_after_checkin')),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_attendance_records_employee_id_employees'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attendance_records')),
    sa.UniqueConstraint('employee_id', 'work_date', name='uq_attendance_employee_work_date')
    )
    op.create_index('ix_attendance_records_work_date', 'attendance_records', ['work_date'], unique=False)
    op.create_table('salaries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('monthly_salary', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('monthly_salary > 0', name=op.f('ck_salaries_positive_amount')),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_salaries_employee_id_employees'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_salaries')),
    sa.UniqueConstraint('employee_id', 'effective_from', name='uq_salaries_employee_effective_from')
    )
    op.create_index(op.f('ix_salaries_employee_id'), 'salaries', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_salaries_employee_id'), table_name='salaries')
    op.drop_table('salaries')
    op.drop_index('ix_attendance_records_work_date', table_name='attendance_records')
    op.drop_table('attendance_records')
