"""Tests for misc, docs, and related commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fastx_cli.app import cli


def test_make_resource_invokes_add() -> None:
    runner = CliRunner()
    with patch("fastx_cli.commands.misc_cmd.add_resource") as ar:
        r = runner.invoke(cli, ["make", "resource", "--name", "u"])
        assert r.exit_code == 0
        ar.assert_called_once()


def test_make_env_invokes_generate_env() -> None:
    runner = CliRunner()
    with patch(
        "fastx_cli.commands.misc_cmd.ProjectBootstrap.generate_env_file",
        return_value=True,
    ) as ge:
        r = runner.invoke(cli, ["make", "env"])
        assert r.exit_code == 0
        ge.assert_called_once()


def test_env_command() -> None:
    runner = CliRunner()
    with patch(
        "fastx_cli.commands.misc_cmd.ProjectBootstrap.generate_env_file",
        return_value=True,
    ):
        r = runner.invoke(cli, ["env"])
        assert r.exit_code == 0


def test_env_command_failure() -> None:
    runner = CliRunner()
    with patch(
        "fastx_cli.commands.misc_cmd.ProjectBootstrap.generate_env_file",
        return_value=False,
    ):
        r = runner.invoke(cli, ["env"])
        assert r.exit_code == 0


def test_docs_generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "apis" / "v1" / "users").mkdir(parents=True)
    (root / "apis" / "v1" / "users" / "get.py").write_text("#")
    (root / "dtos" / "requests" / "apis" / "v1" / "users").mkdir(parents=True)
    (root / "dtos" / "requests" / "apis" / "v1" / "users" / "x.py").write_text("#")
    monkeypatch.chdir(tmp_path)
    with patch(
        "fastx_cli.commands.docs_cmd.resolve_fastmvc_project_root",
        return_value=root,
    ):
        r = CliRunner().invoke(cli, ["docs", "generate"])
        assert r.exit_code == 0


def test_docs_deploy_success() -> None:
    runner = CliRunner()
    with patch("fastx_cli.commands.docs_cmd.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        r = runner.invoke(cli, ["docs", "deploy", "-m", "m"])
        assert r.exit_code == 0


def test_docs_deploy_failure() -> None:
    runner = CliRunner()
    with patch(
        "fastx_cli.commands.docs_cmd.subprocess.run",
        side_effect=RuntimeError("e"),
    ):
        r = runner.invoke(cli, ["docs", "deploy"])
        assert r.exit_code == 0


def test_mkdocs_ecosystem_branch(tmp_path: Path) -> None:
    from fastx_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "proj"
    root.mkdir()
    (root / "docs" / "api").mkdir(parents=True)
    eco = tmp_path / "fastx_other"
    eco.mkdir()
    (eco / "src").mkdir()
    (eco / "src" / "mod.py").write_text("x")
    MkdocsStyleReferenceGenerator(root)._write_ecosystem()
