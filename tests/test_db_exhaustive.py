"""Additional :mod:`fast_cli.commands.db_cmd` branch coverage."""

from __future__ import annotations

import subprocess as sp
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fast_cli.app import cli


def test_migrate_generic_exception(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch(
        "fast_cli.commands.db_cmd.subprocess.run",
        side_effect=RuntimeError("boom"),
    ):
        r = runner.invoke(cli, ["db", "migrate", "-m", "x"])
        assert r.exit_code != 0


def test_upgrade_failure_stderr(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=1, stderr="bad"),
        ]
        r = runner.invoke(cli, ["db", "upgrade"])
        assert r.exit_code != 0


def test_upgrade_timeout(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch(
        "fast_cli.commands.db_cmd.subprocess.run",
        side_effect=sp.TimeoutExpired("a", 1),
    ):
        r = runner.invoke(cli, ["db", "upgrade"])
        assert r.exit_code != 0


def test_upgrade_generic_error(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch(
        "fast_cli.commands.db_cmd.subprocess.run",
        side_effect=KeyError("x"),
    ):
        r = runner.invoke(cli, ["db", "upgrade"])
        assert r.exit_code != 0


def test_downgrade_questionary_cancel(alembic_ready: Path) -> None:
    pytest.importorskip("questionary")
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", True):
        with patch("fast_cli.commands.db_cmd.questionary.confirm") as c:
            c.return_value.ask.return_value = False
            r = runner.invoke(cli, ["db", "downgrade"])
            assert r.exit_code == 0


def test_downgrade_timeout(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch(
            "fast_cli.commands.db_cmd.subprocess.run",
            side_effect=sp.TimeoutExpired("a", 1),
        ):
            r = runner.invoke(cli, ["db", "downgrade"], input="y\n")
            assert r.exit_code != 0


def test_downgrade_fail(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=1, stderr="e"),
            ]
            r = runner.invoke(cli, ["db", "downgrade"], input="y\n")
            assert r.exit_code != 0


def test_downgrade_generic_error(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch(
            "fast_cli.commands.db_cmd.subprocess.run",
            side_effect=ValueError("x"),
        ):
            r = runner.invoke(cli, ["db", "downgrade"], input="y\n")
            assert r.exit_code != 0


def test_reset_questionary_cancel(alembic_ready: Path) -> None:
    pytest.importorskip("questionary")
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", True):
        with patch("fast_cli.commands.db_cmd.questionary.confirm") as c:
            c.return_value.ask.return_value = False
            r = runner.invoke(cli, ["db", "reset"])
            assert r.exit_code == 0


def test_reset_questionary_bad_confirm(alembic_ready: Path) -> None:
    pytest.importorskip("questionary")
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", True):
        with (
            patch("fast_cli.commands.db_cmd.questionary.confirm") as c,
            patch("fast_cli.commands.db_cmd.questionary.text") as t,
        ):
            c.return_value.ask.return_value = True
            t.return_value.ask.return_value = "NOPE"
            r = runner.invoke(cli, ["db", "reset"])
            assert r.exit_code == 0


def test_reset_downgrade_fail(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="e", stdout="")
            r = runner.invoke(
                cli,
                ["db", "reset", "--no-seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code != 0


def test_reset_downgrade_exception(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch(
            "fast_cli.commands.db_cmd.subprocess.run",
            side_effect=OSError("e"),
        ):
            r = runner.invoke(
                cli,
                ["db", "reset", "--no-seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code != 0


def test_reset_upgrade_fail(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stderr="", stdout=""),
                MagicMock(returncode=1, stderr="e", stdout=""),
            ]
            r = runner.invoke(
                cli,
                ["db", "reset", "--no-seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code != 0


def test_reset_upgrade_exception(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stderr="", stdout=""),
                OSError("e"),
            ]
            r = runner.invoke(
                cli,
                ["db", "reset", "--no-seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code != 0


def test_reset_seed_script_error(alembic_ready: Path) -> None:
    runner = CliRunner()
    (alembic_ready / "scripts").mkdir()
    (alembic_ready / "scripts" / "seed.py").write_text("x")
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stderr="", stdout=""),
                MagicMock(returncode=0, stderr="", stdout=""),
                MagicMock(returncode=1, stderr="e", stdout=""),
            ]
            r = runner.invoke(
                cli,
                ["db", "reset", "--seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code == 0


def test_reset_seed_exception(alembic_ready: Path) -> None:
    runner = CliRunner()
    (alembic_ready / "scripts").mkdir()
    (alembic_ready / "scripts" / "seed.py").write_text("x")
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stderr="", stdout=""),
                MagicMock(returncode=0, stderr="", stdout=""),
                OSError("e"),
            ]
            r = runner.invoke(
                cli,
                ["db", "reset", "--seed"],
                input="y\nRESET\n",
            )
            assert r.exit_code == 0


def test_history_current_fail(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=0, stdout="h\n"),
        ]
        r = runner.invoke(cli, ["db", "history"])
        assert r.exit_code == 0


def test_history_exception(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch(
        "fast_cli.commands.db_cmd.subprocess.run",
        side_effect=RuntimeError("x"),
    ):
        r = runner.invoke(cli, ["db", "history"])
        assert r.exit_code != 0


def test_status_no_heads(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=0, stdout="rev"),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout=" (current)\n"),
        ]
        r = runner.invoke(cli, ["db", "status"])
        assert r.exit_code == 0


def test_status_heads_empty(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout=""),
        ]
        r = runner.invoke(cli, ["db", "status"])
        assert r.exit_code == 0
