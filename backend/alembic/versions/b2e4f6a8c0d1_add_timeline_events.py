"""add timeline events

Revision ID: b2e4f6a8c0d1
Revises: a1f3b2c4d5e6
Create Date: 2026-10-04 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2e4f6a8c0d1'
down_revision: Union[str, None] = 'a1f3b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'timeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=False),
        sa.Column('layer', sa.String(length=20), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('start_seconds', sa.Float(), nullable=False),
        sa.Column('end_seconds', sa.Float(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('magnitude', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_timeline_events_id'), 'timeline_events', ['id'], unique=False)
    op.create_index('ix_timeline_events_presentation_id', 'timeline_events', ['presentation_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_timeline_events_presentation_id', table_name='timeline_events')
    op.drop_index(op.f('ix_timeline_events_id'), table_name='timeline_events')
    op.drop_table('timeline_events')
