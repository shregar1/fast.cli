"""Tests for :mod:`fastx_cli.commands.db_cmd`."""

from __future__ import annotations

import subprocess as sp
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.commands.db_cmd import AlembicProjectGuard


def test_alembic_guard_binary() -> None:
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value=None):
        with pytest.raises(click.Abort):
            AlembicProjectGuard.require_alembic_binary()


def test_alembic_guard_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/bin/alembic"):
        with pytest.raises(click.Abort):
            AlembicProjectGuard.require_alembic_ini()


def test_db_migrate_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.return_value = MagicMock(
                returncode=0,
                stdout="Generating /x/migration.py\n",
                stderr="",
            )
            r = runner.invoke(cli, ["db", "migrate", "-m", "msg"])
            assert r.exit_code == 0


def test_db_migrate_no_alembic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value=None):
        r = runner.invoke(cli, ["db", "migrate", "-m", "m"])
        assert r.exit_code != 0


def test_db_migrate_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch(
            "fastx_cli.commands.db_cmd.subprocess.run",
            side_effect=sp.TimeoutExpired("a", 1),
        ):
            r = runner.invoke(cli, ["db", "migrate", "-m", "m"])
            assert r.exit_code != 0


def test_db_migrate_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="e", stdout="")
            r = runner.invoke(cli, ["db", "migrate", "-m", "m"])
            assert r.exit_code != 0


def test_db_upgrade_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="rev", stderr="")
            r = runner.invoke(cli, ["db", "upgrade"])
            assert r.exit_code == 0


def test_db_upgrade_with_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            r = runner.invoke(cli, ["db", "upgrade"])
            assert r.exit_code == 0


def test_db_downgrade_click_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("questionary")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
            with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                r = runner.invoke(cli, ["db", "downgrade"], input="y\n")
                assert r.exit_code == 0


def test_db_downgrade_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        r = runner.invoke(cli, ["db", "downgrade"], input="n\n")
        assert r.exit_code == 0


def test_db_downgrade_questionary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("questionary")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", True):
        with patch("fastx_cli.commands.db_cmd.questionary.confirm") as c:
            c.return_value.ask.return_value = True
            with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
                with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
                    run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                    r = runner.invoke(cli, ["db", "downgrade"])
                    assert r.exit_code == 0


def test_db_reset_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
            with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0, stderr="", stdout="")
                r = runner.invoke(
                    cli,
                    ["db", "reset", "--no-seed"],
                    input="y\nRESET\n",
                )
                assert r.exit_code == 0


def test_db_reset_with_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "seed.py").write_text("print(1)")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
            with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0, stderr="", stdout="")
                r = runner.invoke(
                    cli,
                    ["db", "reset", "--seed"],
                    input="y\nRESET\n",
                )
                assert r.exit_code == 0


def test_db_reset_seed_missing_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
            with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0, stderr="", stdout="")
                r = runner.invoke(
                    cli,
                    ["db", "reset", "--seed"],
                    input="y\nRESET\n",
                )
                assert r.exit_code == 0


def test_db_history_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    out = "line (current)\n  a → b\n  plain\n"
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout="cur"),
                MagicMock(returncode=0, stdout=out),
            ]
            r = runner.invoke(cli, ["db", "history", "--verbose"])
            assert r.exit_code == 0


def test_db_history_failure_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=1, stderr="e", stdout=""),
            ]
            r = runner.invoke(cli, ["db", "history"])
            assert r.exit_code == 0


def test_db_status_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout="head1"),
                MagicMock(returncode=0, stdout="x → y\n"),
            ]
            r = runner.invoke(cli, ["db", "status"])
            assert r.exit_code == 0


def test_db_status_up_to_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch("fastx_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout="cur"),
                MagicMock(returncode=0, stdout="h"),
                MagicMock(returncode=0, stdout=" (current)\n"),
            ]
            r = runner.invoke(cli, ["db", "status"])
            assert r.exit_code == 0


def test_db_status_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text("x")
    runner = CliRunner()
    with patch("fastx_cli.commands.db_cmd.shutil.which", return_value="/a"):
        with patch(
            "fastx_cli.commands.db_cmd.subprocess.run",
            side_effect=RuntimeError("x"),
        ):
            r = runner.invoke(cli, ["db", "status"])
            assert r.exit_code != 0
