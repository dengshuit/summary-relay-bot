from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import logging
from typing import Any, Protocol

import anthropic
from anthropic import AsyncAnthropic

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.models import GroupMessage
from summary_relay_bot.llm.prompts import SUMMARY_SYSTEM_PROMPT, build_summary_prompt

logger = logging.getLogger(__name__)

_ALLOWED_FIELDS = ("message_type", "summary_content")


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


class AnthropicMessagesClient(Protocol):
    def with_options(self, **kwargs: Any) -> Any: ...


class PrivacyAwareSummaryClient:
    def __init__(self, config: AppConfig, *, client: AnthropicMessagesClient | None = None) -> None:
        self.config = config
        self.client = client or AsyncAnthropic(api_key=config.llm_api_key, timeout=config.llm_timeout_seconds)

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
            prompt_version=self.config.summary_prompt_version,
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

        try:
            response = await self.client.with_options(
                timeout=self.config.llm_timeout_seconds,
                max_retries=2,
            ).messages.create(
                model=self.config.llm_model,
                max_tokens=4000,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                system=[
                    {
                        "type": "text",
                        "text": SUMMARY_SYSTEM_PROMPT,
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
        summary = "\n".join(part.strip() for part in text_parts if part.strip()).strip()
        if not summary:
            raise SummaryLLMError("llm_empty_output")
        return summary


def assert_summary_payload_is_whitelisted(payload: SummaryLLMRequest) -> None:
    for item in payload.messages:
        extra = set(item) - set(_ALLOWED_FIELDS)
        if extra:
            raise AssertionError(f"summary payload contains non-whitelisted fields: {sorted(extra)}")
