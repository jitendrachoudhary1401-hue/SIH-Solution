"""Add otp_challenge and account_lockout tables for secure OTP authentication

Revision ID: c2d3e4f5a6b7
Revises: b1e2a3c4d5e6
Create Date: 2026-10-27 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'b1e2a3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'otp_challenge',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=180), nullable=False),
        sa.Column('otp_verifier', sa.String(length=128), nullable=False),
        sa.Column('salt', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'consumed', 'invalidated', 'expired')"),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('otp_challenge', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_otp_challenge_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_otp_challenge_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_otp_challenge_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_otp_challenge_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_otp_challenge_user_id'), ['user_id'], unique=False)

    op.create_table(
        'account_lockout',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=180), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('account_lockout', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_lockout_email'), ['email'], unique=True)


def downgrade():
    with op.batch_alter_table('account_lockout', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_lockout_email'))
    op.drop_table('account_lockout')

    with op.batch_alter_table('otp_challenge', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_otp_challenge_user_id'))
        batch_op.drop_index(batch_op.f('ix_otp_challenge_status'))
        batch_op.drop_index(batch_op.f('ix_otp_challenge_expires_at'))
        batch_op.drop_index(batch_op.f('ix_otp_challenge_email'))
        batch_op.drop_index(batch_op.f('ix_otp_challenge_created_at'))
    op.drop_table('otp_challenge')
