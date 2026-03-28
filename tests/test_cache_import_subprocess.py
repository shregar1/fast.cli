"""Isolated subprocess test for cache command ``ImportError`` path."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cache_clear_import_error_isolated() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    script = """
import builtins
_real = builtins.__import__
def _imp(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "fast_caching" or (name or "").startswith("fast_caching."):
        raise ImportError("blocked")
    return _real(name, globals, locals, fromlist, level)
builtins.__import__ = _imp
from click.testing import CliRunner
from fast_cli.app import cli
r = CliRunner().invoke(cli, ["cache", "clear"])
assert r.exit_code == 0
"""
    subprocess.run([sys.executable, "-c", script], check=True, env=env)
