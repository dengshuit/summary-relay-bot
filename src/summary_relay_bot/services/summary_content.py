from __future__ import annotations

from collections.abc import Sequence

from summary_relay_bot.db.models import GroupMessage


def render_summary_interval(messages: Sequence[GroupMessage]) -> str:
    return "\n".join(
        f"- {message.message_type}: {message.summary_content}"
        for message in messages
    )


def render_admin_summary(group_title: str | None, summary_text: str) -> str:
    title = group_title or "Untitled group"
    return f"Summary for {title}\n\n{summary_text}"


def render_no_new_messages(group_title: str | None) -> str:
    title = group_title or "Untitled group"
    return f"No new messages to summarize for {title}."
