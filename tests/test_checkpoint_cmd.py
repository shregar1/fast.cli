"""Tests for ``fast checkpoint``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner
from fastx_cli.app import cli


def _git_init_with_commit(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.co"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_checkpoint_save_list_show_revert_dry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    r = runner.invoke(cli, ["checkpoint", "save", "-m", "first"])
    assert r.exit_code == 0
    cfile = tmp_path / "checkpoint.json"
    assert cfile.is_file()
    data = json.loads(cfile.read_text(encoding="utf-8"))
    assert len(data["checkpoints"]) == 1
    assert data["checkpoints"][0]["id"] == "cp-0001"
    assert data["checkpoints"][0]["message"] == "first"

    r2 = runner.invoke(cli, ["checkpoint", "list"])
    assert r2.exit_code == 0
    assert "cp-0001" in r2.output

    r3 = runner.invoke(cli, ["checkpoint", "show", "cp-0001"])
    assert r3.exit_code == 0
    assert "git reset --hard" in r3.output

    r4 = runner.invoke(cli, ["checkpoint", "revert", "cp-0001"])
    assert r4.exit_code == 0
    assert "Dry run" in r4.output or "dry" in r4.output.lower()


def test_checkpoint_save_fails_dirty_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dirty.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(cli, ["checkpoint", "save"])
    assert r.exit_code != 0

    r2 = runner.invoke(cli, ["checkpoint", "save", "--allow-dirty"])
    assert r2.exit_code == 0
    data = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert data["checkpoints"][0]["dirty"] is True


def test_checkpoint_not_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    r = runner.invoke(cli, ["checkpoint", "save"])
    assert r.exit_code != 0


def test_checkpoint_list_show_revert_not_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for args in (
        ["checkpoint", "list"],
        ["checkpoint", "show", "cp-0001"],
        ["checkpoint", "revert", "cp-0001"],
    ):
        assert CliRunner().invoke(cli, args).exit_code != 0


def test_checkpoint_revert_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["checkpoint", "save"])
    (tmp_path / "second.md").write_text("y", encoding="utf-8")
    subprocess.run(["git", "add", "second.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    r = runner.invoke(
        cli,
        ["checkpoint", "revert", "cp-0001", "--execute", "--yes"],
    )
    assert r.exit_code == 0
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    first = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))[
        "checkpoints"
    ][0]["git_commit"]
    assert head == first


def test_checkpoint_show_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "show", "cp-9999"])
    assert r.exit_code != 0


def test_checkpoint_list_empty_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "list"])
    assert r.exit_code == 0
    assert "No checkpoints" in r.output


def test_checkpoint_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text("{", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "list"])
    assert r.exit_code != 0


def test_checkpoint_root_not_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "list"])
    assert r.exit_code != 0


def test_checkpoint_checkpoints_not_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text('{"checkpoints":{}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "list"])
    assert r.exit_code != 0


def test_checkpoint_show_missing_git_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text(
        '{"version":1,"checkpoints":[{"id":"cp-0001"}]}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "show", "cp-0001"])
    assert r.exit_code != 0


def test_checkpoint_revert_execute_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(cli, ["checkpoint", "save"])
    with patch("click.confirm", return_value=False):
        r = CliRunner().invoke(cli, ["checkpoint", "revert", "cp-0001", "--execute"])
    assert r.exit_code != 0


def test_checkpoint_save_from_subdirectory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init_with_commit(tmp_path)
    sub = tmp_path / "src" / "deep"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    r = CliRunner().invoke(cli, ["checkpoint", "save", "-m", "nested"])
    assert r.exit_code == 0
    assert (tmp_path / "checkpoint.json").is_file()


def test_checkpoint_list_skips_non_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text(
        '{"version":1,"checkpoints":[1, {"id":"cp-1","created_at":"2020-01-01T00:00:00+00:00",'
        '"git_commit_short":"abcd1234","git_commit":"abcd1234abcd1234abcd1234abcd1234abcd1234",'
        '"branch":"main"}]}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "list"])
    assert r.exit_code == 0
    assert "cp-1" in r.output


def test_run_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastx_cli.commands import checkpoint_cmd as cc

    def _fake(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git"], 1, "", "git error")

    monkeypatch.setattr(cc.subprocess, "run", _fake)
    with pytest.raises(click.ClickException, match="git error"):
        cc._run_git(["status"], Path("/"))


def test_atomic_write_json_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastx_cli.commands import checkpoint_cmd as cc

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)
    with pytest.raises(click.ClickException, match="disk full"):
        cc._atomic_write_json(tmp_path / "checkpoint.json", {"version": 1, "checkpoints": []})


def test_load_checkpoint_missing_checkpoints_key(tmp_path: Path) -> None:
    from fastx_cli.commands.checkpoint_cmd import _load_checkpoint_file

    p = tmp_path / "checkpoint.json"
    p.write_text("{}", encoding="utf-8")
    d = _load_checkpoint_file(p)
    assert d["checkpoints"] == []
    assert d.get("version") == 1


def test_checkpoint_revert_empty_git_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    (tmp_path / "checkpoint.json").write_text(
        '{"version":1,"checkpoints":[{"id":"cp-0001","git_commit":""}]}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["checkpoint", "revert", "cp-0001"])
    assert r.exit_code != 0


def test_atomic_write_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastx_cli.commands import checkpoint_cmd as cc

    def _bad_replace(_self: Path, _target: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", _bad_replace)
    with pytest.raises(click.ClickException, match="replace failed"):
        cc._atomic_write_json(
            tmp_path / "checkpoint.json", {"version": 1, "checkpoints": []}
        )


def test_checkpoint_revert_execute_git_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init_with_commit(tmp_path)
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(cli, ["checkpoint", "save"])
    real_run = subprocess.run

    def _fake(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "reset":
            return subprocess.CompletedProcess(cmd, 1, "", "reset failed")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr("fastx_cli.commands.checkpoint_cmd.subprocess.run", _fake)
    r = CliRunner().invoke(
        cli, ["checkpoint", "revert", "cp-0001", "--execute", "--yes"]
    )
    assert r.exit_code != 0
