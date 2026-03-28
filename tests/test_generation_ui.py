"""Tests for :mod:`fast_cli.generation_ui`."""

from __future__ import annotations

from pathlib import Path

from fast_cli.generation_ui import GenerationSummaryPresenter


def test_show_summary_table_long_description() -> None:
    ctx = {
        "project_name": "p",
        "project_slug": "p",
        "author_name": "a",
        "author_email": "e@e.co",
        "description": "x" * 80,
        "version": "1",
        "python_version": "3.11",
        "venv_name": ".venv",
        "install_deps": True,
        "init_precommit": True,
    }
    GenerationSummaryPresenter().show_summary_table(ctx)


def test_show_next_steps_variants(tmp_path: Path) -> None:
    g = GenerationSummaryPresenter()
    base = {
        "project_name": "p",
        "venv_name": ".venv",
        "install_deps": False,
    }
    g.show_next_steps(tmp_path, {**base, "venv_created": False})
    g.show_next_steps(tmp_path, {**base, "venv_created": True, "deps_installed": True})
    g.show_next_steps(
        tmp_path,
        {
            **base,
            "venv_created": True,
            "deps_installed": False,
            "precommit_initialized": True,
            "github_actions_copied": True,
        },
    )
