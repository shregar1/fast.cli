"""Targeted tests to raise overall line coverage."""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.bundled import git_log_recorder as glr
from fastx_cli.commands import commit_history_setup as chs
from fastx_cli.gitignore import GitignoreUpdater
from fastx_cli.paths import FrameworkSourceLocator
from fastx_cli.project_generation import ProjectGenerationOrchestrator
from fastx_cli.venv import VirtualEnvironmentService


def test_bundled_main_no_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir("/")
    with patch("fastx_cli.bundled.git_log_recorder.get_repo_root", return_value=None):
        glr.main()


def test_bundled_main_get_git_none(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    monkeypatch.chdir(git_repo)
    with patch("fastx_cli.bundled.git_log_recorder.get_git_info", return_value=None):
        glr.main()


def test_bundled_legacy_rename_oserror(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "GIT_METADATA.json").write_text("[]")
    with patch.object(Path, "rename", side_effect=OSError("e")):
        glr.main()


def test_bundled_run_as_main(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    root = Path(__file__).resolve().parents[1]
    p = root / "fastx_cli" / "bundled" / "git_log_recorder.py"
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
            "import fastx_cli.bundled.git_log_recorder as g; g.main()",
        ],
        check=True,
        env=env,
    )


def test_template_write_oserror(tmp_path: Path) -> None:
    from fastx_cli.template_engine import TemplateRenderer

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
    from fastx_cli.file_copy import ProjectCopier
    from fastx_cli.template_engine import TemplateRenderer

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
    with patch("fastx_cli.file_copy.shutil.copy2", side_effect=OSError("e")):
        ProjectCopier(TemplateRenderer()).copy_with_progress(src, tgt, ["f.py"], ctx)


def test_github_process_file_error(tmp_path: Path) -> None:
    from fastx_cli.github_workflows import GitHubWorkflowsCopier

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
        "fastx_cli.github_workflows.TemplateRenderer.process_file",
        side_effect=OSError("e"),
    ):
        assert c.copy_into_project(proj, ctx) is False


def test_precommit_windows_paths(tmp_path: Path) -> None:
    from fastx_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".git").mkdir()
    vdir = tmp_path / ".venv"
    pip = vdir / "Scripts" / "pip.exe"
    pc = vdir / "Scripts" / "pre-commit.exe"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pc.write_text("")
    with patch("fastx_cli.precommit.sys.platform", "win32"):
        with patch("fastx_cli.precommit.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            PreCommitInstaller().install(tmp_path, ".venv")


def test_precommit_chdir_oserror(tmp_path: Path) -> None:
    from fastx_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".git").mkdir()
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pc = vdir / "bin" / "pre-commit"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pc.write_text("")
    with patch("fastx_cli.precommit.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        with patch(
            "fastx_cli.precommit.os.chdir",
            side_effect=[OSError("e"), None],
        ):
            assert PreCommitInstaller().install(tmp_path, ".venv") is False


