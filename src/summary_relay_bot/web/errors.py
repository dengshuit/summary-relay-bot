from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class WebUnauthorizedError(Exception):
    """Raised when a Web API request fails admin token authentication."""


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def api_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code=code, message=message, details=details),
    )


def unauthorized_response() -> JSONResponse:
    return api_error_response(
        status_code=401,
        code="unauthorized",
        message="认证失败",
    )


async def unauthorized_exception_handler(
    request: Request,
    exc: WebUnauthorizedError,
) -> JSONResponse:
    return unauthorized_response()


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return api_error_response(
        status_code=400,
        code="validation_error",
        message="request validation failed",
    )
