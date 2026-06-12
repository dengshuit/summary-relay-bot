from __future__ import annotations

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.repositories import (
    create_private_message,
    create_reply_map,
    get_or_create_raw_update,
    upsert_private_user,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app


ADMIN_TOKEN = "webui-admin-secret"


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=ADMIN_TOKEN,
    )


def _web_app(session_factory, bootstrap_config: BootstrapConfig):
    return create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
    )


async def _request(
    app,
    method: str,
    path: str,
    *,
    token: str | None = ADMIN_TOKEN,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers)


async def _seed_relays(session):
    raw, _ = await get_or_create_raw_update(
        session,
        update_id=9901,
        payload={"message": {"text": "raw private update payload must not leak"}},
    )
    alice = await upsert_private_user(
        session,
        telegram_user_id=2002,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    inbound = await create_private_message(
        session,
        private_user=alice,
        raw_update=raw,
        direction="incoming",
        telegram_chat_id=2002,
        telegram_message_id=55,
        admin_message_id=101,
        message_type="text",
        text="hello owner, please help",
        delivery_status="sent",
    )
    await create_reply_map(
        session,
        private_user=alice,
        private_message=inbound,
        admin_chat_id=1001,
        admin_message_id=101,
        source_kind="copied_message",
    )
    await create_private_message(
        session,
        private_user=alice,
        direction="outgoing",
        telegram_chat_id=2002,
        telegram_message_id=56,
        admin_message_id=102,
        message_type="text",
        text="owner reply",
        delivery_status="failed",
        error_type="telegram_error",
        error_message="delivery failed",
    )
    return inbound


async def test_get_private_relays_returns_reply_maps_stats_and_safe_previews(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    async with session_scope(session_factory) as session:
        inbound = await _seed_relays(session)

    response = await _request(_web_app(session_factory, bootstrap_config), "GET", "/api/private-relays")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["total"] == 2
    assert payload["stats"]["sent"] == 1
    assert payload["stats"]["failed"] == 1
    item = next(item for item in payload["items"] if item["id"] == inbound.id)
    assert item["private_user"]["telegram_user_id"] == 2002
    assert item["text_preview"] == "hello owner, please help"
    assert item["reply_maps"] == [
        {
            "source_kind": "copied_message",
            "status": "mapped",
            "admin_message_id": 101,
        }
    ]
    rendered = response.text
    assert "raw private update payload must not leak" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered


async def test_private_relays_filters_search_and_paginates(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    async with session_scope(session_factory) as session:
        inbound = await _seed_relays(session)

    app = _web_app(session_factory, bootstrap_config)
    filtered = await _request(app, "GET", "/api/private-relays?direction=incoming&status=sent&q=alice")
    page = await _request(app, "GET", "/api/private-relays?limit=1")

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [inbound.id]
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["next_cursor"] is not None


async def test_private_relays_api_requires_admin_token(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "GET",
        "/api/private-relays",
        token=None,
    )

    assert response.status_code == 401
