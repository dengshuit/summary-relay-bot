from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import logging
from typing import Any, Protocol

import anthropic
from anthropic import AsyncAnthropic
import httpx

from summary_relay_bot.db.models import GroupMessage
from summary_relay_bot.llm.prompts import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from summary_relay_bot.services.runtime_config import SummaryProfileRuntimeConfig

logger = logging.getLogger(__name__)

_ALLOWED_FIELDS = ("message_type", "summary_content")
_OPENAI_PROVIDER_TYPES = frozenset({"openai", "openai_compatible"})
_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MAX_OUTPUT_TOKENS = 4000
_DEFAULT_MAX_RETRIES = 2


class SummaryLLMError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SummaryLLMRequest:
    group_title: str | None
    prompt_version: str
    messages: list[dict[str, Any]]

    def to_interval_text(self) -> str:
        lines: list[str] = []
        for item in self.messages:
            lines.append(f"- {item['message_type']}: {item['summary_content']}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class SummaryLLMSettings:
    provider_type: str
    api_key: str
    model: str
    timeout_seconds: int
    max_retries: int = _DEFAULT_MAX_RETRIES
    base_url: str | None = None
    prompt_version: str = "v1"
    system_prompt: str = SUMMARY_SYSTEM_PROMPT
    temperature: float | None = None
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS


class AnthropicMessagesClient(Protocol):
    def with_options(self, **kwargs: Any) -> Any: ...


class OpenAIHTTPClient(Protocol):
    async def post(self, url: str, **kwargs: Any) -> Any: ...


class AnthropicSummaryProvider:
    def __init__(self, settings: SummaryLLMSettings, *, client: AnthropicMessagesClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAnthropic(api_key=settings.api_key, timeout=settings.timeout_seconds)

    async def summarize(self, prompt: str) -> str:
        try:
            response = await self.client.with_options(
                timeout=self.settings.timeout_seconds,
                max_retries=self.settings.max_retries,
            ).messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_output_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                system=[
                    {
                        "type": "text",
                        "text": self.settings.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APITimeoutError as exc:
            raise SummaryLLMError("llm_timeout") from exc
        except anthropic.RateLimitError as exc:
            raise SummaryLLMError("llm_rate_limited") from exc
        except anthropic.APIStatusError as exc:
            raise SummaryLLMError(f"llm_api_error:{exc.status_code}") from exc
        except anthropic.APIError as exc:
            raise SummaryLLMError("llm_api_error") from exc

        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return _join_summary_text(text_parts)


class OpenAICompatibleSummaryProvider:
    def __init__(self, settings: SummaryLLMSettings, *, client: OpenAIHTTPClient | None = None) -> None:
        self.settings = settings
        self.client = client

    async def summarize(self, prompt: str) -> str:
        endpoint = _openai_chat_completions_endpoint(self.settings)
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_output_tokens,
            "messages": [
                {"role": "system", "content": self.settings.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature

        if self.client is not None:
            return await self._summarize_with_client(self.client, endpoint, payload)

        async with httpx.AsyncClient() as client:
            return await self._summarize_with_client(client, endpoint, payload)

    async def _summarize_with_client(
        self,
        client: OpenAIHTTPClient,
        endpoint: str,
        payload: dict[str, Any],
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        last_error: SummaryLLMError | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.timeout_seconds,
                )
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise SummaryLLMError("llm_api_error") from exc
                return _extract_openai_summary(data)
            except httpx.TimeoutException as exc:
                raise SummaryLLMError("llm_timeout") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error = _openai_status_error(status_code)
                if _should_retry_openai_status(status_code) and attempt < self.settings.max_retries:
                    last_error = error
                    continue
                raise error from exc
            except httpx.HTTPError as exc:
                error = SummaryLLMError("llm_api_error")
                if attempt < self.settings.max_retries:
                    last_error = error
                    continue
                raise error from exc

        raise last_error or SummaryLLMError("llm_api_error")


class PrivacyAwareSummaryClient:
    def __init__(
        self,
        config: SummaryProfileRuntimeConfig,
        *,
        client: AnthropicMessagesClient | None = None,
        http_client: OpenAIHTTPClient | None = None,
    ) -> None:
        self.config = config
        self.settings = _settings_from_config(config)
        if self.settings.provider_type == "anthropic":
            self.provider = AnthropicSummaryProvider(self.settings, client=client)
        elif self.settings.provider_type in _OPENAI_PROVIDER_TYPES:
            self.provider = OpenAICompatibleSummaryProvider(self.settings, client=http_client)
        else:
            raise SummaryLLMError(f"unsupported_llm_provider_type:{self.settings.provider_type}")

    def build_request(
        self,
        *,
        group_title: str | None,
        group_messages: Sequence[GroupMessage],
    ) -> SummaryLLMRequest:
        safe_messages: list[dict[str, Any]] = []
        for message in group_messages:
            safe_messages.append(
                {
                    "message_type": message.message_type,
                    "summary_content": message.summary_content,
                }
            )
        return SummaryLLMRequest(
            group_title=group_title,
            prompt_version=self.settings.prompt_version,
            messages=safe_messages,
        )

    async def summarize_group_messages(
        self,
        *,
        group_title: str | None,
        group_messages: Sequence[GroupMessage],
    ) -> str:
        request = self.build_request(group_title=group_title, group_messages=group_messages)
        if not request.messages:
            raise SummaryLLMError("summary request has no messages")

        prompt = build_summary_prompt(
            request.group_title,
            request.prompt_version,
            request.to_interval_text(),
        )

        summary = await self.provider.summarize(prompt)
        if not summary:
            raise SummaryLLMError("llm_empty_output")
        return summary


def assert_summary_payload_is_whitelisted(payload: SummaryLLMRequest) -> None:
    for item in payload.messages:
        extra = set(item) - set(_ALLOWED_FIELDS)
        if extra:
            raise AssertionError(f"summary payload contains non-whitelisted fields: {sorted(extra)}")


def _settings_from_config(config: SummaryProfileRuntimeConfig) -> SummaryLLMSettings:
    provider = getattr(config, "llm_provider", None)
    if provider is not None:
        return SummaryLLMSettings(
            provider_type=_normalize_provider_type(provider.provider_type),
            api_key=provider.api_key,
            model=config.model,
            timeout_seconds=provider.timeout_seconds,
            max_retries=provider.max_retries,
            base_url=provider.base_url,
            prompt_version=config.prompt_version,
            system_prompt=config.system_prompt or SUMMARY_SYSTEM_PROMPT,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens or _DEFAULT_MAX_OUTPUT_TOKENS,
        )

    raise SummaryLLMError("invalid_llm_config")


def _normalize_provider_type(provider_type: str) -> str:
    return provider_type.strip().lower()


def _openai_chat_completions_endpoint(settings: SummaryLLMSettings) -> str:
    if settings.provider_type == "openai":
        base_url = settings.base_url or _OPENAI_BASE_URL
    else:
        if not settings.base_url:
            raise SummaryLLMError("llm_base_url_required")
        base_url = settings.base_url
    return f"{base_url.rstrip('/')}/chat/completions"


def _openai_status_error(status_code: int) -> SummaryLLMError:
    if status_code == 429:
        return SummaryLLMError("llm_rate_limited")
    return SummaryLLMError(f"llm_api_error:{status_code}")


def _should_retry_openai_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 500, 502, 503, 504}


def _extract_openai_summary(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SummaryLLMError("llm_empty_output")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return _join_summary_text([content])
    if isinstance(content, list):
        text_parts = [part.get("text") for part in content if isinstance(part, dict) and part.get("type") == "text"]
        return _join_summary_text(text_parts)
    raise SummaryLLMError("llm_empty_output")


def _join_summary_text(text_parts: Sequence[str | None]) -> str:
    return "\n".join(part.strip() for part in text_parts if part and part.strip()).strip()
