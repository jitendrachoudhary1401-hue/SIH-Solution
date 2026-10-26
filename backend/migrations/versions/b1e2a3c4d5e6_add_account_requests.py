"""Add account_request table for registration workflows

Revision ID: b1e2a3c4d5e6
Revises: 423a5674c47d
Create Date: 2026-10-27 01:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1e2a3c4d5e6'
down_revision = '423a5674c47d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'account_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=180), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('college_name', sa.String(length=200), nullable=True),
        sa.Column('institution_id', sa.Integer(), nullable=True),
        sa.Column('roll_number', sa.String(length=60), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('academic_year', sa.String(length=30), nullable=True),
        sa.Column('employee_id', sa.String(length=60), nullable=True),
        sa.Column('designation', sa.String(length=100), nullable=True),
        sa.Column('bureau_code', sa.String(length=30), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_decision_reason', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
        sa.CheckConstraint("request_type IN ('student', 'college_rep', 'officer')"),
        sa.ForeignKeyConstraint(['institution_id'], ['institution.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('account_request', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_request_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_account_request_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_account_request_request_type'), ['request_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_account_request_status'), ['status'], unique=False)


def downgrade():
    with op.batch_alter_table('account_request', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_request_status'))
        batch_op.drop_index(batch_op.f('ix_account_request_request_type'))
        batch_op.drop_index(batch_op.f('ix_account_request_email'))
        batch_op.drop_index(batch_op.f('ix_account_request_created_at'))
    op.drop_table('account_request')
