from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import unquote, urlsplit

from summary_relay_bot.db.models import utcnow

if TYPE_CHECKING:
    from summary_relay_bot.services.userbot_ingestion import DeletedMessage, EditedMessage, IncomingMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UserbotClientConfig:
    api_id: int
    api_hash: str
    session_string: str | None = None
    proxy_url: str | None = None


@dataclass(frozen=True, slots=True)
class UserbotIdentity:
    telegram_user_id: int | None
    telegram_username: str | None
    telegram_display_name: str | None


@dataclass(frozen=True, slots=True)
class UserbotAuthResult:
    identity: UserbotIdentity
    session_string: str


class UserbotClientError(RuntimeError):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


class UserbotPasswordRequired(UserbotClientError):
    def __init__(self, partial_session_string: str | None = None) -> None:
        super().__init__("password_required", "two-factor password is required")
        self.partial_session_string = partial_session_string


class UserbotAuthClient(Protocol):
    async def send_code(self, phone_number: str) -> str:
        raise NotImplementedError

    async def sign_in_code(
        self,
        *,
        phone_number: str,
        code: str,
        phone_code_hash: str,
    ) -> UserbotAuthResult:
        raise NotImplementedError

    async def sign_in_password(self, password: str) -> UserbotAuthResult:
        raise NotImplementedError


