"""Edge cases for :meth:`ProjectGenerationOrchestrator.run_interactive` and ``run_basic``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.paths import FrameworkSourceLocator
from fastx_cli.project_generation import ProjectGenerationOrchestrator


def test_interactive_cancel_empty_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("questionary")
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
            texts = iter(["proj", ""])

            def text_side(*a, **k):
                m = MagicMock()
                m.ask.return_value = next(texts)
                return m

            q.text.side_effect = text_side
            ProjectGenerationOrchestrator().run_interactive()


def test_interactive_skip_nonempty_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("questionary")
    d = tmp_path / "out"
    d.mkdir()
    (d / "f").write_text("x")
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
            texts = iter(["p", str(d)])

            def text_side(*a, **k):
                m = MagicMock()
                m.ask.return_value = next(texts)
                return m

            q.text.side_effect = text_side
            q.confirm.return_value.ask.return_value = False
            ProjectGenerationOrchestrator().run_interactive()


def test_run_basic_outer_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", False):
        with patch(
            "fastx_cli.project_generation.click.prompt",
            side_effect=["p", str(tmp_path / "o"), "A", "a@a.co", "d", "0.1.0", "n"],
        ):
            with patch.object(
                FrameworkSourceLocator,
                "fast_mvc_root",
                side_effect=RuntimeError("boom"),
            ):
                r = CliRunner().invoke(cli, ["generate"])
                assert r.exit_code != 0
