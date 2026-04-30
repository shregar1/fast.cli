"""Shared pytest fixtures for fast-cli."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def alembic_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``alembic.ini`` + cwd + ``alembic`` on PATH for db command tests."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/bin/alembic"):
        yield tmp_path


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Initialize a git repository under ``tmp_path`` and return its root."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("# t\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path
