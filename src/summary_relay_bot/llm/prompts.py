from __future__ import annotations

SUMMARY_SYSTEM_PROMPT = """You summarize Telegram group conversations for the configured bot owner.

Rules:
- Summarize only the provided group-summary items.
- Do not mention Telegram numeric IDs or file IDs.
- Treat bracketed media markers like [photo] or [document: name] as content placeholders.
- Return concise bullet points plus notable questions or decisions when present.
- If the interval is too sparse to summarize, say that briefly.
"""


def build_summary_prompt(group_title: str | None, prompt_version: str, items_text: str) -> str:
    title = group_title or "Untitled group"
    return (
        f"Prompt version: {prompt_version}\n"
        f"Group: {title}\n\n"
        "Summarize the following new group activity. The input has already been privacy-filtered; "
        "do not add identifiers that are not present in the summary text.\n\n"
        f"{items_text}"
    )
