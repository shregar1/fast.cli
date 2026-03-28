"""Tests targeting remaining uncovered lines (push total ≥ 99%)."""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fast_cli.app import cli
from fast_cli.commands import commit_history_setup as chs


def test_hook_present_skips_non_dict_repo() -> None:
    data = {"repos": ["not-a-dict"]}
    assert chs._hook_already_present(data) is False


def test_ensure_returns_false_when_hook_present() -> None:
    data = {"repos": [{"repo": "local", "hooks": [{"id": "git-log-recorder"}]}]}
    assert chs._ensure_local_git_log_hook(data) is False


def test_ensure_hook_merges_when_hooks_not_list() -> None:
    data = {"repos": [{"repo": "local", "hooks": None}]}
    assert chs._ensure_local_git_log_hook(data) is True
    assert isinstance(data["repos"][0]["hooks"], list)


def test_write_config_yaml_list_root(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("- item\n")
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w or "already" in desc or "unchanged" in desc


def test_write_config_unchanged_branch(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("repos: []\n")
    with patch.object(chs, "_ensure_local_git_log_hook", return_value=False):
        w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert not w and desc == "unchanged"


def test_dump_yaml_adds_trailing_newline() -> None:
    with patch("fast_cli.commands.commit_history_setup.yaml.dump", return_value="x: 1"):
        assert chs._dump_yaml({"x": 1}).endswith("\n")


def test_install_hooks_nonzero_exit(git_repo: Path) -> None:
    with patch("fast_cli.commands.commit_history_setup.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=1, stderr="e"),
            MagicMock(returncode=0, stderr=""),
        ]
        ok, err = chs._install_pre_commit_hooks(git_repo)
        assert not ok and err


def test_install_hooks_timeout(git_repo: Path) -> None:
    with patch(
        "fast_cli.commands.commit_history_setup.subprocess.run",
        side_effect=subprocess.TimeoutExpired("p", 1),
    ):
        ok, err = chs._install_pre_commit_hooks(git_repo)
        assert not ok and "timed out" in (err or "")


def test_setup_commit_log_success_install(git_repo: Path) -> None:
    with patch(
        "fast_cli.commands.commit_history_setup._install_pre_commit_hooks",
        return_value=(True, None),
    ):
        r = CliRunner().invoke(cli, ["setup-commit-log", "-C", str(git_repo)])
        assert r.exit_code == 0


def test_setup_commit_log_idempotent_info(git_repo: Path) -> None:
    CliRunner().invoke(cli, ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)])
    r = CliRunner().invoke(cli, ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)])
    assert r.exit_code == 0


def test_db_reset_click_cancel_first(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        r = runner.invoke(cli, ["db", "reset"], input="n\n")
        assert r.exit_code == 0


def test_db_reset_click_wrong_confirm_text(alembic_ready: Path) -> None:
    runner = CliRunner()
    with patch("fast_cli.commands.db_cmd.HAS_QUESTIONARY", False):
        r = runner.invoke(cli, ["db", "reset", "--no-seed"], input="y\nNOPE\n")
        assert r.exit_code == 0


def test_github_no_yaml_files(tmp_path: Path) -> None:
    from fast_cli.github_workflows import GitHubWorkflowsCopier

    root = tmp_path / "r"
    (root / "templates" / "github").mkdir(parents=True)
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
    assert c.copy_into_project(proj, ctx) is False


def test_precommit_pip_oserror(tmp_path: Path) -> None:
    from fast_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".git").mkdir()
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    with patch("fast_cli.precommit.subprocess.run", side_effect=OSError("e")):
        assert PreCommitInstaller().install(tmp_path, ".venv") is False


def test_precommit_git_init_when_no_dotgit(tmp_path: Path) -> None:
    from fast_cli.precommit import PreCommitInstaller

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    vdir = tmp_path / ".venv"
    pip = vdir / "bin" / "pip"
    pc = vdir / "bin" / "pre-commit"
    pip.parent.mkdir(parents=True)
    pip.write_text("")
    pc.write_text("")
    with patch("fast_cli.precommit.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        assert PreCommitInstaller().install(tmp_path, ".venv") is True


def test_cache_invalidate_new_loop() -> None:
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
    import sys

    sys.modules["fast_caching"] = types.ModuleType("fast_caching")
    sys.modules["fast_caching.src"] = types.ModuleType("fast_caching.src")
    sys.modules["fast_caching.src.fast_caching"] = inner
    try:
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            assert CliRunner().invoke(cli, ["cache", "invalidate", "x"]).exit_code == 0
    finally:
        for k in list(sys.modules):
            if k == "fast_caching" or k.startswith("fast_caching."):
                del sys.modules[k]


def test_tasks_status_with_error_field() -> None:
    import types

    res = MagicMock()
    res.task_id = "1"
    res.status = "failed"
    res.timestamp = "t"
    res.result = None
    res.error = "boom"

    async def get_result(_: str):
        return res

    fake = types.ModuleType("fast_platform.src.task")
    ft = MagicMock()
    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    import sys

    sys.modules["fast_platform"] = types.ModuleType("fast_platform")
    sys.modules["fast_platform.src"] = types.ModuleType("fast_platform.src")
    sys.modules["fast_platform.src.task"] = fake
    try:
        assert CliRunner().invoke(cli, ["tasks", "status", "id"]).exit_code == 0
    finally:
        for k in ("fast_platform.src.task", "fast_platform.src", "fast_platform"):
            sys.modules.pop(k, None)


def test_tasks_dashboard_new_event_loop() -> None:
    fake = types.ModuleType("fast_platform.src.task")
    fake.TaskRegistry = MagicMock()
    fake.TaskRegistry.all_tasks.return_value = {}
    ft = MagicMock()

    async def get_result(_n: str):
        return None

    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    sys.modules["fast_platform"] = types.ModuleType("fast_platform")
    sys.modules["fast_platform.src"] = types.ModuleType("fast_platform.src")
    sys.modules["fast_platform.src.task"] = fake
    try:
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            with patch("fast_cli.commands.tasks_cmd.time.sleep", side_effect=KeyboardInterrupt):
                assert CliRunner().invoke(cli, ["tasks", "dashboard"]).exit_code == 0
    finally:
        for k in ("fast_platform.src.task", "fast_platform.src", "fast_platform"):
            sys.modules.pop(k, None)


def test_run_basic_inner_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fast_cli.paths import FrameworkSourceLocator

    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.py").write_text("x")
    with patch("fast_cli.project_generation.HAS_QUESTIONARY", False):
        with patch(
            "fast_cli.project_generation.click.prompt",
            side_effect=["p", str(tmp_path / "o"), "A", "a@a.co", "d", "0.1.0", "n"],
        ):
            with patch.object(FrameworkSourceLocator, "fast_mvc_root", return_value=src):
                with patch.object(
                    FrameworkSourceLocator,
                    "list_existing_template_items",
                    return_value=["f.py"],
                ):
                    with patch(
                        "fast_cli.project_generation.shutil.copy2",
                        side_effect=RuntimeError("inner"),
                    ):
                        r = CliRunner().invoke(cli, ["generate"])
                        assert r.exit_code != 0
