"""Subprocess smoke tests: real ``python -m fast_cli.app`` invocations.

These complement unit tests by exercising entry points, env handling (``NO_COLOR``),
and minimal installs closer to how users run the CLI. Kept small so CI can run them
on Linux and Windows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(
    args: list[str],
    *,
    check: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "fast_cli.app", *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def test_smoke_help() -> None:
    p = _run(["--help"])
    assert p.returncode == 0
    assert "FastMVC CLI" in p.stdout or "fast" in p.stdout.lower()


def test_smoke_doctor() -> None:
    p = _run(["doctor"])
    assert p.returncode == 0
    assert "Environment" in p.stdout or "python" in p.stdout.lower()


def test_smoke_generate_help() -> None:
    p = _run(["generate", "--help"])
    assert p.returncode == 0


def test_smoke_db_help() -> None:
    p = _run(["db", "--help"])
    assert p.returncode == 0


def test_smoke_no_color() -> None:
    p = _run(["doctor"], extra_env={"NO_COLOR": "1"})
    assert p.returncode == 0


def test_smoke_narrow_columns() -> None:
    p = _run(["doctor"], extra_env={"COLUMNS": "40"})
    assert p.returncode == 0


def test_smoke_dumb_term() -> None:
    p = _run(["--help"], extra_env={"TERM": "dumb"})
    assert p.returncode == 0


def test_entry_point_console_scripts_resolve() -> None:
    """``pip install -e .`` exposes ``fast`` on PATH; editable devs use this."""
    root = Path(__file__).resolve().parents[1]
    scripts = Path(sys.executable).parent
    for name in ("fast", "fast-cli", "fastmvc"):
        candidate = scripts / name
        if sys.platform == "win32":
            candidate = scripts / f"{name}.exe"
        if not candidate.is_file():
            continue
        p = subprocess.run(
            [str(candidate), "--help"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0
        return
    pytest.skip("Console scripts not on PATH (use python -m fast_cli.app)")
