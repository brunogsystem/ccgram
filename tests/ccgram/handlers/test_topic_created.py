"""Tests for FORUM_TOPIC_CREATED handler (manual topic starts setup)."""

from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import MessageHandler


def _make_update(
    thread_id: int | None = 42,
    chat_id: int = -100999,
    chat_type: str = "supergroup",
    user_id: int = 100,
) -> MagicMock:
    """Create a mock Update for FORUM_TOPIC_CREATED."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.message.message_thread_id = thread_id
    update.message.forum_topic_created = MagicMock()
    return update


_PATCH_ALLOWED = patch("ccgram.config.Config.is_user_allowed", return_value=True)


class TestTopicCreatedHandler:
    @_PATCH_ALLOWED
    @patch("ccgram.handlers.text_handler.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.handlers.directory_browser.clear_browse_state")
    @patch("ccgram.handlers.topic_lifecycle.thread_router")
    async def test_opens_session_setup_for_new_topic(
        self,
        mock_router: MagicMock,
        mock_clear: MagicMock,
        mock_unbound: AsyncMock,
        _allowed: MagicMock,
    ) -> None:
        from ccgram.handlers.topic_lifecycle import topic_created_handler

        ctx = MagicMock()
        ctx.user_data = {"old": "state"}
        update = _make_update()

        await topic_created_handler(update, ctx)

        mock_router.set_group_chat_id.assert_called_once_with(100, 42, -100999)
        mock_clear.assert_called_once_with(ctx.user_data)
        mock_unbound.assert_awaited_once_with(
            100, 42, None, ctx.user_data, update.message
        )

    @patch("ccgram.handlers.text_handler.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.handlers.topic_lifecycle.thread_router")
    async def test_skips_disallowed_user(
        self, mock_router: MagicMock, mock_unbound: AsyncMock
    ) -> None:
        from ccgram.handlers.topic_lifecycle import topic_created_handler

        update = _make_update()
        with patch("ccgram.config.Config.is_user_allowed", return_value=False):
            await topic_created_handler(update, MagicMock())

        mock_router.set_group_chat_id.assert_not_called()
        mock_unbound.assert_not_awaited()

    @_PATCH_ALLOWED
    @patch("ccgram.handlers.text_handler.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.handlers.topic_lifecycle.thread_router")
    async def test_skips_general_topic(
        self,
        mock_router: MagicMock,
        mock_unbound: AsyncMock,
        _allowed: MagicMock,
    ) -> None:
        from ccgram.handlers.topic_lifecycle import topic_created_handler

        update = _make_update(thread_id=1)
        await topic_created_handler(update, MagicMock())

        mock_router.set_group_chat_id.assert_not_called()
        mock_unbound.assert_not_awaited()

    @_PATCH_ALLOWED
    @patch("ccgram.handlers.text_handler.handle_unbound_topic", new_callable=AsyncMock)
    @patch("ccgram.handlers.topic_lifecycle.thread_router")
    async def test_skips_missing_topic_created_payload(
        self,
        mock_router: MagicMock,
        mock_unbound: AsyncMock,
        _allowed: MagicMock,
    ) -> None:
        from ccgram.handlers.topic_lifecycle import topic_created_handler

        update = _make_update()
        update.message.forum_topic_created = None

        await topic_created_handler(update, MagicMock())

        mock_router.set_group_chat_id.assert_not_called()
        mock_unbound.assert_not_awaited()


class TestTopicCreatedRegistration:
    @patch("ccgram.bot.config")
    def test_topic_created_handler_registered(self, mock_config: MagicMock) -> None:
        from ccgram.bot import create_bot
        from ccgram.handlers.topic_lifecycle import topic_created_handler

        mock_config.telegram_bot_token = "fake:token"
        app = create_bot()

        callbacks = [
            handler.callback
            for group_handlers in app.handlers.values()
            for handler in group_handlers
            if isinstance(handler, MessageHandler)
        ]

        assert topic_created_handler in callbacks
