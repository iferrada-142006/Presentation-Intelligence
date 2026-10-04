"""add video features

Revision ID: a1f3b2c4d5e6
Revises: c7468a82a15d
Create Date: 2026-10-04 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1f3b2c4d5e6'
down_revision: Union[str, None] = 'c7468a82a15d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'video_features',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=False),
        sa.Column('timestamp_seconds', sa.Float(), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=True),
        sa.Column('face_detected', sa.Integer(), nullable=True),
        sa.Column('head_yaw', sa.Float(), nullable=True),
        sa.Column('head_pitch', sa.Float(), nullable=True),
        sa.Column('head_roll', sa.Float(), nullable=True),
        sa.Column('body_movement', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_video_features_id'), 'video_features', ['id'], unique=False)
    op.create_index('ix_video_features_presentation_id', 'video_features', ['presentation_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_video_features_presentation_id', table_name='video_features')
    op.drop_index(op.f('ix_video_features_id'), table_name='video_features')
    op.drop_table('video_features')