def test_venv_win32_pip(tmp_path: Path) -> None:
    from fastx_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    with patch("fastx_cli.venv.sys.platform", "win32"):
        vdir = tmp_path / ".venv"
        pip = vdir / "Scripts" / "pip.exe"
        pip.parent.mkdir(parents=True)
        pip.write_text("")
        with patch("fastx_cli.venv.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            VirtualEnvironmentService().install_requirements(tmp_path, ".venv")


def test_commit_history_install_timeout(tmp_path: Path) -> None:
    import subprocess as sp

    with patch(
        "fastx_cli.commands.commit_history_setup.subprocess.run",
        side_effect=sp.TimeoutExpired("p", 1),
    ):
        ok, err = chs._install_pre_commit_hooks(tmp_path)
        assert not ok


def test_commit_history_merge_local_bad_hooks_type(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("repos:\n  - repo: local\n    hooks: null\n")
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w


def test_app_main_block() -> None:
    import runpy

    root = Path(__file__).resolve().parents[1]
    p = root / "fastx_cli" / "app.py"
    with patch.object(sys, "argv", ["fast", "--help"]):
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(p), run_name="__main__")
        assert exc.value.code == 0


def test_cache_clear_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_caching" or name.startswith("fastx_caching."):
            raise ImportError("no fastx_caching")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_caching" or k.startswith("fastx_caching."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["cache", "clear"])
    assert r.exit_code == 0
    assert "fastx_caching" in r.output.lower()


def test_cache_invalidate_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_caching" or name.startswith("fastx_caching."):
            raise ImportError("no fastx_caching")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_caching" or k.startswith("fastx_caching."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["cache", "invalidate", "tag1"])
    assert r.exit_code == 0
    assert "fastx_caching" in r.output.lower()


def test_tasks_dashboard_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    m = types.ModuleType("fastx_platform.src.task")

    class TaskRegistry:
        @staticmethod
        def all_tasks() -> dict[str, object]:
            return {"t1": object()}

    class Backend:
        async def get_result(self, name: str) -> MagicMock:
            r = MagicMock()
            r.status = "ok"
            return r

    ft = MagicMock()
    ft.backend = Backend()
    m.TaskRegistry = TaskRegistry
    m.fastx_tasks = ft
    monkeypatch.setitem(sys.modules, "fastx_platform", types.ModuleType("fastx_platform"))
    monkeypatch.setitem(sys.modules, "fastx_platform.src", types.ModuleType("fastx_platform.src"))
    monkeypatch.setitem(sys.modules, "fastx_platform.src.task", m)
    _sleep_calls: list[int] = []

    def _sleep(_: float) -> None:
        _sleep_calls.append(1)
        if len(_sleep_calls) >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr("fastx_cli.commands.tasks_cmd.time.sleep", _sleep)
    r = CliRunner().invoke(cli, ["tasks", "dashboard", "-r", "10000"])
    assert r.exit_code == 0


def test_run_interactive_email_key_sets_author_email_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("questionary")
    monkeypatch.setattr(
        "fastx_cli.project_generation.load_user_defaults",
        lambda: {"email": "only@e.co"},
    )
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
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

            def text_side(*a: object, **k: object) -> MagicMock:
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
            assert any(
                getattr(c, "kwargs", {}).get("default") == "only@e.co"
                for c in q.text.call_args_list
            )


def test_run_basic_email_default_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "fastx_cli.project_generation.load_user_defaults",
        lambda: {"email": "only@email.com"},
    )
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", False):
        with patch.object(
            FrameworkSourceLocator,
            "fastx_mvc_root",
            side_effect=RuntimeError("boom"),
        ):

            def fake_prompt(msg: str, default: str | None = None, **kwargs: object) -> str:
                if "Project name" in msg:
                    return "p"
                if "Target directory" in msg:
                    return str(tmp_path / "o")
                if "Author name" in msg:
                    return "A"
                if "email" in msg.lower():
                    assert default == "only@email.com"
                    return "only@email.com"
                if "description" in msg.lower():
                    return "d"
                if "version" in msg or "Initial" in msg:
                    return "0.1.0"
                raise AssertionError(msg)

            def fake_confirm(msg: str, default: bool = True) -> bool:
                if "virtual environment" in msg.lower():
                    return False
                raise AssertionError(msg)

            with patch("fastx_cli.project_generation.click.prompt", side_effect=fake_prompt):
                with patch("fastx_cli.project_generation.click.confirm", side_effect=fake_confirm):
                    r = CliRunner().invoke(cli, ["generate"])
                    assert r.exit_code != 0


def test_run_interactive_full_wizard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("questionary")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
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
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
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
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", True):
        with patch("fastx_cli.project_generation.questionary") as q:
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
    with patch("fastx_cli.project_generation.HAS_QUESTIONARY", False):
        with patch.object(FrameworkSourceLocator, "fastx_mvc_root", return_value=src):
            with patch.object(
                FrameworkSourceLocator,
                "list_existing_template_items",
                return_value=["f.py"],
            ):
                with patch(
                    "fastx_cli.project_generation.GitHubWorkflowsCopier.copy_into_project",
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
        "fastx_cli.commands.add_cmd.resolve_fastmvc_project_root", return_value=root
    ):
        with patch("fastx_cli.commands.add_cmd.HAS_QUESTIONARY", False):
            r = runner.invoke(
                cli,
                ["add", "resource", "--folder", "u", "--resource", "g", "--version", "2"],
            )
            assert r.exit_code == 0


def test_docs_skips_init_files(tmp_path: Path) -> None:
    from fastx_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

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
    from fastx_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "proj"
    root.mkdir()
    (root / "docs" / "api").mkdir(parents=True)
    eco = tmp_path / "fastx_pkg"
    eco.mkdir()
    (eco / "bare.py").write_text("#")
    MkdocsStyleReferenceGenerator(root)._write_ecosystem()


