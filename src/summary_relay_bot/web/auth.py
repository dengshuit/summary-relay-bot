from __future__ import annotations

from typing import Annotated

import hashlib
import hmac

from fastapi import Depends, Header

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.web.deps import get_bootstrap_config
from summary_relay_bot.web.errors import WebUnauthorizedError


_BEARER_SCHEME = "bearer"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    scheme, separator, credentials = authorization.partition(" ")
    token = credentials.strip()
    if separator == "" or scheme.lower() != _BEARER_SCHEME or token == "":
        return None
    if " " in token:
        return None
    return token


def constant_time_token_equals(presented_token: str, expected_token: str) -> bool:
    presented_digest = hashlib.sha256(presented_token.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected_token.encode("utf-8")).digest()
    return hmac.compare_digest(presented_digest, expected_digest)


async def require_admin_token(
    authorization: Annotated[str | None, Header()] = None,
    bootstrap_config: BootstrapConfig = Depends(get_bootstrap_config),
) -> None:
    presented_token = _extract_bearer_token(authorization)
    token_matches = constant_time_token_equals(
        presented_token or "",
        bootstrap_config.webui_admin_token,
    )
    if presented_token is None or not token_matches:
        raise WebUnauthorizedError
