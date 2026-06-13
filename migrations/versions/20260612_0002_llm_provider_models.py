from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260612_0002"
down_revision: str | None = "20260604_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh schema reset: 20260604_0001 now creates llm_providers.models.
    # Keep this historical revision as a no-op so upgrade heads remain stable.
    return None


def downgrade() -> None:
    return None
