from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.db.models import utcnow
from summary_relay_bot.db.repositories import redact_raw_payloads_older_than


@dataclass(frozen=True, slots=True)
class RetentionResult:
    redacted_raw_updates: int


async def cleanup_raw_update_payloads(
    session: AsyncSession,
    *,
    retention_days: int,
) -> RetentionResult:
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")
    older_than = utcnow() - timedelta(days=retention_days)
    redacted = await redact_raw_payloads_older_than(session, older_than=older_than)
    return RetentionResult(redacted_raw_updates=redacted)
