"""added new status

Revision ID: c30191fce04f
Revises: 833e4a41c2ad
Create Date: 2026-08-14 14:10:04.216822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c30191fce04f'
down_revision: Union[str, Sequence[str], None] = '833e4a41c2ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUS_ENUM = sa.Enum(
    'CREATED', 'QUEUED', 'RUNNING', 'FINISHED', 'CANCELED', 'FAILED', 'UNKNOWN',
    name='processingstatusenum',
)
NEW_STATUS_ENUM = sa.Enum(
    'CREATED', 'QUEUED', 'RUNNING', 'FINISHED', 'CANCELED', 'FAILED', 'DELETED', 'UNKNOWN',
    name='processingstatusenum',
)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'processing_jobs', 'status',
        existing_type=OLD_STATUS_ENUM,
        type_=NEW_STATUS_ENUM,
        existing_nullable=False,
    )
    op.alter_column(
        'upscaling_tasks', 'status',
        existing_type=OLD_STATUS_ENUM,
        type_=NEW_STATUS_ENUM,
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'upscaling_tasks', 'status',
        existing_type=NEW_STATUS_ENUM,
        type_=OLD_STATUS_ENUM,
        existing_nullable=False,
    )
    op.alter_column(
        'processing_jobs', 'status',
        existing_type=NEW_STATUS_ENUM,
        type_=OLD_STATUS_ENUM,
        existing_nullable=False,
    )
