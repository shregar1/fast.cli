"""Tests for GitHub workflows, venv, pre-commit, gitignore."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fast_cli.gitignore import GitignoreUpdater
from fast_cli.github_workflows import GitHubWorkflowsCopier
from fast_cli.precommit import PreCommitInstaller
from fast_cli.venv import VirtualEnvironmentService


def test_github_workflows_missing_templates(tmp_path: Path) -> None:
    c = GitHubWorkflowsCopier(repo_root=tmp_path)
    assert c.copy_into_project(tmp_path, {}) is False


def test_github_workflows_copies(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    tpl = root / "templates" / "github"
    tpl.mkdir(parents=True)
    (tpl / "ci.yml").write_text("n: {{PROJECT_NAME}}")
    c = GitHubWorkflowsCopier(repo_root=root)
    proj = tmp_path / "proj"
    proj.mkdir()
    ctx = {
        "project_name": "X",
        "project_slug": "x",
        "author_name": "a",
        "author_email": "a@a.co",
        "description": "d",
        "version": "1",
        "python_version": "3.11",
    }
    assert c.copy_into_project(proj, ctx) is True


def test_github_workflows_oserror(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    tpl = root / "templates" / "github"
    tpl.mkdir(parents=True)
    (tpl / "ci.yml").write_text("x")
    c = GitHubWorkflowsCopier(repo_root=root)
    proj = tmp_path / "proj"
    proj.mkdir()
    with patch("fast_cli.github_workflows.shutil.copy2", side_effect=OSError("e")):
        assert c.copy_into_project(proj, {}) is False


def test_gitignore_new_file(tmp_path: Path) -> None:
    GitignoreUpdater().update_for_venv(tmp_path, ".venv")


def test_gitignore_append(tmp_path: Path) -> None:
    g = tmp_path / ".gitignore"
    g.write_text("existing\n")
    GitignoreUpdater().update_for_venv(tmp_path, ".venv")


def test_gitignore_skip_if_present(tmp_path: Path) -> None:
    g = tmp_path / ".gitignore"
    g.write_text(".venv/\n")
    GitignoreUpdater().update_for_venv(tmp_path, ".venv")


def test_gitignore_oserror(tmp_path: Path) -> None:
    with patch.object(Path, "exists", return_value=False):
        with patch.object(Path, "write_text", side_effect=OSError("e")):
            GitignoreUpdater().update_for_venv(tmp_path, ".venv")


def test_venv_activation_commands() -> None:
    u, w = VirtualEnvironmentService().activation_commands("venv")
    assert "activate" in u


def test_venv_create_success(tmp_path: Path) -> None:
    with patch("fast_cli.venv.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        assert VirtualEnvironmentService().create(tmp_path, ".venv") is True


def test_venv_create_failure(tmp_path: Path) -> None:
    with patch("fast_cli.venv.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr="err")
        assert VirtualEnvironmentService().create(tmp_path, ".venv") is False


def test_venv_create_timeout(tmp_path: Path) -> None:
    import subprocess as sp

    with patch(
        "fast_cli.venv.subprocess.run",
        side_effect=sp.TimeoutExpired("x", 1),
    ):
        assert VirtualEnvironmentService().create(tmp_path, ".venv") is False


def test_venv_create_file_not_found(tmp_path: Path) -> None:
    with patch("fast_cli.venv.subprocess.run", side_effect=FileNotFoundError()):
        assert VirtualEnvironmentService().create(tmp_path, ".venv") is False


def test_venv_create_oserror(tmp_path: Path) -> None:
    with patch("fast_cli.venv.subprocess.run", side_effect=OSError("e")):
        assert VirtualEnvironmentService().create(tmp_path, ".venv") is False


def test_venv_install_no_requirements(tmp_path: Path) -> None:
    assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_venv_install_success(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pip\n")
    vdir = tmp_path / ".venv"
    if sys.platform == "win32":
        pip = vdir / "Scripts" / "pip.exe"
    else:
        pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    with patch("fast_cli.venv.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is True


def test_venv_install_failure(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("x\n")
    vdir = tmp_path / ".venv"
    if sys.platform == "win32":
        pip = vdir / "Scripts" / "pip.exe"
    else:
        pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    with patch("fast_cli.venv.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr="e")
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_precommit_missing_config(tmp_path: Path) -> None:
    assert PreCommitInstaller().install(tmp_path, ".venv") is False


def test_precommit_install_flow(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    vdir = tmp_path / ".venv"
    if sys.platform == "win32":
        pip = vdir / "Scripts" / "pip.exe"
        pc = vdir / "Scripts" / "pre-commit.exe"
    else:
        pip = vdir / "bin" / "pip"
        pc = vdir / "bin" / "pre-commit"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    pc.write_text("")
    pc.chmod(0o755)
    with patch("fast_cli.precommit.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        assert PreCommitInstaller().install(tmp_path, ".venv") is True


def test_precommit_pip_fail(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    vdir = tmp_path / ".venv"
    if sys.platform == "win32":
        pip = vdir / "Scripts" / "pip.exe"
    else:
        pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    with patch("fast_cli.precommit.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr="e")
        assert PreCommitInstaller().install(tmp_path, ".venv") is False


def test_precommit_install_cmd_fail(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    vdir = tmp_path / ".venv"
    if sys.platform == "win32":
        pip = vdir / "Scripts" / "pip.exe"
        pc = vdir / "Scripts" / "pre-commit.exe"
    else:
        pip = vdir / "bin" / "pip"
        pc = vdir / "bin" / "pre-commit"
    pip.parent.mkdir(parents=True)
    for p in (pip, pc):
        p.write_text("")
        p.chmod(0o755)
    calls = []

    def side_effect(cmd, **kw):  # noqa: ANN001
        calls.append(cmd)
        if "install" in cmd and "pre-commit" in str(cmd[0]):
            return MagicMock(returncode=1, stderr="bad")
        return MagicMock(returncode=0)

    with patch("fast_cli.precommit.subprocess.run", side_effect=side_effect):
        assert PreCommitInstaller().install(tmp_path, ".venv") is False
