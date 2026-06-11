from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from summary_relay_bot.llm.client import PrivacyAwareSummaryClient, SummaryLLMError, assert_summary_payload_is_whitelisted
from summary_relay_bot.services.runtime_config import LLMProviderRuntimeConfig, SummaryProfileRuntimeConfig


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


class FakeOpenAIHTTPClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


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


def openai_response(status_code: int = 200, *, payload: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://llm.example.test/v1/chat/completions")
    return httpx.Response(
        status_code,
        json=payload or {"choices": [{"message": {"content": "openai summary"}}]},
        request=request,
    )


def runtime_summary_profile(**overrides) -> SummaryProfileRuntimeConfig:
    provider_overrides = overrides.pop("provider", {})
    provider = LLMProviderRuntimeConfig(
        llm_provider_id=2,
        provider_type="openai_compatible",
        api_key="runtime-llm-key",
        default_model="provider-default-model",
        timeout_seconds=17,
        max_retries=1,
        base_url="https://llm.example.test/v1",
    )
    provider = replace(provider, **provider_overrides)
    values = {
        "summary_profile_id": 3,
        "llm_provider": provider,
        "model": "profile-model",
        "prompt_version": "runtime-v2",
        "system_prompt": "runtime system prompt",
        "temperature": 0.3,
        "max_output_tokens": 123,
    }
    values.update(overrides)
    return SummaryProfileRuntimeConfig(**values)


def test_build_request_whitelists_summary_fields_only() -> None:
    client = PrivacyAwareSummaryClient(
        runtime_summary_profile(provider={"provider_type": "anthropic"}),
        client=FakeAnthropicClient(),
    )

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


async def test_summarize_uses_runtime_profile_model_timeout_prompt_version_and_cache() -> None:
    fake_client = FakeAnthropicClient(response_text="- concise summary")
    runtime_profile = runtime_summary_profile(provider={"provider_type": "anthropic"})
    client = PrivacyAwareSummaryClient(runtime_profile, client=fake_client)

    summary = await client.summarize_group_messages(
        group_title="Group",
        group_messages=[group_message(id=11, summary_content="hello group")],
    )

    assert summary == "- concise summary"
    assert fake_client.options == {"timeout": runtime_profile.llm_provider.timeout_seconds, "max_retries": 1}
    [call] = fake_client.messages.calls
    assert call["model"] == runtime_profile.model
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "medium"}
    assert call["system"] == [
        {
            "type": "text",
            "text": runtime_profile.system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert f"Prompt version: {runtime_profile.prompt_version}" in call["messages"][0]["content"]


async def test_summarize_rejects_empty_intervals() -> None:
    client = PrivacyAwareSummaryClient(runtime_summary_profile(), client=FakeAnthropicClient())

    with pytest.raises(SummaryLLMError, match="no messages"):
        await client.summarize_group_messages(group_title="Group", group_messages=[])


async def test_summarize_rejects_empty_llm_output() -> None:
    client = PrivacyAwareSummaryClient(
        runtime_summary_profile(provider={"provider_type": "anthropic"}),
        client=FakeAnthropicClient(response_text="   "),
    )

    with pytest.raises(SummaryLLMError, match="empty"):
        await client.summarize_group_messages(
            group_title="Group",
            group_messages=[group_message()],
        )


def test_client_rejects_non_runtime_profile_config(app_config) -> None:
    with pytest.raises(SummaryLLMError, match="invalid_llm_config"):
        PrivacyAwareSummaryClient(app_config)


async def test_openai_compatible_uses_runtime_provider_base_url_and_chat_completions_payload() -> None:
    fake_http = FakeOpenAIHTTPClient(
        [openai_response(payload={"choices": [{"message": {"content": "  compatible summary  "}}]})]
    )
    client = PrivacyAwareSummaryClient(runtime_summary_profile(), http_client=fake_http)

    summary = await client.summarize_group_messages(
        group_title="Group",
        group_messages=[group_message(summary_content="hello compatible provider")],
    )

    assert summary == "compatible summary"
    [call] = fake_http.calls
    assert call["url"] == "https://llm.example.test/v1/chat/completions"
    assert call["timeout"] == 17
    assert call["headers"] == {
        "Authorization": "Bearer runtime-llm-key",
        "Content-Type": "application/json",
    }
    assert call["json"]["model"] == "profile-model"
    assert call["json"]["max_tokens"] == 123
    assert call["json"]["temperature"] == 0.3
    assert call["json"]["messages"][0] == {"role": "system", "content": "runtime system prompt"}
    assert "Prompt version: runtime-v2" in call["json"]["messages"][1]["content"]
    assert "hello compatible provider" in call["json"]["messages"][1]["content"]


async def test_openai_provider_uses_default_openai_base_url_without_env_base_url() -> None:
    fake_http = FakeOpenAIHTTPClient([openai_response()])
    config = runtime_summary_profile(provider={"provider_type": "openai", "base_url": None})
    client = PrivacyAwareSummaryClient(config, http_client=fake_http)

    await client.summarize_group_messages(
        group_title="Group",
        group_messages=[group_message()],
    )

    [call] = fake_http.calls
    assert call["url"] == "https://api.openai.com/v1/chat/completions"


async def test_openai_compatible_requires_runtime_base_url() -> None:
    fake_http = FakeOpenAIHTTPClient([openai_response()])
    config = runtime_summary_profile(provider={"base_url": None})
    client = PrivacyAwareSummaryClient(config, http_client=fake_http)

    with pytest.raises(SummaryLLMError, match="llm_base_url_required"):
        await client.summarize_group_messages(
            group_title="Group",
            group_messages=[group_message()],
        )

    assert fake_http.calls == []


async def test_openai_compatible_retries_retryable_status_and_maps_rate_limit() -> None:
    fake_retry_http = FakeOpenAIHTTPClient(
        [
            openai_response(503, payload={"error": {"message": "try again"}}),
            openai_response(payload={"choices": [{"message": {"content": "after retry"}}]}),
        ]
    )
    client = PrivacyAwareSummaryClient(runtime_summary_profile(), http_client=fake_retry_http)

    summary = await client.summarize_group_messages(
        group_title="Group",
        group_messages=[group_message()],
    )

    assert summary == "after retry"
    assert len(fake_retry_http.calls) == 2

    fake_rate_limit_http = FakeOpenAIHTTPClient([openai_response(429, payload={"error": {"message": "limited"}})])
    client = PrivacyAwareSummaryClient(runtime_summary_profile(), http_client=fake_rate_limit_http)

    with pytest.raises(SummaryLLMError, match="llm_rate_limited"):
        await client.summarize_group_messages(
            group_title="Group",
            group_messages=[group_message()],
        )
