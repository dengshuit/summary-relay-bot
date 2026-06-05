from __future__ import annotations

import html
from typing import Any


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
    lines = ["New private message", f"From: {name}"]
    if user_id is not None:
        lines.append(f"User ID: {user_id}")
    if message_id is not None:
        lines.append(f"User message ID: {message_id}")
    lines.append("Reply to this card or the copied message to respond.")
    return "\n".join(lines)
