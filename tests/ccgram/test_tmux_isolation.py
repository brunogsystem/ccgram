"""Tests for ccgram tmux isolation hardening."""

import subprocess
from unittest.mock import patch

from ccgram.hook import _resolve_window_id
from ccgram.tmux_manager import TmuxManager
from ccgram.utils import tmux_cmd, tmux_socket_name


class _FakePane:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bool, bool]] = []

    def send_keys(self, cmd: str, enter: bool = True, literal: bool = True) -> None:
        self.sent.append((cmd, enter, literal))


def test_tmux_cmd_uses_private_socket_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_NAME", raising=False)
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_PATH", raising=False)

    assert tmux_socket_name() == "ccgram"
    assert tmux_cmd("list-windows") == ["tmux", "-L", "ccgram", "list-windows"]


def test_tmux_cmd_can_target_default_socket(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_NAME", raising=False)

    assert tmux_cmd("list-sessions", isolated=False) == ["tmux", "list-sessions"]


def test_start_agent_scrubs_tmux_and_secret_env() -> None:
    pane = _FakePane()

    TmuxManager._start_agent_in_pane(
        pane,
        "codex --dangerously-bypass-approvals-and-sandbox",
        "resume",
    )

    assert len(pane.sent) == 1
    cmd, enter, literal = pane.sent[0]
    assert enter is True
    assert literal is True
    assert "env -u TMUX -u TMUX_PANE" in cmd
    assert "-u TELEGRAM_BOT_TOKEN" in cmd
    assert "-u OPENAI_API_KEY" in cmd
    assert cmd.endswith("codex --dangerously-bypass-approvals-and-sandbox resume")


def test_hook_prefers_ccgram_window_id_without_tmux(monkeypatch) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setenv("CCGRAM_WINDOW_ID", "ccgram:@42")
    monkeypatch.setenv("CCGRAM_WINDOW_NAME", "work")

    assert _resolve_window_id("") == ("ccgram:@42", "@42", "work")


def test_hook_fallback_uses_private_tmux_socket(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_WINDOW_ID", raising=False)
    monkeypatch.setenv("CCGRAM_TMUX_SOCKET_NAME", "ccgram-test")
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="ccgram\t@7\twork\n", stderr=""
    )

    with patch("ccgram.hook.subprocess.run", return_value=completed) as mock_run:
        assert _resolve_window_id("%9") == ("ccgram:@7", "@7", "work")

    mock_run.assert_called_once_with(
        [
            "tmux",
            "-L",
            "ccgram-test",
            "display-message",
            "-t",
            "%9",
            "-p",
            "#{session_name}\t#{window_id}\t#{window_name}",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
