from __future__ import annotations

import html
from typing import Any

TELEGRAM_MESSAGE_LIMIT = 4096
TRUNCATION_SUFFIX = "\n[message truncated]"


def display_name(user: Any) -> str:
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    username = getattr(user, "username", None)
    full_name = " ".join(part for part in (first, last) if part).strip()
    if full_name and username:
        return f"{full_name} (@{username})"
    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return "Unknown user"


def render_private_user_info_card(user: Any, message_id: int | None) -> str:
    name = html.escape(display_name(user))
    user_id = getattr(user, "id", None)
    lines = ["Message context", f"From: {name}"]
    if user_id is not None:
        lines.append(f"User ID: {user_id}")
    if message_id is not None:
        lines.append(f"User message ID: {message_id}")
    lines.append("Reply to the relayed message or this card to respond.")
    return "\n".join(lines)


def render_private_text_relay(user: Any, text: str) -> str:
    name = html.escape(display_name(user))
    user_id = getattr(user, "id", None)
    lines = [f"<blockquote>From: {name}"]
    if user_id is not None:
        lines.append(f"User ID: {html.escape(str(user_id))}")
    lines.append("</blockquote>")
    header = "\n".join(lines)
    remaining = TELEGRAM_MESSAGE_LIMIT - len(header) - 1
    lines.append(_fit_escaped_text(text, remaining))
    return "\n".join(lines)


def _fit_escaped_text(text: str, limit: int) -> str:
    escaped_text = html.escape(text)
    if len(escaped_text) <= limit:
        return escaped_text
    target = max(0, limit - len(TRUNCATION_SUFFIX))
    low = 0
    high = len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if len(html.escape(text[:mid])) <= target:
            low = mid
        else:
            high = mid - 1
    return html.escape(text[:low]) + TRUNCATION_SUFFIX
