"""Tests for copier, bootstrap, and decimate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.commands.decimate_cmd import ArtifactDecimator
from fastx_cli.file_copy import ProjectCopier, template_copytree_ignore
from fastx_cli.project_setup import ProjectBootstrap


def _ctx() -> dict:
    return {
        "project_name": "P",
        "project_slug": "p",
        "author_name": "A",
        "author_email": "a@b.co",
        "description": "D",
        "version": "1.0.0",
        "python_version": "3.11",
    }


def test_template_copytree_ignore_omits_tests_framework(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    (tests_root / "framework").mkdir()
    (tests_root / "framework" / "internal.py").write_text("#")
    (tests_root / "dev").mkdir()
    (tests_root / "dev" / "sample.py").write_text("#")

    ign = template_copytree_ignore(tests_root)
    skipped = ign(str(tests_root), ["framework", "dev", "__pycache__"])
    assert "framework" in skipped
    assert "dev" not in skipped


def test_template_copytree_ignore_does_not_skip_framework_elsewhere(tmp_path: Path) -> None:
    core = tmp_path / "core"
    core.mkdir()
    (core / "framework").mkdir()
    ign = template_copytree_ignore(core)
    skipped = ign(str(core), ["framework", "x.py"])
    assert "framework" not in skipped


def test_project_copier_copy_dir_and_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("{{PROJECT_NAME}}")
    (src / "pkg").mkdir()
    (src / "pkg" / "x.py").write_text("#")
    copier = ProjectCopier()
    tgt = tmp_path / "tgt"
    tgt.mkdir()
    n = copier.copy_with_progress(src, tgt, ["app.py", "pkg"], _ctx())
    assert n == 2
    assert (tgt / "app.py").read_text() == "P"


def test_project_copier_skips_dot_git(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("x")
    copier = ProjectCopier()
    tgt = tmp_path / "tgt"
    tgt.mkdir()
    n = copier.copy_with_progress(src, tgt, [".git"], _ctx())
    assert n == 0


def test_project_copier_oserror(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "missing").mkdir()
    copier = ProjectCopier()
    tgt = tmp_path / "tgt"
    tgt.mkdir()
    with patch("fastx_cli.file_copy.shutil.copy2", side_effect=OSError("e")):
        copier.copy_with_progress(src, tgt, ["missing"], _ctx())


def test_bootstrap_generate_env(tmp_path: Path) -> None:
    b = ProjectBootstrap()
    (tmp_path / ".env.example").write_text("X={{PROJECT_NAME}}")
    assert b.generate_env_file(tmp_path, _ctx()) is True
    assert (tmp_path / ".env").read_text().strip()


def test_bootstrap_generate_env_exists(tmp_path: Path) -> None:
    b = ProjectBootstrap()
    (tmp_path / ".env.example").write_text("x")
    (tmp_path / ".env").write_text("secret")
    assert b.generate_env_file(tmp_path, _ctx()) is False


def test_bootstrap_generate_env_copy_error(tmp_path: Path) -> None:
    b = ProjectBootstrap()
    (tmp_path / ".env.example").write_text("x")
    with patch("fastx_cli.project_setup.shutil.copy2", side_effect=OSError("e")):
        assert b.generate_env_file(tmp_path, _ctx()) is False


def test_bootstrap_create_structure(tmp_path: Path) -> None:
    ProjectBootstrap().create_project_structure(tmp_path, {})


def test_bootstrap_update_pyproject(tmp_path: Path) -> None:
    b = ProjectBootstrap()
    (tmp_path / "pyproject.toml").write_text(
        'name = "old"\ndescription = "old"\nauthors = [old]\nmaintainers = [old]\n'
    )
    b.update_pyproject_toml(
        tmp_path,
        {
            "project_slug": "newp",
            "description": "newd",
            "author_name": "An",
            "author_email": "e@e.co",
        },
    )


def test_bootstrap_update_pyproject_missing(tmp_path: Path) -> None:
    ProjectBootstrap().update_pyproject_toml(tmp_path, {"project_slug": "x"})


def test_bootstrap_update_pyproject_io_error(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('name = "x"\n')
    with patch.object(Path, "read_text", side_effect=OSError("e")):
        ProjectBootstrap().update_pyproject_toml(
            tmp_path,
            {
                "project_slug": "n",
                "description": "d",
                "author_name": "a",
                "author_email": "b@c",
            },
        )


def test_decimate_clean(tmp_path: Path) -> None:
    ArtifactDecimator("python", tmp_path).run()


def test_decimate_removes_pycache(tmp_path: Path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"")
    ArtifactDecimator("python", tmp_path).run()


def test_decimate_unknown_language(tmp_path: Path) -> None:
    ArtifactDecimator("unknown", tmp_path).run()


def test_decimate_pycache_alias(tmp_path: Path) -> None:
    ArtifactDecimator("pycache", tmp_path).run()


def test_decimate_delete_failure(tmp_path: Path) -> None:
    d = tmp_path / "__pycache__"
    d.mkdir()
    with patch("fastx_cli.commands.decimate_cmd.shutil.rmtree", side_effect=OSError("e")):
        ArtifactDecimator("python", tmp_path).run()


def test_decimate_cli(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["decimate", "python", "."])
    assert r.exit_code == 0
