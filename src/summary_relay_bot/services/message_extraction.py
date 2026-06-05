from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractedMessage:
    message_type: str
    text: str | None
    caption: str | None
    summary_content: str
    file_id: str | None = None
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    media_metadata: dict[str, Any] | None = None
    unsupported: bool = False
    unsupported_reason: str | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _with_caption(placeholder: str, caption: str | None) -> str:
    caption = _clean(caption)
    if caption:
        return f"{placeholder} {caption}"
    return placeholder


def _metadata(
    *,
    file_id: str | None = None,
    file_unique_id: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    message_type: str,
    caption: str | None = None,
) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "file_size": file_size,
        "message_type": message_type,
        "caption": caption,
    }


def extract_message_for_summary(message: Any) -> ExtractedMessage:
    text = _clean(getattr(message, "text", None))
    caption = _clean(getattr(message, "caption", None))
    if text is not None:
        return ExtractedMessage(message_type="text", text=text, caption=None, summary_content=text)

    document = getattr(message, "document", None)
    if document is not None:
        file_name = getattr(document, "file_name", None)
        placeholder = f"[document: {file_name}]" if file_name else "[document]"
        return ExtractedMessage(
            message_type="document",
            text=None,
            caption=caption,
            summary_content=_with_caption(placeholder, caption),
            file_id=getattr(document, "file_id", None),
            file_unique_id=getattr(document, "file_unique_id", None),
            file_name=file_name,
            mime_type=getattr(document, "mime_type", None),
            file_size=getattr(document, "file_size", None),
            media_metadata=_metadata(
                file_id=getattr(document, "file_id", None),
                file_unique_id=getattr(document, "file_unique_id", None),
                file_name=file_name,
                mime_type=getattr(document, "mime_type", None),
                file_size=getattr(document, "file_size", None),
                message_type="document",
                caption=caption,
            ),
        )

    photos = getattr(message, "photo", None)
    if photos:
        largest = photos[-1]
        return ExtractedMessage(
            message_type="photo",
            text=None,
            caption=caption,
            summary_content=_with_caption("[photo]", caption),
            file_id=getattr(largest, "file_id", None),
            file_unique_id=getattr(largest, "file_unique_id", None),
            file_size=getattr(largest, "file_size", None),
            media_metadata=_metadata(
                file_id=getattr(largest, "file_id", None),
                file_unique_id=getattr(largest, "file_unique_id", None),
                file_size=getattr(largest, "file_size", None),
                message_type="photo",
                caption=caption,
            ),
        )

    for attr, placeholder in (
        ("voice", "[voice]"),
        ("video", "[video]"),
        ("sticker", "[sticker]"),
    ):
        media = getattr(message, attr, None)
        if media is not None:
            return ExtractedMessage(
                message_type=attr,
                text=None,
                caption=caption,
                summary_content=_with_caption(placeholder, caption),
                file_id=getattr(media, "file_id", None),
                file_unique_id=getattr(media, "file_unique_id", None),
                mime_type=getattr(media, "mime_type", None),
                file_size=getattr(media, "file_size", None),
                media_metadata=_metadata(
                    file_id=getattr(media, "file_id", None),
                    file_unique_id=getattr(media, "file_unique_id", None),
                    mime_type=getattr(media, "mime_type", None),
                    file_size=getattr(media, "file_size", None),
                    message_type=attr,
                    caption=caption,
                ),
            )

    return ExtractedMessage(
        message_type="unsupported",
        text=None,
        caption=caption,
        summary_content="[unsupported]" if not caption else f"[unsupported] {caption}",
        media_metadata={"message_type": "unsupported", "caption": caption},
        unsupported=True,
        unsupported_reason="unsupported_message_type",
    )


def message_type_for_private_copy(message: Any) -> str:
    if getattr(message, "text", None):
        return "text"
    for attr in ("document", "photo", "voice", "video", "sticker", "audio", "animation"):
        if getattr(message, attr, None):
            return attr
    return "unsupported"
