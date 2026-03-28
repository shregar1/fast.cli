"""Tests for :mod:`fast_cli.commands.commit_history_setup`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from fast_cli.app import cli
from fast_cli.commands import commit_history_setup as chs


def test_repos_list_normalizes_non_list() -> None:
    data: dict = {"repos": None}
    r = chs._repos_list(data)
    assert r == []
    assert isinstance(data["repos"], list)


def test_hook_already_present_true() -> None:
    data = {
        "repos": [
            {
                "repo": "local",
                "hooks": [{"id": "git-log-recorder"}],
            }
        ]
    }
    assert chs._hook_already_present(data) is True


def test_ensure_local_git_log_merges_into_existing_local() -> None:
    data = {"repos": [{"repo": "local", "hooks": [{"id": "other"}]}]}
    assert chs._ensure_local_git_log_hook(data) is True
    hooks = data["repos"][0]["hooks"]
    assert any(h.get("id") == "git-log-recorder" for h in hooks)


def test_ensure_local_appends_new_local_repo() -> None:
    data = {"repos": []}
    assert chs._ensure_local_git_log_hook(data) is True
    assert data["repos"][-1]["repo"] == "local"


def test_write_pre_commit_creates_minimal(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w and desc == "created"
    loaded = yaml.safe_load(p.read_text())
    assert any(
        h.get("id") == "git-log-recorder"
        for r in loaded["repos"]
        for h in r.get("hooks", [])
    )


def test_write_pre_commit_with_common_hooks(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    w, _ = chs._write_pre_commit_config(p, with_common_hooks=True)
    assert w
    loaded = yaml.safe_load(p.read_text())
    assert len(loaded["repos"]) >= 2


def test_write_pre_commit_merge_existing(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("repos: []\n")
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w and desc == "updated"


def test_write_pre_commit_idempotent(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    chs._write_pre_commit_config(p, with_common_hooks=False)
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert not w and "already" in desc


def test_write_pre_commit_bad_yaml(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("{ bad")
    from click import ClickException

    with pytest.raises(ClickException):
        chs._write_pre_commit_config(p, with_common_hooks=False)


def test_install_pre_commit_hooks_success(tmp_path: Path) -> None:
    with patch("fast_cli.commands.commit_history_setup.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        ok, err = chs._install_pre_commit_hooks(tmp_path)
        assert ok and err is None
        assert run.call_count == 2


def test_install_pre_commit_hooks_missing_binary(tmp_path: Path) -> None:
    with patch("fast_cli.commands.commit_history_setup.subprocess.run") as run:
        run.side_effect = FileNotFoundError()
        ok, err = chs._install_pre_commit_hooks(tmp_path)
        assert not ok


def test_git_toplevel_none(tmp_path: Path) -> None:
    assert chs._git_toplevel(tmp_path / "nope") is None


def test_ensure_gitignore_appends_missing(tmp_path: Path) -> None:
    changed, added = chs._ensure_gitignore_entries(tmp_path)
    assert changed and set(added) == {
        "coverage_output.txt",
        "commit_history.json",
    }
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert chs.GITIGNORE_MARKER in text
    assert "coverage_output.txt" in text
    assert "commit_history.json" in text


def test_ensure_gitignore_idempotent(tmp_path: Path) -> None:
    chs._ensure_gitignore_entries(tmp_path)
    changed, added = chs._ensure_gitignore_entries(tmp_path)
    assert not changed and added == []


def test_ensure_gitignore_partial_existing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("coverage_output.txt\n", encoding="utf-8")
    changed, added = chs._ensure_gitignore_entries(tmp_path)
    assert changed and added == ["commit_history.json"]


def test_setup_commit_log_integration(git_repo: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(
        cli,
        ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)],
    )
    assert r.exit_code == 0
    assert (git_repo / "_maint" / "scripts" / "git_log_recorder.py").exists()


def test_setup_commit_log_not_git(tmp_path: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["setup-commit-log", "-C", str(tmp_path)])
    assert r.exit_code == 1


def test_setup_commit_log_bad_yaml_exits(git_repo: Path) -> None:
    (git_repo / ".pre-commit-config.yaml").write_text("{ bad")
    r = CliRunner().invoke(
        cli,
        ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)],
    )
    assert r.exit_code == 1


def test_setup_commit_log_chmod_oserror(git_repo: Path) -> None:
    real_chmod = Path.chmod

    def chmod_side(self: Path, *a, **k):  # noqa: ANN002
        if self.name == "git_log_recorder.py":
            raise OSError("e")
        return real_chmod(self, *a, **k)

    with patch.object(Path, "chmod", chmod_side):
        r = CliRunner().invoke(
            cli,
            ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)],
        )
        assert r.exit_code == 0


def test_setup_commit_log_install_hooks_fail(git_repo: Path) -> None:
    with patch(
        "fast_cli.commands.commit_history_setup._install_pre_commit_hooks",
        return_value=(False, "no pre-commit"),
    ):
        r = CliRunner().invoke(
            cli,
            ["setup-commit-log", "-C", str(git_repo)],
        )
        assert r.exit_code == 0


def test_setup_commit_log_no_install_hooks_message(git_repo: Path) -> None:
    r = CliRunner().invoke(
        cli,
        ["setup-commit-log", "--no-install-hooks", "-C", str(git_repo)],
    )
    assert r.exit_code == 0
