"""Subprocess tests for :mod:`fast_cli.commands.tasks_cmd` import paths."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(code: str) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    subprocess.run([sys.executable, "-c", code], check=True, env=env, cwd=root)


def test_tasks_worker_import_error() -> None:
    _run(
        """
import builtins
_real = builtins.__import__
def _imp(n, *a, **kw):
    if n == "fast_platform" or str(n).startswith("fast_platform."):
        raise ImportError("no")
    return _real(n, *a, **kw)
builtins.__import__ = _imp
from click.testing import CliRunner
from fast_cli.app import cli
assert CliRunner().invoke(cli, ["tasks", "worker"]).exit_code == 0
"""
    )


def test_tasks_list_import_error() -> None:
    _run(
        """
import builtins
_real = builtins.__import__
def _imp(n, *a, **kw):
    if n == "fast_platform" or str(n).startswith("fast_platform."):
        raise ImportError("no")
    return _real(n, *a, **kw)
builtins.__import__ = _imp
from click.testing import CliRunner
from fast_cli.app import cli
assert CliRunner().invoke(cli, ["tasks", "list"]).exit_code == 0
"""
    )


def test_tasks_status_import_error() -> None:
    _run(
        """
import builtins
_real = builtins.__import__
def _imp(n, *a, **kw):
    if n == "fast_platform" or str(n).startswith("fast_platform."):
        raise ImportError("no")
    return _real(n, *a, **kw)
builtins.__import__ = _imp
from click.testing import CliRunner
from fast_cli.app import cli
assert CliRunner().invoke(cli, ["tasks", "status", "x"]).exit_code == 0
"""
    )


def test_tasks_dashboard_import_error() -> None:
    _run(
        """
import builtins
_real = builtins.__import__
def _imp(n, *a, **kw):
    if n == "fast_platform" or str(n).startswith("fast_platform."):
        raise ImportError("no")
    return _real(n, *a, **kw)
builtins.__import__ = _imp
from click.testing import CliRunner
from fast_cli.app import cli
assert CliRunner().invoke(cli, ["tasks", "dashboard"]).exit_code == 0
"""
    )
