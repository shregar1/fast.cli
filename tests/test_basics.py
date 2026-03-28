"""Smoke tests for package metadata, paths, output, and CLI shims."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fast_cli
from click.testing import CliRunner
from fast_cli import __version__
from fast_cli.app import cli, main
from fast_cli.cli import cli as cli_shim
from fast_cli.commands.project_root import resolve_fastmvc_project_root
from fast_cli.output import output


def test_version_matches_init() -> None:
    assert isinstance(__version__, str)
    assert fast_cli.__version__ == __version__


def test_resolve_fastmvc_project_root_with_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert resolve_fastmvc_project_root(tmp_path) == tmp_path


def test_resolve_fastmvc_project_root_fast_mvc_only(tmp_path: Path) -> None:
    (tmp_path / "fast_mvc").mkdir()
    assert resolve_fastmvc_project_root(tmp_path) == tmp_path / "fast_mvc"


def test_output_methods() -> None:
    output.print_banner()
    output.print_success("ok")
    output.print_error("err")
    output.print_warning("warn")
    output.print_info("info")
    output.print_step(1, "step")


def test_cli_shim_same_as_app() -> None:
    assert cli is cli_shim


def test_main_invokes_cli() -> None:
    with patch("fast_cli.app.cli") as mock_cli:
        main()
        mock_cli.assert_called_once()


def test_fast_cli_main_block() -> None:
    import runpy

    with patch("fast_cli.app.main") as mock_main:
        runpy.run_module("fast_cli.__main__", run_name="__main__")
        mock_main.assert_called_once()


def test_cli_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    assert "FastMVC" in r.output or "fast" in r.output.lower()


def test_cli_version(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--version"])
    assert r.exit_code == 0
    assert __version__ in r.output
