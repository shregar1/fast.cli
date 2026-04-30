"""Tests for :mod:`fastx_cli.constants` and :mod:`fastx_cli.paths`."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastx_cli.constants import ARTIFACTS_BY_LANGUAGE, DEFAULT_TEMPLATE_ITEMS
from fastx_cli.paths import FrameworkSourceLocator


def test_default_template_items_nonempty() -> None:
    assert "app.py" in DEFAULT_TEMPLATE_ITEMS
    assert isinstance(DEFAULT_TEMPLATE_ITEMS, list)


def test_artifacts_by_language_keys() -> None:
    assert "python" in ARTIFACTS_BY_LANGUAGE
    assert "java" in ARTIFACTS_BY_LANGUAGE
    assert "rust" in ARTIFACTS_BY_LANGUAGE


def test_framework_locator_repo_root(tmp_path: Path) -> None:
    loc = FrameworkSourceLocator(package_dir=tmp_path / "fastx_cli")
    assert loc.repo_root == tmp_path


def test_fast_mvc_root_prefers_repo_child(tmp_path: Path) -> None:
    pkg = tmp_path / "fastx_cli"
    pkg.mkdir()
    mvc = tmp_path / "fast_mvc"
    mvc.mkdir()
    loc = FrameworkSourceLocator(package_dir=pkg)
    assert loc.fast_mvc_root() == mvc


def test_fast_mvc_root_fallback_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = tmp_path / "pkg" / "fastx_cli"
    pkg.mkdir(parents=True)
    mvc = tmp_path / "fast_mvc"
    mvc.mkdir()
    monkeypatch.chdir(tmp_path)
    loc = FrameworkSourceLocator(package_dir=pkg)
    assert loc.fast_mvc_root() == mvc


def test_list_existing_template_items(tmp_path: Path) -> None:
    pkg = tmp_path / "fastx_cli"
    pkg.mkdir()
    mvc = tmp_path / "fast_mvc"
    mvc.mkdir()
    (mvc / "app.py").write_text("# x")
    loc = FrameworkSourceLocator(package_dir=pkg)
    items = loc.list_existing_template_items()
    assert "app.py" in items
