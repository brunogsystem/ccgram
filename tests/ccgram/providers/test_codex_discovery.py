"""Tests for Codex transcript discovery."""

import json
import os
import time
from pathlib import Path

from ccgram.providers.codex import CodexProvider, _is_primary_codex_session


def _write_codex_session(
    path: Path,
    *,
    session_id: str,
    cwd: str,
    source: str,
    originator: str,
    mtime: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "cwd": cwd,
                    "source": source,
                    "originator": originator,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(path, (mtime, mtime))


def test_primary_codex_session_rejects_exec_transcripts() -> None:
    assert (
        _is_primary_codex_session({"source": "exec", "originator": "codex_exec"})
        is False
    )


def test_primary_codex_session_accepts_interactive_cli_transcripts() -> None:
    assert (
        _is_primary_codex_session({"source": "cli", "originator": "codex-tui"})
        is True
    )
    assert (
        _is_primary_codex_session({"source": "cli", "originator": "codex_cli_rs"})
        is True
    )


def test_discover_transcript_skips_newer_codex_exec_and_finds_cli(
    tmp_path, monkeypatch
) -> None:
    cwd = tmp_path / "project"
    cwd.mkdir()
    home = tmp_path / "home"
    now = time.time()

    newer_exec = (
        home
        / ".ccgram"
        / "codex"
        / "sessions"
        / "2026"
        / "04"
        / "30"
        / "rollout-newer-exec.jsonl"
    )
    older_cli = (
        home
        / ".ccgram"
        / "codex"
        / "sessions"
        / "2026"
        / "04"
        / "30"
        / "rollout-older-cli.jsonl"
    )
    _write_codex_session(
        newer_exec,
        session_id="exec-session",
        cwd=str(cwd),
        source="exec",
        originator="codex_exec",
        mtime=now,
    )
    _write_codex_session(
        older_cli,
        session_id="cli-session",
        cwd=str(cwd),
        source="cli",
        originator="codex-tui",
        mtime=now - 1,
    )

    monkeypatch.setenv("CCGRAM_CODEX_HOME", str(home / ".ccgram" / "codex"))
    monkeypatch.setattr("ccgram.providers.codex.Path.home", lambda: home)

    event = CodexProvider().discover_transcript(str(cwd), "ccgram:@1")

    assert event is not None
    assert event.session_id == "cli-session"
    assert event.transcript_path == str(older_cli)
