from __future__ import annotations

from dataclasses import dataclass

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter, TelegramServerError


def _safe_message(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {text[:500]}"


@dataclass(frozen=True, slots=True)
class TelegramFailure:
    error_type: str
    message: str
    retryable: bool
    retry_after: int | None = None


def classify_telegram_error(exc: Exception) -> TelegramFailure:
    if isinstance(exc, TelegramRetryAfter):
        return TelegramFailure(
            error_type="rate_limited",
            message=_safe_message(exc),
            retryable=True,
            retry_after=getattr(exc, "retry_after", None),
        )
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        return TelegramFailure(
            error_type="telegram_transient",
            message=_safe_message(exc),
            retryable=True,
        )
    if isinstance(exc, TelegramForbiddenError):
        return TelegramFailure(
            error_type="telegram_forbidden",
            message=_safe_message(exc),
            retryable=False,
        )
    if isinstance(exc, TelegramAPIError):
        return TelegramFailure(
            error_type="telegram_api_error",
            message=_safe_message(exc),
            retryable=False,
        )
    return TelegramFailure(
        error_type=exc.__class__.__name__,
        message=str(exc),
        retryable=False,
    )
