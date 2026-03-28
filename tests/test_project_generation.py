"""Tests for :mod:`fast_cli.project_generation`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fast_cli.app import cli
from fast_cli.paths import FrameworkSourceLocator
from fast_cli.project_generation import ProjectGenerationOrchestrator
from fast_cli.venv import VirtualEnvironmentService


def test_execute_pipeline_full_mock(tmp_path: Path) -> None:
    orch = ProjectGenerationOrchestrator()
    ctx = {
        "create_venv": True,
        "install_deps": True,
        "init_precommit": True,
        "venv_name": ".venv",
    }
    with patch.object(orch, "_locator") as loc:
        loc.fast_mvc_root.return_value = tmp_path / "src"
        loc.list_existing_template_items.return_value = []
        orch._copier.copy_with_progress = MagicMock(return_value=0)
        orch._bootstrap.create_project_structure = MagicMock()
        orch._workflows.copy_into_project = MagicMock(return_value=True)
        orch._bootstrap.update_pyproject_toml = MagicMock()
        orch._bootstrap.generate_env_file = MagicMock()
        orch._venv.create = MagicMock(return_value=True)
        orch._gitignore.update_for_venv = MagicMock()
        orch._venv.install_requirements = MagicMock(return_value=True)
        orch._precommit.install = MagicMock(return_value=True)
        orch._ui.show_next_steps = MagicMock()
        tgt = tmp_path / "out"
        tgt.mkdir()
        orch._execute_pipeline(tgt, ctx)
        orch._precommit.install.assert_called_once()


def test_run_cli_options_abort_on_error(tmp_path: Path) -> None:
    runner = CliRunner()
    with patch.object(
        ProjectGenerationOrchestrator,
        "_execute_pipeline",
        side_effect=RuntimeError("x"),
    ):
        r = runner.invoke(
            cli,
            ["generate", "--name", "n", "--path", str(tmp_path), "--no-venv"],
        )
        assert r.exit_code != 0


def test_run_quickstart_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    with patch.object(
        ProjectGenerationOrchestrator,
        "_execute_pipeline",
        side_effect=RuntimeError("x"),
    ):
        r = runner.invoke(cli, ["quickstart", "--no-install-deps", "-n", "q"])
        assert r.exit_code != 0


def test_run_basic_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("x")
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", False):
        with patch.object(FrameworkSourceLocator, "fast_mvc_root", return_value=src):
            with patch.object(
                FrameworkSourceLocator,
                "list_existing_template_items",
                return_value=["app.py"],
            ):
                with patch.object(VirtualEnvironmentService, "create", return_value=False):
                    runner = CliRunner()
                    inp = "\n".join(
                        [
                            "proj",
                            str(tmp_path / "out"),
                            "A",
                            "a@a.co",
                            "d",
                            "0.1.0",
                            "n",
                        ]
                    )
                    r = runner.invoke(cli, ["generate"], input=inp)
                    assert r.exit_code == 0


def test_run_interactive_cancel_name() -> None:
    pytest.importorskip("questionary")
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", True):
        t = MagicMock()
        t.ask.return_value = None
        with patch("fast_cli.project_generation.questionary.text", return_value=t):
            ProjectGenerationOrchestrator().run_interactive()


def test_run_cli_options_happy_path(tmp_path: Path) -> None:
    orch = ProjectGenerationOrchestrator()
    with patch.object(orch, "_execute_pipeline"):
        orch.run_cli_options(
            "n",
            str(tmp_path),
            "a",
            "e@e.co",
            "d",
            "1.0.0",
            False,
            ".venv",
            False,
        )


def test_run_quickstart_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    orch = ProjectGenerationOrchestrator()
    with patch.object(orch, "_execute_pipeline"):
        orch.run_quickstart("x", ".venv", False)


def test_new_command_invokes_generate(tmp_path: Path) -> None:
    runner = CliRunner()
    with patch.object(ProjectGenerationOrchestrator, "run_cli_options") as m:
        r = runner.invoke(
            cli,
            ["new", "--name", "a", "--path", str(tmp_path), "--no-venv"],
        )
        assert r.exit_code == 0
        m.assert_called_once()


def test_run_basic_oserror_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "d").mkdir()
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", False):
        with patch.object(FrameworkSourceLocator, "fast_mvc_root", return_value=src):
            with patch.object(
                FrameworkSourceLocator,
                "list_existing_template_items",
                return_value=["d"],
            ):
                with patch(
                    "fast_cli.project_generation.shutil.copytree",
                    side_effect=OSError,
                ):
                    with patch.object(
                        VirtualEnvironmentService, "create", return_value=False
                    ):
                        runner = CliRunner()
                        inp = "\n".join(
                            [
                                "p",
                                str(tmp_path / "o"),
                                "A",
                                "a@a.co",
                                "d",
                                "0.1.0",
                                "n",
                            ]
                        )
                        r = runner.invoke(cli, ["generate"], input=inp)
                        assert r.exit_code == 0
