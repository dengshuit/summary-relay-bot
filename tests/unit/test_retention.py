from __future__ import annotations

import pytest

from summary_relay_bot.services.retention import cleanup_raw_update_payloads


async def test_retention_requires_positive_days(db_session) -> None:
    with pytest.raises(ValueError, match="positive"):
        await cleanup_raw_update_payloads(db_session, retention_days=0)
