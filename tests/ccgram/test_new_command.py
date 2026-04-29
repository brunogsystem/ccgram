"""Tests for /new command (renamed from /start)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccgram.bot import create_bot, new_command, start_command


def _make_update(user_id: int, thread_id: int | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=user_id)
    update.message = AsyncMock()
    update.message.message_thread_id = thread_id
    return update


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


@pytest.fixture(autouse=True)
def _allow_user():
    with patch("ccgram.bot.is_user_allowed", return_value=True):
        yield


class TestNewCommand:
    async def test_sends_welcome(self) -> None:
        update = _make_update(100)
        ctx = _make_context()

        await new_command(update, ctx)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Claude Code Monitor" in text

    async def test_clears_browse_state(self) -> None:
        update = _make_update(100)
        ctx = _make_context()

        with patch("ccgram.bot.clear_browse_state") as mock_clear:
            await new_command(update, ctx)
            mock_clear.assert_called_once_with(ctx.user_data)

    async def test_unauthorized_user(self) -> None:
        update = _make_update(999)
        ctx = _make_context()

        with patch("ccgram.bot.is_user_allowed", return_value=False):
            await new_command(update, ctx)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "not authorized" in text

    async def test_no_message(self) -> None:
        update = _make_update(100)
        update.message = None
        ctx = _make_context()

        await new_command(update, ctx)

    async def test_no_user(self) -> None:
        update = _make_update(100)
        update.effective_user = None
        ctx = _make_context()

        await new_command(update, ctx)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "not authorized" in text


class TestStartCommand:
    @patch("ccgram.bot.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.bot.thread_router")
    async def test_opens_session_creation_without_pending_text(
        self, mock_router: MagicMock, mock_unbound: AsyncMock
    ) -> None:
        mock_router.get_window_for_thread.return_value = None
        update = _make_update(100, thread_id=42)
        ctx = _make_context()

        await start_command(update, ctx)

        mock_unbound.assert_awaited_once_with(100, 42, None, ctx.user_data, update.message)

    @patch("ccgram.bot.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.bot.thread_router")
    async def test_bound_topic_reports_existing_session(
        self, mock_router: MagicMock, mock_unbound: AsyncMock
    ) -> None:
        mock_router.get_window_for_thread.return_value = "@7"
        mock_router.get_display_name.return_value = "proj"
        update = _make_update(100, thread_id=42)
        ctx = _make_context()

        await start_command(update, ctx)

        mock_unbound.assert_not_awaited()
        update.message.reply_text.assert_called_once()
        assert "already bound" in update.message.reply_text.call_args.args[0]


class TestCommandRegistration:
    @patch("ccgram.bot.config")
    def test_new_and_start_both_registered(self, mock_config: MagicMock) -> None:
        mock_config.telegram_bot_token = "fake:token"
        app = create_bot()

        handler_commands: list[str] = []
        for group_handlers in app.handlers.values():
            for handler in group_handlers:
                if hasattr(handler, "commands"):
                    handler_commands.extend(handler.commands)  # type: ignore[union-attr]

        assert "new" in handler_commands
        assert "start" in handler_commands

    @patch("ccgram.bot.config")
    def test_start_has_own_session_creation_handler(self, mock_config: MagicMock) -> None:
        mock_config.telegram_bot_token = "fake:token"
        app = create_bot()

        new_handler = None
        start_handler = None
        for group_handlers in app.handlers.values():
            for handler in group_handlers:
                if hasattr(handler, "commands"):
                    if "new" in handler.commands:  # type: ignore[union-attr]
                        new_handler = handler
                    if "start" in handler.commands:  # type: ignore[union-attr]
                        start_handler = handler

        assert new_handler is not None
        assert start_handler is not None
        assert new_handler.callback is new_command
        assert start_handler.callback is start_command
