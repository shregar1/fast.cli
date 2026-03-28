"""Targeted tests to raise overall line coverage."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from fast_cli.app import cli
from fast_cli.bundled import git_log_recorder as glr
from fast_cli.commands import commit_history_setup as chs
from fast_cli.gitignore import GitignoreUpdater
from fast_cli.paths import FrameworkSourceLocator
from fast_cli.project_generation import ProjectGenerationOrchestrator
from fast_cli.venv import VirtualEnvironmentService


def test_bundled_main_no_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir("/")
    with patch("fast_cli.bundled.git_log_recorder.get_repo_root", return_value=None):
        glr.main()


def test_bundled_main_get_git_none(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    monkeypatch.chdir(git_repo)
    with patch("fast_cli.bundled.git_log_recorder.get_git_info", return_value=None):
        glr.main()


def test_bundled_legacy_rename_oserror(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "GIT_METADATA.json").write_text("[]")
    with patch.object(Path, "rename", side_effect=OSError("e")):
        glr.main()


def test_bundled_run_as_main(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    root = Path(__file__).resolve().parents[1]
    p = root / "fast_cli" / "bundled" / "git_log_recorder.py"
    monkeypatch.chdir(git_repo)
    runpy.run_path(str(p), run_name="__main__")


def test_bundled_module_main(git_repo: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root), "GIT_REPO": str(git_repo)}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; os.chdir(os.environ['GIT_REPO']); "
            "import fast_cli.bundled.git_log_recorder as g; g.main()",
        ],
        check=True,
        env=env,
    )


def test_template_write_oserror(tmp_path: Path) -> None:
    from fast_cli.template_engine import TemplateRenderer

    p = tmp_path / "f.txt"
    p.write_text("{{PROJECT_NAME}}")
    with patch.object(Path, "write_text", side_effect=OSError("e")):
        TemplateRenderer().process_file(
            p,
            {
                "project_name": "p",
                "project_slug": "p",
                "author_name": "a",
                "author_email": "a@a.co",
                "description": "d",
                "version": "1",
                "python_version": "3.11",
            },
        )


def test_file_copy_oserror_on_copy2(tmp_path: Path) -> None:
    from fast_cli.file_copy import ProjectCopier
    from fast_cli.template_engine import TemplateRenderer

    src = tmp_path / "s"
    src.mkdir()
    (src / "f.py").write_text("x")
    tgt = tmp_path / "t"
    tgt.mkdir()
    ctx = {
        "project_name": "p",
        "project_slug": "p",
        "author_name": "a",
        "author_email": "a@a.co",
        "description": "d",
        "version": "1",
        "python_version": "3.11",
    }
    with patch("fast_cli.file_copy.shutil.copy2", side_effect=OSError("e")):
        ProjectCopier(TemplateRenderer()).copy_with_progress(src, tgt, ["f.py"], ctx)


def test_github_process_file_error(tmp_path: Path) -> None:
    from fast_cli.github_workflows import GitHubWorkflowsCopier

    root = tmp_path / "r"
    tpl = root / "templates" / "github"
    tpl.mkdir(parents=True)
    (tpl / "ci.yml").write_text("x")
    ctx = {
        "project_name": "X",
        "project_slug": "x",
        "author_name": "a",
        "author_email": "a@b.co",
        "description": "d",
        "version": "1",
        "python_version": "3.11",
    }
    c = GitHubWorkflowsCopier(repo_root=root)
    proj = tmp_path / "p"
    proj.mkdir()
    with patch(
        "fast_cli.github_workflows.TemplateRenderer.process_file",
        side_effect=OSError("e"),
    ):
        assert c.copy_into_project(proj, ctx) is False


def test_precommit_windows_paths(tmp_path: Path) -> None:
    from fast_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".git").mkdir()
    vdir = tmp_path / ".venv"
    pip = vdir / "Scripts" / "pip.exe"
    pc = vdir / "Scripts" / "pre-commit.exe"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pc.write_text("")
    with patch("fast_cli.precommit.sys.platform", "win32"):
        with patch("fast_cli.precommit.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            PreCommitInstaller().install(tmp_path, ".venv")


def test_precommit_chdir_oserror(tmp_path: Path) -> None:
    from fast_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".git").mkdir()
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pc = vdir / "bin" / "pre-commit"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pc.write_text("")
    with patch("fast_cli.precommit.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        with patch(
            "fast_cli.precommit.os.chdir",
            side_effect=[OSError("e"), None],
        ):
            assert PreCommitInstaller().install(tmp_path, ".venv") is False


def test_venv_win32_pip(tmp_path: Path) -> None:
    from fast_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    with patch("fast_cli.venv.sys.platform", "win32"):
        vdir = tmp_path / ".venv"
        pip = vdir / "Scripts" / "pip.exe"
        pip.parent.mkdir(parents=True)
        pip.write_text("")
        with patch("fast_cli.venv.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            VirtualEnvironmentService().install_requirements(tmp_path, ".venv")


def test_commit_history_install_timeout(tmp_path: Path) -> None:
    import subprocess as sp

    with patch(
        "fast_cli.commands.commit_history_setup.subprocess.run",
        side_effect=sp.TimeoutExpired("p", 1),
    ):
        ok, err = chs._install_pre_commit_hooks(tmp_path)
        assert not ok


def test_commit_history_merge_local_bad_hooks_type(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("repos:\n  - repo: local\n    hooks: null\n")
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w


def test_run_interactive_full_wizard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("questionary")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fast_cli.project_generation.questionary") as q:
            texts = iter(
                [
                    "projname",
                    str(out),
                    "Author",
                    "a@b.co",
                    "desc",
                    "0.1.0",
                    ".venv",
                ]
            )

            def text_side(*a, **k):
                m = MagicMock()
                m.ask.return_value = next(texts)
                return m

            q.text.side_effect = text_side
            conf = MagicMock()
            conf.ask.side_effect = [True, True, True, True]
            q.confirm.return_value = conf
            q.select.return_value.ask.return_value = "3.11"
            orch = ProjectGenerationOrchestrator()
            with patch.object(orch, "_execute_pipeline"):
                orch.run_interactive()


def test_run_interactive_cancel_final_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("questionary")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fast_cli.project_generation.questionary") as q:
            texts = iter(
                [
                    "projname",
                    str(out),
                    "A",
                    "a@b.co",
                    "d",
                    "0.1.0",
                    ".venv",
                ]
            )

            def text_side(*a, **k):
                m = MagicMock()
                m.ask.return_value = next(texts)
                return m

            q.text.side_effect = text_side
            conf = MagicMock()
            conf.ask.side_effect = [True, True, True, False]
            q.confirm.return_value = conf
            q.select.return_value.ask.return_value = "3.11"
            ProjectGenerationOrchestrator().run_interactive()


def test_run_interactive_execute_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("questionary")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fast_cli.project_generation.questionary") as q:
            texts = iter(
                [
                    "projname",
                    str(out),
                    "A",
                    "a@b.co",
                    "d",
                    "0.1.0",
                    ".venv",
                ]
            )

            def text_side(*a, **k):
                m = MagicMock()
                m.ask.return_value = next(texts)
                return m

            q.text.side_effect = text_side
            conf = MagicMock()
            conf.ask.side_effect = [True, True, True, True]
            q.confirm.return_value = conf
            q.select.return_value.ask.return_value = "3.11"
            orch = ProjectGenerationOrchestrator()
            with patch.object(orch, "_execute_pipeline", side_effect=RuntimeError("fail")):
                with pytest.raises(click.Abort):
                    orch.run_interactive()


def test_run_basic_venv_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.py").write_text("x")
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", False):
        with patch.object(FrameworkSourceLocator, "fast_mvc_root", return_value=src):
            with patch.object(
                FrameworkSourceLocator,
                "list_existing_template_items",
                return_value=["f.py"],
            ):
                with patch(
                    "fast_cli.project_generation.GitHubWorkflowsCopier.copy_into_project",
                    return_value=False,
                ):
                    with patch.object(VirtualEnvironmentService, "create", return_value=True):
                        with patch.object(GitignoreUpdater, "update_for_venv"):
                            with patch.object(
                                VirtualEnvironmentService,
                                "install_requirements",
                                return_value=True,
                            ):
                                inp = "\n".join(
                                    [
                                        "p",
                                        str(tmp_path / "o"),
                                        "A",
                                        "a@a.co",
                                        "d",
                                        "0.1.0",
                                        "y",
                                        ".venv",
                                        "y",
                                    ]
                                )
                                r = CliRunner().invoke(cli, ["generate"], input=inp)
                                assert r.exit_code == 0


def test_add_resource_version_prefix(tmp_path: Path) -> None:
    root = tmp_path / "app"
    (root / "abstractions").mkdir(parents=True)
    (root / "abstractions" / "controller.py").write_text("#")
    runner = CliRunner()
    with patch(
        "fast_cli.commands.add_cmd.resolve_fastmvc_project_root", return_value=root
    ):
        with patch("fast_cli.commands.add_cmd.HAS_QUESTIONARY", False):
            r = runner.invoke(
                cli,
                ["add", "resource", "--folder", "u", "--resource", "g", "--version", "2"],
            )
            assert r.exit_code == 0


def test_docs_skips_init_files(tmp_path: Path) -> None:
    from fast_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "p"
    (root / "apis" / "v1" / "users").mkdir(parents=True)
    (root / "apis" / "v1" / "users" / "__init__.py").write_text("#")
    (root / "apis" / "v1" / "users" / "get.py").write_text("#")
    (root / "dtos" / "requests" / "apis" / "v1" / "users").mkdir(parents=True)
    (root / "dtos" / "requests" / "apis" / "v1" / "users" / "__init__.py").write_text("#")
    (root / "dtos" / "requests" / "apis" / "v1" / "users" / "dto.py").write_text("#")
    (root / "docs" / "api").mkdir(parents=True)
    ep = root / "docs" / "api" / "endpoints.md"
    dp = root / "docs" / "api" / "dtos.md"
    g = MkdocsStyleReferenceGenerator(root)
    g._write_api_endpoints(ep)
    g._write_dto_reference(dp)


def test_docs_ecosystem_no_src(tmp_path: Path) -> None:
    from fast_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "proj"
    root.mkdir()
    (root / "docs" / "api").mkdir(parents=True)
    eco = tmp_path / "fast_pkg"
    eco.mkdir()
    (eco / "bare.py").write_text("#")
    MkdocsStyleReferenceGenerator(root)._write_ecosystem()


def test_cache_clear_returns_false() -> None:
    import types

    inner = types.ModuleType("fast_caching.src.fast_caching")

    class Backend:
        async def clear(self) -> bool:
            return False

    class FC:
        backend = Backend()

        async def invalidate(self, tags: list) -> int:
            return 0

    inner.fast_cache = FC()
    sys.modules["fast_caching"] = types.ModuleType("fast_caching")
    sys.modules["fast_caching.src"] = types.ModuleType("fast_caching.src")
    sys.modules["fast_caching.src.fast_caching"] = inner
    try:
        assert CliRunner().invoke(cli, ["cache", "clear"]).exit_code == 0
    finally:
        for k in list(sys.modules):
            if k == "fast_caching" or k.startswith("fast_caching."):
                del sys.modules[k]


def test_venv_install_timeout(tmp_path: Path) -> None:
    from fast_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    import subprocess as sp

    with patch(
        "fast_cli.venv.subprocess.run",
        side_effect=sp.TimeoutExpired("p", 1),
    ):
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_venv_install_oserror(tmp_path: Path) -> None:
    from fast_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    with patch("fast_cli.venv.subprocess.run", side_effect=OSError("e")):
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_github_mkdir_oserror(tmp_path: Path) -> None:
    from fast_cli.github_workflows import GitHubWorkflowsCopier

    root = tmp_path / "r"
    tpl = root / "templates" / "github"
    tpl.mkdir(parents=True)
    (tpl / "ci.yml").write_text("x")
    ctx = {
        "project_name": "X",
        "project_slug": "x",
        "author_name": "a",
        "author_email": "a@b.co",
        "description": "d",
        "version": "1",
        "python_version": "3.11",
    }
    c = GitHubWorkflowsCopier(repo_root=root)
    proj = tmp_path / "p"
    proj.mkdir()
    real_mkdir = Path.mkdir

    def mkdir_side(self: Path, *a, **k):  # noqa: ANN002
        if ".github" in str(self):
            raise OSError("e")
        return real_mkdir(self, *a, **k)

    with patch.object(Path, "mkdir", mkdir_side):
        assert c.copy_into_project(proj, ctx) is False


def test_docs_ecosystem_skip_items(tmp_path: Path) -> None:
    from fast_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "proj"
    root.mkdir()
    (root / "docs" / "api").mkdir(parents=True)
    eco = tmp_path / "fast_skip"
    eco.mkdir()
    (eco / ".hidden").mkdir()
    (eco / "__pycache__").mkdir()
    (eco / "tests").mkdir()
    MkdocsStyleReferenceGenerator(root)._write_ecosystem()


def test_cache_clear_new_event_loop(tmp_path: Path) -> None:
    import types

    inner = types.ModuleType("fast_caching.src.fast_caching")

    class Backend:
        async def clear(self) -> bool:
            return True

    class FC:
        backend = Backend()

        async def invalidate(self, tags: list) -> int:
            return 1

    inner.fast_cache = FC()
    sys.modules["fast_caching"] = types.ModuleType("fast_caching")
    sys.modules["fast_caching.src"] = types.ModuleType("fast_caching.src")
    sys.modules["fast_caching.src.fast_caching"] = inner
    try:
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            assert CliRunner().invoke(cli, ["cache", "clear"]).exit_code == 0
            assert CliRunner().invoke(cli, ["cache", "invalidate", "t"]).exit_code == 0
    finally:
        for k in list(sys.modules):
            if k == "fast_caching" or k.startswith("fast_caching."):
                del sys.modules[k]
