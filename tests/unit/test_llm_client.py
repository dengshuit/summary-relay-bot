from __future__ import annotations

from types import SimpleNamespace

import pytest

from summary_relay_bot.llm.client import PrivacyAwareSummaryClient, SummaryLLMError, assert_summary_payload_is_whitelisted
from summary_relay_bot.llm.prompts import SUMMARY_SYSTEM_PROMPT


class FakeMessagesAPI:
    def __init__(self, response_text: str = "summary") -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.response_text)],
        )


class FakeAnthropicClient:
    def __init__(self, response_text: str = "summary") -> None:
        self.options: dict | None = None
        self.messages = FakeMessagesAPI(response_text=response_text)

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


def group_message(**overrides):
    values = {
        "id": 7,
        "message_type": "document",
        "summary_content": "[document: report.pdf] read this",
        "telegram_message_id": 99,
        "sender_user_id": 123456,
        "file_id": "telegram-file-id",
        "raw_update": {"message": "raw update must not leak"},
        "private_content": "private relay content must not leak",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_request_whitelists_summary_fields_only(app_config) -> None:
    client = PrivacyAwareSummaryClient(app_config, client=FakeAnthropicClient())

    request = client.build_request(
        group_title="Group",
        group_messages=[group_message()],
    )

    assert request.messages == [
        {
            "message_type": "document",
            "summary_content": "[document: report.pdf] read this",
        }
    ]
    assert_summary_payload_is_whitelisted(request)
    rendered = request.to_interval_text()
    assert "#7" not in rendered
    assert "telegram-file-id" not in rendered
    assert "123456" not in rendered
    assert "raw update" not in rendered
    assert "private relay" not in rendered


async def test_summarize_uses_configured_model_timeout_prompt_version_and_cache(app_config) -> None:
    fake_client = FakeAnthropicClient(response_text="- concise summary")
    client = PrivacyAwareSummaryClient(app_config, client=fake_client)

    summary = await client.summarize_group_messages(
        group_title="Group",
        group_messages=[group_message(id=11, summary_content="hello group")],
    )

    assert summary == "- concise summary"
    assert fake_client.options == {"timeout": app_config.llm_timeout_seconds, "max_retries": 2}
    [call] = fake_client.messages.calls
    assert call["model"] == app_config.llm_model
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "medium"}
    assert call["system"] == [
        {
            "type": "text",
            "text": SUMMARY_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert f"Prompt version: {app_config.summary_prompt_version}" in call["messages"][0]["content"]


async def test_summarize_rejects_empty_intervals(app_config) -> None:
    client = PrivacyAwareSummaryClient(app_config, client=FakeAnthropicClient())

    with pytest.raises(SummaryLLMError, match="no messages"):
        await client.summarize_group_messages(group_title="Group", group_messages=[])


async def test_summarize_rejects_empty_llm_output(app_config) -> None:
    client = PrivacyAwareSummaryClient(app_config, client=FakeAnthropicClient(response_text="   "))

    with pytest.raises(SummaryLLMError, match="empty"):
        await client.summarize_group_messages(
            group_title="Group",
            group_messages=[group_message()],
        )
