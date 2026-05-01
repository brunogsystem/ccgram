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


class _FakeWindow:
    def __init__(self, window_id: str, window_name: str) -> None:
        self.window_id = window_id
        self.window_name = window_name
        self.active_pane = _FakePane()
        self.killed = False
        self.renamed_to = ""

    def kill(self) -> None:
        self.killed = True

    def rename_window(self, name: str) -> None:
        self.renamed_to = name


class _FakeWindows:
    def __init__(self, window: _FakeWindow) -> None:
        self.window = window

    def get(self, window_id: str, default=None):  # noqa: ANN001
        return self.window if window_id == self.window.window_id else default


class _FakeSession:
    def __init__(self, window: _FakeWindow) -> None:
        self.windows = _FakeWindows(window)


def test_tmux_cmd_uses_private_socket_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_NAME", raising=False)
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_PATH", raising=False)

    assert tmux_socket_name() == "ccgram"
    assert tmux_cmd("list-windows") == ["tmux", "-L", "ccgram", "list-windows"]


def test_tmux_cmd_can_target_default_socket(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_TMUX_SOCKET_NAME", raising=False)

    assert tmux_cmd("list-sessions", isolated=False) == ["tmux", "list-sessions"]


def test_start_agent_scrubs_tmux_and_secret_env(monkeypatch, tmp_path) -> None:
    pane = _FakePane()
    source_home = tmp_path / "home"
    source_codex = source_home / ".codex"
    source_codex.mkdir(parents=True)
    (source_codex / "auth.json").write_text("{}")
    (source_codex / "config.toml").write_text("model = 'test'\n")
    codex_home = tmp_path / ".ccgram" / "codex"
    monkeypatch.setattr("ccgram.tmux_manager.Path.home", lambda: source_home)
    monkeypatch.setattr("ccgram.tmux_manager.config.config_dir", tmp_path / ".ccgram")

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
    assert "-u CCGRAM_TMUX_SOCKET_NAME" in cmd
    assert "-u CCGRAM_TMUX_SOCKET_PATH" in cmd
    assert f"-u CCGRAM_TMUX_SOCKET_PATH CODEX_HOME={codex_home}" in cmd
    assert cmd.endswith(" codex --dangerously-bypass-approvals-and-sandbox resume")
    assert (codex_home / "auth.json").exists()
    assert (codex_home / "config.toml").exists()


def test_hook_prefers_ccgram_window_id_without_tmux(monkeypatch) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setenv("CCGRAM_WINDOW_ID", "ccgram:@42")
    monkeypatch.setenv("CCGRAM_WINDOW_NAME", "work")

    assert _resolve_window_id("") == ("ccgram:@42", "@42", "work")


def test_hook_fallback_uses_private_tmux_socket(monkeypatch) -> None:
    monkeypatch.delenv("CCGRAM_WINDOW_ID", raising=False)
    monkeypatch.setenv("CCGRAM_ALLOW_TMUX_PANE_HOOK_FALLBACK", "1")
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


async def test_kill_window_refuses_own_window() -> None:
    tm = TmuxManager(session_name="test")
    window = _FakeWindow("@9", "worker")

    with (
        patch("ccgram.tmux_manager.config") as mock_config,
        patch.object(tm, "get_session", return_value=_FakeSession(window)),
    ):
        mock_config.own_window_id = "@9"
        mock_config.tmux_main_window_name = "__main__"

        assert await tm.kill_window("@9") is False

    assert window.killed is False


async def test_kill_window_refuses_main_window() -> None:
    tm = TmuxManager(session_name="test")
    window = _FakeWindow("@0", "__main__")

    with (
        patch("ccgram.tmux_manager.config") as mock_config,
        patch.object(tm, "get_session", return_value=_FakeSession(window)),
    ):
        mock_config.own_window_id = None
        mock_config.tmux_main_window_name = "__main__"

        assert await tm.kill_window("@0") is False

    assert window.killed is False


async def test_send_keys_refuses_protected_window() -> None:
    tm = TmuxManager(session_name="test")
    window = _FakeWindow("@0", "__main__")

    with (
        patch("ccgram.tmux_manager.config") as mock_config,
        patch.object(tm, "get_session", return_value=_FakeSession(window)),
    ):
        mock_config.own_window_id = None
        mock_config.tmux_main_window_name = "__main__"

        assert await tm.send_keys("@0", "hello", raw=True) is False

    assert window.active_pane.sent == []


async def test_rename_window_refuses_protected_window() -> None:
    tm = TmuxManager(session_name="test")
    window = _FakeWindow("@0", "__main__")

    with (
        patch("ccgram.tmux_manager.config") as mock_config,
        patch.object(tm, "get_session", return_value=_FakeSession(window)),
    ):
        mock_config.own_window_id = None
        mock_config.tmux_main_window_name = "__main__"

        assert await tm.rename_window("@0", "renamed") is False

    assert window.renamed_to == ""
