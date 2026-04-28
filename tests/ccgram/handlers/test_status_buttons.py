"""Tests for status message inline action buttons (Esc, Screenshot, Notify)."""

from unittest.mock import patch

import pytest

from ccgram.handlers.callback_data import (
    CB_STATUS_ESC,
    CB_STATUS_NOTIFY,
    CB_STATUS_RECALL,
    CB_STATUS_REMOTE,
    CB_STATUS_SCREENSHOT,
    CB_STATUS_TOOLMODE,
    NOTIFY_MODE_ICONS,
)
from ccgram.handlers.status_bubble import build_status_keyboard


def _all_callback_data(window_id: str) -> list[str]:
    kb = build_status_keyboard(window_id)
    return [
        btn.callback_data
        for row in kb.inline_keyboard
        for btn in row
        if isinstance(btn.callback_data, str)
    ]


class TestBuildStatusKeyboard:
    @pytest.mark.parametrize(
        "prefix",
        [CB_STATUS_ESC, CB_STATUS_SCREENSHOT, CB_STATUS_NOTIFY, CB_STATUS_TOOLMODE],
    )
    def test_has_button_with_prefix(self, prefix: str) -> None:
        assert any(d.startswith(prefix) for d in _all_callback_data("@0"))

    def test_window_id_in_callback_data(self) -> None:
        data = _all_callback_data("@42")
        assert f"{CB_STATUS_ESC}@42" in data
        assert f"{CB_STATUS_SCREENSHOT}@42" in data
        assert f"{CB_STATUS_NOTIFY}@42" in data
        assert f"{CB_STATUS_TOOLMODE}@42" in data
        assert not any(d.startswith(CB_STATUS_REMOTE) for d in data)

    def test_callback_data_truncated_to_64_bytes(self) -> None:
        long_id = "@" + "x" * 60
        kb = build_status_keyboard(long_id)
        prefixes = (
            CB_STATUS_ESC,
            CB_STATUS_SCREENSHOT,
            CB_STATUS_NOTIFY,
            CB_STATUS_TOOLMODE,
        )
        for row in kb.inline_keyboard:
            for btn in row:
                cb = btn.callback_data
                assert isinstance(cb, str)
                assert len(cb) == 64
                assert any(cb.startswith(p) for p in prefixes)

    @pytest.mark.parametrize(("mode", "expected_icon"), list(NOTIFY_MODE_ICONS.items()))
    def test_bell_icon_reflects_notification_mode(
        self, mode: str, expected_icon: str
    ) -> None:
        with patch(
            "ccgram.handlers.status_bubble.get_notification_mode", return_value=mode
        ):
            kb = build_status_keyboard("@0")
            notify_btn = kb.inline_keyboard[0][2]
            assert notify_btn.text == expected_icon

    def test_no_history_single_row(self) -> None:
        kb = build_status_keyboard("@0")
        assert len(kb.inline_keyboard) == 1

    def test_history_adds_row(self) -> None:
        kb = build_status_keyboard("@0", history=["hello", "world"])
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].callback_data == f"{CB_STATUS_RECALL}@0:0"
        assert kb.inline_keyboard[0][1].callback_data == f"{CB_STATUS_RECALL}@0:1"

    def test_history_label_truncated(self) -> None:
        long_cmd = "a" * 30
        kb = build_status_keyboard("@0", history=[long_cmd])
        label = kb.inline_keyboard[0][0].text
        assert label.startswith("\u2191 ")
        assert label.endswith("\u2026")
        assert len(label) <= 2 + 20 + 1

    def test_history_none_no_extra_row(self) -> None:
        kb = build_status_keyboard("@0", history=None)
        assert len(kb.inline_keyboard) == 1

    def test_history_empty_list_no_extra_row(self) -> None:
        kb = build_status_keyboard("@0", history=[])
        assert len(kb.inline_keyboard) == 1

    def test_history_callback_data_truncated_to_64_bytes(self) -> None:
        long_id = "@" + "x" * 60
        kb = build_status_keyboard(long_id, history=["cmd"])
        btn = kb.inline_keyboard[0][0]
        cb = btn.callback_data
        assert isinstance(cb, str)
        assert len(cb) == 64  # type: ignore[arg-type]
        assert cb.startswith(CB_STATUS_RECALL)  # type: ignore[union-attr]

    def test_rc_button_not_in_status_keyboard(self) -> None:
        data = _all_callback_data("@0")
        assert not any(d.startswith(CB_STATUS_REMOTE) for d in data)

    def test_rc_active_does_not_add_status_button(self) -> None:
        kb = build_status_keyboard("@0", rc_active=True)
        data = [
            btn.callback_data
            for row in kb.inline_keyboard
            for btn in row
            if isinstance(btn.callback_data, str)
        ]
        assert not any(d.startswith(CB_STATUS_REMOTE) for d in data)


class TestToolModeButton:
    """Tool-call visibility lives in the status keyboard Dashboard slot."""

    @pytest.mark.parametrize(
        ("mode", "icon"),
        [("silent", "🔇"), ("batched", "⚡"), ("verbose", "💬")],
    )
    def test_tool_mode_icon_reflects_batch_mode(self, mode: str, icon: str) -> None:
        with patch("ccgram.handlers.status_bubble.get_batch_mode", return_value=mode):
            kb = build_status_keyboard("@0", user_id=42)
        btn = kb.inline_keyboard[0][-1]
        assert btn.text == icon
        assert btn.callback_data == f"{CB_STATUS_TOOLMODE}@0"
        assert btn.web_app is None

    def test_dashboard_not_in_status_keyboard(self) -> None:
        with patch("ccgram.handlers.status_bar_actions.config") as cfg:
            cfg.miniapp_base_url = "https://example.com"
            cfg.telegram_bot_token = "bot:abc"
            kb = build_status_keyboard("@0", user_id=42)
        for row in kb.inline_keyboard:
            for btn in row:
                assert btn.web_app is None

    def test_history_row_does_not_replace_tool_mode(self) -> None:
        kb = build_status_keyboard("@0", history=["a", "b"], user_id=42)
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[-1][-1].callback_data == f"{CB_STATUS_TOOLMODE}@0"
