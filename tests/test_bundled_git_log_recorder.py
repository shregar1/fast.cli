"""Tests for :mod:`fast_cli.bundled.git_log_recorder`."""

from __future__ import annotations

import json
import subprocess as sp
from pathlib import Path
from unittest.mock import patch

import pytest
from fast_cli.bundled import git_log_recorder as glr


def test_get_repo_root_success() -> None:
    with patch(
        "fast_cli.bundled.git_log_recorder.subprocess.check_output",
        return_value=b"/repo\n",
    ):
        assert glr.get_repo_root() == Path("/repo")


def test_get_repo_root_failure() -> None:
    with patch(
        "fast_cli.bundled.git_log_recorder.subprocess.check_output",
        side_effect=sp.CalledProcessError(1, "git"),
    ):
        assert glr.get_repo_root() is None


def test_get_git_info_success(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    info = glr.get_git_info()
    assert info is not None
    assert "hash" in info and "message" in info


def test_get_git_info_error() -> None:
    with patch(
        "fast_cli.bundled.git_log_recorder.subprocess.check_output",
        side_effect=RuntimeError("boom"),
    ):
        assert glr.get_git_info() is None


def test_main_writes_commit_history(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    hist = git_repo / "commit_history.json"
    if hist.exists():
        hist.unlink()
    glr.main()
    assert hist.exists()


def test_main_corrupt_json_ignored(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "commit_history.json").write_text("not json {")
    glr.main()


def test_main_duplicate_hash_skips(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    info = glr.get_git_info()
    assert info
    (git_repo / "commit_history.json").write_text(json.dumps([info]))
    glr.main()


def test_legacy_rename_to_commit_history(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    hist = git_repo / "commit_history.json"
    if hist.exists():
        hist.unlink()
    (git_repo / "GIT_METADATA.json").write_text("[]")
    glr.main()
    assert (git_repo / "commit_history.json").exists()