def test_cache_clear_returns_false() -> None:
    import types

    inner = types.ModuleType("fastx_caching.src.fastx_caching")

    class Backend:
        async def clear(self) -> bool:
            return False

    class FC:
        backend = Backend()

        async def invalidate(self, tags: list) -> int:
            return 0

    inner.fastx_cache = FC()
    sys.modules["fastx_caching"] = types.ModuleType("fastx_caching")
    sys.modules["fastx_caching.src"] = types.ModuleType("fastx_caching.src")
    sys.modules["fastx_caching.src.fastx_caching"] = inner
    try:
        assert CliRunner().invoke(cli, ["cache", "clear"]).exit_code == 0
    finally:
        for k in list(sys.modules):
            if k == "fastx_caching" or k.startswith("fastx_caching."):
                del sys.modules[k]


def test_venv_install_timeout(tmp_path: Path) -> None:
    from fastx_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    import subprocess as sp

    with patch(
        "fastx_cli.venv.subprocess.run",
        side_effect=sp.TimeoutExpired("p", 1),
    ):
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_venv_install_oserror(tmp_path: Path) -> None:
    from fastx_cli.venv import VirtualEnvironmentService

    (tmp_path / "requirements.txt").write_text("x")
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pip.chmod(0o755)
    with patch("fastx_cli.venv.subprocess.run", side_effect=OSError("e")):
        assert VirtualEnvironmentService().install_requirements(tmp_path, ".venv") is False


def test_github_mkdir_oserror(tmp_path: Path) -> None:
    from fastx_cli.github_workflows import GitHubWorkflowsCopier

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
    from fastx_cli.commands.docs_cmd import MkdocsStyleReferenceGenerator

    root = tmp_path / "proj"
    root.mkdir()
    (root / "docs" / "api").mkdir(parents=True)
    eco = tmp_path / "fastx_skip"
    eco.mkdir()
    (eco / ".hidden").mkdir()
    (eco / "__pycache__").mkdir()
    (eco / "tests").mkdir()
    MkdocsStyleReferenceGenerator(root)._write_ecosystem()


def test_cache_clear_new_event_loop(tmp_path: Path) -> None:
    import types

    inner = types.ModuleType("fastx_caching.src.fastx_caching")

    class Backend:
        async def clear(self) -> bool:
            return True

    class FC:
        backend = Backend()

        async def invalidate(self, tags: list) -> int:
            return 1

    inner.fastx_cache = FC()
    sys.modules["fastx_caching"] = types.ModuleType("fastx_caching")
    sys.modules["fastx_caching.src"] = types.ModuleType("fastx_caching.src")
    sys.modules["fastx_caching.src.fastx_caching"] = inner
    try:
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            assert CliRunner().invoke(cli, ["cache", "clear"]).exit_code == 0
            assert CliRunner().invoke(cli, ["cache", "invalidate", "t"]).exit_code == 0
    finally:
        for k in list(sys.modules):
            if k == "fastx_caching" or k.startswith("fastx_caching."):
                del sys.modules[k]


def test_tasks_worker_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_platform" or name.startswith("fastx_platform."):
            raise ImportError("no fastx_platform")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_platform" or k.startswith("fastx_platform."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["tasks", "worker"])
    assert r.exit_code == 0
    assert "fastx_tasks" in r.output.lower()


def test_tasks_list_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_platform" or name.startswith("fastx_platform."):
            raise ImportError("no fastx_platform")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_platform" or k.startswith("fastx_platform."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["tasks", "list"])
    assert r.exit_code == 0
    assert "fastx_tasks" in r.output.lower()


def test_tasks_status_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_platform" or name.startswith("fastx_platform."):
            raise ImportError("no fastx_platform")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_platform" or k.startswith("fastx_platform."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["tasks", "status", "tid"])
    assert r.exit_code == 0
    assert "fastx_tasks" in r.output.lower()


def test_tasks_dashboard_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastx_platform" or name.startswith("fastx_platform."):
            raise ImportError("no fastx_platform")
        return real_import(name, *args, **kwargs)

    for k in list(sys.modules):
        if k == "fastx_platform" or k.startswith("fastx_platform."):
            del sys.modules[k]
    monkeypatch.setattr(builtins, "__import__", fake_import)
    r = CliRunner().invoke(cli, ["tasks", "dashboard"])
    assert r.exit_code == 0
    assert "fastx_tasks" in r.output.lower()