UserbotClientFactory = Callable[[UserbotClientConfig], UserbotAuthClient]
UserbotDialogDiscoveryProvider = Callable[[], Awaitable[Sequence[Any]]]
UserbotIncomingMessageHandler = Callable[["IncomingMessage"], Awaitable[None]]
UserbotEditedMessageHandler = Callable[["EditedMessage"], Awaitable[None]]
UserbotDeletedMessageHandler = Callable[["DeletedMessage"], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class UserbotUpdateHandlers:
    on_message: UserbotIncomingMessageHandler
    on_edit: UserbotEditedMessageHandler
    on_delete: UserbotDeletedMessageHandler


class UserbotUpdateCollector(Protocol):
    async def run_until_disconnected(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError


UserbotUpdateCollectorFactory = Callable[
    [UserbotClientConfig, int, UserbotUpdateHandlers],
    UserbotUpdateCollector,
]


def parse_userbot_proxy_url(proxy_url: str | None) -> dict[str, object] | None:
    if proxy_url is None or proxy_url.strip() == "":
        return None

    parsed = urlsplit(proxy_url.strip())
    if parsed.scheme not in {"socks5", "socks4", "http"}:
        raise UserbotClientError("invalid_proxy", "proxy_url scheme is not supported")
    if not parsed.hostname or parsed.port is None:
        raise UserbotClientError("invalid_proxy", "proxy_url must include host and port")
    if parsed.port <= 0:
        raise UserbotClientError("invalid_proxy", "proxy_url port is invalid")

    proxy: dict[str, object] = {
        "proxy_type": parsed.scheme,
        "addr": parsed.hostname,
        "port": parsed.port,
        "rdns": True,
    }
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    return proxy


def create_telethon_userbot_client(config: UserbotClientConfig) -> UserbotAuthClient:
    return TelethonUserbotAuthClient(config)


def create_telethon_dialog_discovery_provider(config: UserbotClientConfig) -> UserbotDialogDiscoveryProvider:
    async def discover_dialogs() -> Sequence[DiscoveredDialog]:
        return await discover_telethon_dialogs(config)

    return discover_dialogs


def create_telethon_update_collector(
    config: UserbotClientConfig,
    userbot_id: int,
    handlers: UserbotUpdateHandlers,
) -> UserbotUpdateCollector:
    return TelethonUserbotUpdateCollector(config, userbot_id, handlers)


async def discover_telethon_dialogs(config: UserbotClientConfig) -> Sequence[DiscoveredDialog]:
    from summary_relay_bot.services.userbot_ingestion import DiscoveredDialog

    async def action(client: Any) -> Sequence[DiscoveredDialog]:
        dialogs: list[DiscoveredDialog] = []
        async for dialog in client.iter_dialogs():
            entity = getattr(dialog, "entity", None)
            dialogs.append(
                DiscoveredDialog(
                    telegram_entity_id=int(_dialog_entity_id(dialog, entity)),
                    entity_type=_dialog_entity_type(dialog, entity),
                    title=getattr(dialog, "title", None) or getattr(entity, "title", None),
                    username=getattr(entity, "username", None),
                    telegram_access_hash=getattr(entity, "access_hash", None),
                    telegram_peer_type=entity.__class__.__name__ if entity is not None else None,
                )
            )
        return dialogs

    return await _with_telethon_client(config, action)


class TelethonUserbotUpdateCollector:
    def __init__(
        self,
        config: UserbotClientConfig,
        userbot_id: int,
        handlers: UserbotUpdateHandlers,
    ) -> None:
        self._config = config
        self._userbot_id = userbot_id
        self._handlers = handlers
        self._client: Any | None = None

    async def run_until_disconnected(self) -> None:
        try:
            from telethon import events
        except ImportError as exc:
            raise UserbotClientError("telethon_unavailable", "Telethon is not installed") from exc

        client = _create_telethon_client(self._config)
        self._client = client
        try:
            client.add_event_handler(self._handle_new_message, events.NewMessage())
            client.add_event_handler(self._handle_edited_message, events.MessageEdited())
            client.add_event_handler(self._handle_deleted_message, events.MessageDeleted())
            await client.connect()
            await client.run_until_disconnected()
        except (OSError, TimeoutError) as exc:
            raise UserbotClientError("telegram_network_error", "Telegram is temporarily unreachable") from exc
        finally:
            await client.disconnect()
            if self._client is client:
                self._client = None

    async def disconnect(self) -> None:
        client = self._client
        if client is not None:
            await client.disconnect()

    async def _handle_new_message(self, event: Any) -> None:
        try:
            message = await _incoming_message_from_event(self._userbot_id, event)
        except UserbotClientError:
            logger.exception("Dropped malformed Telethon new-message update")
            return
        await self._handlers.on_message(message)

    async def _handle_edited_message(self, event: Any) -> None:
        try:
            edit = await _edited_message_from_event(self._userbot_id, event)
        except UserbotClientError:
            logger.exception("Dropped malformed Telethon edit update")
            return
        await self._handlers.on_edit(edit)

    async def _handle_deleted_message(self, event: Any) -> None:
        try:
            deleted = _deleted_message_from_event(self._userbot_id, event)
        except UserbotClientError:
            logger.exception("Dropped malformed Telethon delete update")
            return
        await self._handlers.on_delete(deleted)


class TelethonUserbotAuthClient:
    def __init__(self, config: UserbotClientConfig) -> None:
        self._config = config

    async def send_code(self, phone_number: str) -> str:
        async def action(client: Any) -> str:
            sent = await client.send_code_request(phone_number)
            phone_code_hash = getattr(sent, "phone_code_hash", None)
            if not phone_code_hash:
                raise UserbotClientError("telegram_auth_error", "Telegram did not return a phone code hash")
            return str(phone_code_hash)

        return await self._with_client(action)

    async def sign_in_code(
        self,
        *,
        phone_number: str,
        code: str,
        phone_code_hash: str,
    ) -> UserbotAuthResult:
        async def action(client: Any) -> UserbotAuthResult:
            try:
                user = await client.sign_in(
                    phone=phone_number,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
            except _session_password_needed_error() as exc:
                partial_session_string = _save_session_string(client)
                raise UserbotPasswordRequired(partial_session_string) from exc
            return await _auth_result(client, user)

        return await self._with_client(action)

    async def sign_in_password(self, password: str) -> UserbotAuthResult:
        async def action(client: Any) -> UserbotAuthResult:
            user = await client.sign_in(password=password)
            return await _auth_result(client, user)

        return await self._with_client(action)

    async def _with_client(self, action: Callable[[Any], Awaitable[Any]]) -> Any:
        return await _with_telethon_client(self._config, action)


async def _with_telethon_client(config: UserbotClientConfig, action: Callable[[Any], Awaitable[Any]]) -> Any:
    client = _create_telethon_client(config)
    try:
        await client.connect()
        return await action(client)
    except UserbotPasswordRequired:
        raise
    except _phone_code_invalid_error() as exc:
        raise UserbotClientError("invalid_code", "phone code is invalid") from exc
    except _phone_code_expired_error() as exc:
        raise UserbotClientError("expired_code", "phone code has expired") from exc
    except _password_hash_invalid_error() as exc:
        raise UserbotClientError("invalid_password", "two-factor password is invalid") from exc
    except _phone_number_invalid_error() as exc:
        raise UserbotClientError("invalid_phone_number", "phone number is invalid") from exc
    except _flood_wait_error() as exc:
        raise UserbotClientError("telegram_rate_limited", "Telegram rate limit is active") from exc
    except _rpc_error() as exc:
        raise UserbotClientError("telegram_auth_error", "Telegram authorization failed") from exc
    except (OSError, TimeoutError) as exc:
        raise UserbotClientError("telegram_network_error", "Telegram is temporarily unreachable") from exc
    finally:
        await client.disconnect()


def _create_telethon_client(config: UserbotClientConfig) -> Any:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError as exc:
        raise UserbotClientError("telethon_unavailable", "Telethon is not installed") from exc

    try:
        proxy = parse_userbot_proxy_url(config.proxy_url)
    except UserbotClientError:
        raise

    client = TelegramClient(
        StringSession(config.session_string or ""),
        config.api_id,
        config.api_hash,
        proxy=proxy,
    )
    return client


async def _incoming_message_from_event(userbot_id: int, event: Any) -> IncomingMessage:
    from summary_relay_bot.services.userbot_ingestion import IncomingMessage

    message = _event_message(event)
    chat = await _event_chat(event)
    sender = await _event_sender(event)
    message_type, text, caption, media_metadata = _normalized_message_parts(message)
    return IncomingMessage(
        userbot_id=userbot_id,
        telegram_entity_id=_event_entity_id(event, chat),
        telegram_message_id=_message_id(event, message),
        message_date=_message_datetime(message, "date"),
        text=text,
        caption=caption,
        message_type=message_type,
        telegram_thread_id=_message_thread_id(message),
        edited_at=_optional_message_datetime(message, "edit_date"),
        sender_user_id=_sender_id(sender),
        sender_username=_sender_username(sender),
        sender_display_name=_sender_display_name(sender),
        media_metadata=media_metadata,
    )


async def _edited_message_from_event(userbot_id: int, event: Any) -> EditedMessage:
    from summary_relay_bot.services.userbot_ingestion import EditedMessage

    message = _event_message(event)
    chat = await _event_chat(event)
    message_type, text, caption, media_metadata = _normalized_message_parts(message)
    return EditedMessage(
        userbot_id=userbot_id,
        telegram_entity_id=_event_entity_id(event, chat),
        telegram_message_id=_message_id(event, message),
        edited_at=_optional_message_datetime(message, "edit_date")
        or _optional_message_datetime(event, "date")
        or utcnow(),
        text=text,
        caption=caption,
        message_type=message_type,
        media_metadata=media_metadata,
    )


def _deleted_message_from_event(userbot_id: int, event: Any) -> DeletedMessage:
    from summary_relay_bot.services.userbot_ingestion import DeletedMessage

    message_ids = _deleted_message_ids(event)
    return DeletedMessage(
        userbot_id=userbot_id,
        telegram_entity_id=_event_entity_id(event, None),
        telegram_message_ids=message_ids,
        deleted_at=_optional_message_datetime(event, "date") or utcnow(),
    )


def _event_message(event: Any) -> Any:
    return getattr(event, "message", event)


async def _event_chat(event: Any) -> Any | None:
    get_chat = getattr(event, "get_chat", None)
    if get_chat is None:
        return getattr(event, "chat", None)
    return await get_chat()


async def _event_sender(event: Any) -> Any | None:
    get_sender = getattr(event, "get_sender", None)
    if get_sender is None:
        return getattr(event, "sender", None)
    return await get_sender()


def _event_entity_id(event: Any, chat: Any | None) -> int:
    for candidate in (
        getattr(event, "chat_id", None),
        getattr(_event_message(event), "chat_id", None),
        getattr(chat, "id", None),
    ):
        if candidate is not None:
            return int(candidate)
    raise UserbotClientError("telegram_update_error", "Telegram update is missing a chat id")


def _message_id(event: Any, message: Any) -> int:
    for candidate in (getattr(message, "id", None), getattr(event, "id", None)):
        if candidate is not None:
            return int(candidate)
    raise UserbotClientError("telegram_update_error", "Telegram update is missing a message id")


def _deleted_message_ids(event: Any) -> Sequence[int]:
    deleted_ids = getattr(event, "deleted_ids", None)
    if deleted_ids is not None:
        return [int(message_id) for message_id in deleted_ids]
    for candidate in (getattr(event, "deleted_id", None), getattr(event, "id", None)):
        if candidate is not None:
            return [int(candidate)]
    raise UserbotClientError("telegram_update_error", "Telegram delete update is missing message ids")


def _message_datetime(source: Any, attribute: str) -> datetime:
    return _optional_message_datetime(source, attribute) or utcnow()


def _optional_message_datetime(source: Any, attribute: str) -> datetime | None:
    value = getattr(source, attribute, None)
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _message_thread_id(message: Any) -> int | None:
    reply_to = getattr(message, "reply_to", None)
    for candidate in (
        getattr(reply_to, "forum_topic", None),
        getattr(reply_to, "reply_to_top_id", None),
        getattr(message, "reply_to_top_id", None),
        getattr(message, "reply_to_msg_id", None),
    ):
        if isinstance(candidate, bool):
            continue
        if candidate is not None:
            return int(candidate)
    return None


def _normalized_message_parts(message: Any) -> tuple[str, str | None, str | None, dict[str, object] | None]:
    content = _message_text(message)
    message_type = _message_type(message)
    has_media = message_type != "text"
    text = content if not has_media else None
    caption = content if has_media else None
    return message_type, text, caption, _media_metadata(message, message_type)


def _message_text(message: Any) -> str | None:
    for attribute in ("message", "raw_text", "text"):
        value = getattr(message, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _message_type(message: Any) -> str:
    if getattr(message, "photo", None) is not None:
        return "photo"
    if getattr(message, "video", None) is not None:
        return "video"
    if getattr(message, "voice", None) is not None:
        return "voice"
    if getattr(message, "audio", None) is not None:
        return "audio"
    if getattr(message, "sticker", None) is not None:
        return "sticker"
    if getattr(message, "document", None) is not None:
        file_info = getattr(message, "file", None)
        mime_type = getattr(file_info, "mime_type", None)
        if isinstance(mime_type, str):
            if mime_type.startswith("video/"):
                return "video"
            if mime_type.startswith("audio/"):
                return "audio"
        return "document"
    media = getattr(message, "media", None)
    if media is None:
        return "text"
    name = media.__class__.__name__.removeprefix("MessageMedia").lower()
    return name or "media"


def _media_metadata(message: Any, message_type: str) -> dict[str, object] | None:
    if message_type == "text":
        return None
    file_info = getattr(message, "file", None)
    metadata: dict[str, object] = {"media_type": message_type}
    for target_key, attribute in (
        ("file_name", "name"),
        ("mime_type", "mime_type"),
        ("file_size", "size"),
    ):
        value = getattr(file_info, attribute, None)
        if value is not None:
            metadata[target_key] = value
    return metadata


def _sender_id(sender: Any | None) -> int | None:
    value = getattr(sender, "id", None)
    return int(value) if value is not None else None


def _sender_username(sender: Any | None) -> str | None:
    value = getattr(sender, "username", None)
    return str(value) if value else None


def _sender_display_name(sender: Any | None) -> str | None:
    if sender is None:
        return None
    first_name = getattr(sender, "first_name", None)
    last_name = getattr(sender, "last_name", None)
    username = getattr(sender, "username", None)
    title = getattr(sender, "title", None)
    return " ".join(part for part in (first_name, last_name) if part) or username or title


def _dialog_entity_id(dialog: Any, entity: Any) -> int:
    for candidate in (
        getattr(dialog, "id", None),
        getattr(entity, "id", None),
    ):
        if candidate is not None:
            return int(candidate)
    raise UserbotClientError("telegram_dialog_error", "Telegram dialog is missing an entity id")


def _dialog_entity_type(dialog: Any, entity: Any) -> str:
    if getattr(dialog, "is_group", False):
        if getattr(entity, "megagroup", False):
            return "megagroup"
        return "group"
    if getattr(dialog, "is_channel", False):
        if getattr(entity, "megagroup", False):
            return "megagroup"
        return "broadcast_channel"
    return "unknown"


async def _auth_result(client: Any, user: Any) -> UserbotAuthResult:
    if user is None:
        user = await client.get_me()
    return UserbotAuthResult(
        identity=_identity_from_user(user),
        session_string=_save_session_string(client),
    )


def _identity_from_user(user: Any) -> UserbotIdentity:
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    username = getattr(user, "username", None)
    display_name = " ".join(part for part in (first_name, last_name) if part) or username
    return UserbotIdentity(
        telegram_user_id=getattr(user, "id", None),
        telegram_username=username,
        telegram_display_name=display_name,
    )


def _save_session_string(client: Any) -> str:
    session_string = client.session.save()
    if not session_string:
        raise UserbotClientError("telegram_auth_error", "Telegram session export failed")
    return str(session_string)


def _session_password_needed_error() -> type[Exception]:
    from telethon.errors import SessionPasswordNeededError

    return SessionPasswordNeededError


def _phone_code_invalid_error() -> type[Exception]:
    from telethon.errors import PhoneCodeInvalidError

    return PhoneCodeInvalidError


def _phone_code_expired_error() -> type[Exception]:
    from telethon.errors import PhoneCodeExpiredError

    return PhoneCodeExpiredError


def _password_hash_invalid_error() -> type[Exception]:
    from telethon.errors import PasswordHashInvalidError

    return PasswordHashInvalidError


def _phone_number_invalid_error() -> type[Exception]:
    from telethon.errors import PhoneNumberInvalidError

    return PhoneNumberInvalidError


def _flood_wait_error() -> type[Exception]:
    from telethon.errors import FloodWaitError

    return FloodWaitError


def _rpc_error() -> type[Exception]:
    from telethon.errors import RPCError

    return RPCError
