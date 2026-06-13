from __future__ import annotations

from types import SimpleNamespace

from aiogram.filters import Command

from summary_relay_bot.handlers.admin import USER_HELP, build_router, handle_user_help
from summary_relay_bot.telegram.guards import PrivateNonOwnerFilter


class FakeMessage:
    def __init__(self, user_id: int) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


async def test_non_owner_start_help_guidance_is_direct_reply() -> None:
    message = FakeMessage(2002)

    await handle_user_help(message, owner_id=1001)

    assert message.answers == [USER_HELP]
    assert "Just send your message here" in USER_HELP


async def test_owner_is_not_handled_by_non_owner_guidance() -> None:
    message = FakeMessage(1001)

    await handle_user_help(message, owner_id=1001)

    assert message.answers == []


def test_router_handles_non_owner_start_and_help_before_private_relay() -> None:
    router = build_router(owner_id=1001)
    guidance_handler = router.message.handlers[-1]
    command_filter = next(
        filter_object.callback
        for filter_object in guidance_handler.filters
        if isinstance(filter_object.callback, Command)
    )

    assert guidance_handler.callback is handle_user_help
    assert any(isinstance(filter_object.callback, PrivateNonOwnerFilter) for filter_object in guidance_handler.filters)
    assert command_filter.commands == ("start", "help")
