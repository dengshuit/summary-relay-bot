from __future__ import annotations

from types import SimpleNamespace

from aiogram import Dispatcher

from summary_relay_bot.config import AppConfig
from summary_relay_bot.handlers import admin, register_routers
from summary_relay_bot.telegram.commands import ADMIN_COMMANDS, USER_COMMANDS


REMOVED_SUMMARY_COMMANDS = {"groups", "summary", "enable_group", "disable_group", "set_interval"}


class FakeMessage:
    def __init__(self, *, user_id: int = 2002, chat_type: str = "private") -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(type=chat_type)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


def _commands(commands) -> set[str]:
    return {command.command for command in commands}


def test_owner_command_menu_excludes_group_summary_commands() -> None:
    commands = _commands(ADMIN_COMMANDS)

    assert commands == {"start", "help", "reply"}
    assert commands.isdisjoint(REMOVED_SUMMARY_COMMANDS)


def test_non_owner_command_menu_only_exposes_start_and_help() -> None:
    assert _commands(USER_COMMANDS) == {"start", "help"}


def test_admin_help_excludes_group_summary_commands() -> None:
    assert "/reply <user_id> <message>" in admin.ADMIN_HELP
    for command in REMOVED_SUMMARY_COMMANDS:
        assert f"/{command}" not in admin.ADMIN_HELP


def test_private_relay_dispatcher_does_not_include_group_summary_routers() -> None:
    dispatcher = Dispatcher()

    register_routers(
        dispatcher,
        AppConfig(database_url="sqlite+aiosqlite:///:memory:"),
        owner_id=1001,
    )

    assert [router.name for router in dispatcher.sub_routers] == [
        "admin",
        "admin_replies",
        "private_user",
    ]


def test_admin_router_no_longer_registers_manual_summary_handler() -> None:
    router = admin.build_router(owner_id=1001)
    callbacks = {handler.callback.__name__ for handler in router.message.handlers}

    assert "handle_manual_summary" not in callbacks


async def test_non_owner_unsupported_slash_command_is_not_relayed() -> None:
    message = FakeMessage()

    await admin.handle_user_unsupported_command(message, owner_id=1001)

    assert message.answers == [admin.USER_UNSUPPORTED_COMMAND]
