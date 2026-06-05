from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message


PRIVATE_CHAT = "private"
GROUP_CHATS = {"group", "supergroup"}


def is_owner_user(user_id: int | None, owner_id: int) -> bool:
    return user_id is not None and user_id == owner_id


def is_private_chat(chat_type: str | None) -> bool:
    return chat_type == PRIVATE_CHAT


def is_group_chat(chat_type: str | None) -> bool:
    return chat_type in GROUP_CHATS


def is_owner_private_message(message: Any, owner_id: int) -> bool:
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    return is_owner_user(user_id, owner_id) and is_private_chat(chat_type)


def is_private_non_owner_message(message: Any, owner_id: int) -> bool:
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    return user_id is not None and user_id != owner_id and is_private_chat(chat_type)


class OwnerPrivateFilter(BaseFilter):
    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    async def __call__(self, message: Message) -> bool:
        return is_owner_private_message(message, self.owner_id)


class PrivateNonOwnerFilter(BaseFilter):
    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    async def __call__(self, message: Message) -> bool:
        return is_private_non_owner_message(message, self.owner_id)


class GroupChatFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_group_chat(getattr(getattr(message, "chat", None), "type", None))
