from __future__ import annotations

from types import SimpleNamespace

import pytest

from summary_relay_bot.telegram.guards import (
    GroupChatFilter,
    OwnerPrivateFilter,
    PrivateNonOwnerFilter,
    is_group_chat,
    is_owner_private_message,
    is_private_non_owner_message,
)


def message(user_id: int | None, chat_type: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=None if user_id is None else SimpleNamespace(id=user_id),
        chat=SimpleNamespace(type=chat_type),
    )


def test_owner_private_guard_requires_owner_and_private_chat() -> None:
    assert is_owner_private_message(message(1001, "private"), 1001)
    assert not is_owner_private_message(message(1001, "group"), 1001)
    assert not is_owner_private_message(message(2002, "private"), 1001)


@pytest.mark.asyncio
async def test_aiogram_owner_private_filter() -> None:
    guard = OwnerPrivateFilter(1001)

    assert await guard(message(1001, "private"))
    assert not await guard(message(1001, "supergroup"))


def test_private_non_owner_guard_rejects_admin_and_groups() -> None:
    assert is_private_non_owner_message(message(2002, "private"), 1001)
    assert not is_private_non_owner_message(message(1001, "private"), 1001)
    assert not is_private_non_owner_message(message(2002, "group"), 1001)


@pytest.mark.asyncio
async def test_group_filter_matches_group_and_supergroup_only() -> None:
    guard = GroupChatFilter()

    assert is_group_chat("group")
    assert is_group_chat("supergroup")
    assert await guard(message(2002, "group"))
    assert await guard(message(2002, "supergroup"))
    assert not await guard(message(2002, "private"))
