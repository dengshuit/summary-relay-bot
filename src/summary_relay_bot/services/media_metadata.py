from __future__ import annotations

from typing import Any

from summary_relay_bot.services.message_extraction import ExtractedMessage


def media_metadata_from_extracted(extracted: ExtractedMessage) -> dict[str, Any] | None:
    return extracted.media_metadata
