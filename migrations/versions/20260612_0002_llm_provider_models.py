from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260612_0002"
down_revision: str | None = "20260604_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column("llm_providers", sa.Column("models", _json_type(), nullable=True))
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.execute("update llm_providers set models = jsonb_build_array(default_model)")
    else:
        op.execute("update llm_providers set models = json_array(default_model)")
    op.alter_column("llm_providers", "models", nullable=False)


def downgrade() -> None:
    op.drop_column("llm_providers", "models")
