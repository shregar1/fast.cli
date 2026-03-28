"""Additional unit and integration tests for CLI shims, output, and edge cases."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from click.testing import CliRunner
from rich.console import Console

from fast_cli.app import cli, main
from fast_cli.commands import commit_history_setup as chs
from fast_cli.output import CliOutput


def test_new_command_invokes_pipeline(tmp_path: Path) -> None:
    with patch(
        "fast_cli.project_generation.ProjectGenerationOrchestrator._execute_pipeline"
    ) as pipe:
        r = CliRunner().invoke(
            cli,
            [
                "new",
                "--name",
                "myproj",
                "--path",
                str(tmp_path),
                "--no-venv",
                "--no-install-deps",
            ],
        )
    assert r.exit_code == 0
    pipe.assert_called_once()


def test_fast_cli_cli_shim_same_objects() -> None:
    from fast_cli.app import cli as app_cli
    from fast_cli.app import main as app_main
    from fast_cli.cli import cli as shim_cli
    from fast_cli.cli import main as shim_main

    assert app_cli is shim_cli
    assert app_main is shim_main


def test_main_delegates_to_root_cli() -> None:
    """``main()`` must call the root group with no stray ``sys.argv`` from pytest."""
    with patch("fast_cli.app.cli") as mock_cli:
        main()
    mock_cli.assert_called_once_with()


def test_cli_output_all_methods_capture() -> None:
    buf = io.StringIO()
    out = CliOutput()
    out.console = Console(file=buf, width=120, force_terminal=False, legacy_windows=False)
    out.print_banner()
    out.print_success("done")
    out.print_error("bad")
    out.print_warning("warn")
    out.print_info("info")
    out.print_step(1, "first")
    text = buf.getvalue()
    assert "done" in text and "bad" in text and "warn" in text and "info" in text
    assert "Step 1" in text


def test_python_m_fast_cli_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    r = subprocess.run(
        [sys.executable, "-m", "fast_cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=str(repo_root),
    )
    assert r.returncode == 0
    assert "FastMVC" in r.stdout or "generate" in r.stdout


def test_cli_version_option() -> None:
    r = CliRunner().invoke(cli, ["--version"])
    assert r.exit_code == 0
    assert r.output.strip()


def test_gitignore_non_comment_lines() -> None:
    text = """
# comment
coverage_output.txt

  # indented comment
commit_history.json

keep-me
"""
    assert chs._gitignore_non_comment_lines(text) == {
        "coverage_output.txt",
        "commit_history.json",
        "keep-me",
    }


def test_ensure_gitignore_oserror_on_write(tmp_path: Path) -> None:
    real_write = Path.write_text

    def selective_write(self: Path, *a: object, **kw: object) -> None:
        if self.name == ".gitignore":
            raise OSError("read-only")
        return real_write(self, *a, **kw)

    with patch.object(Path, "write_text", selective_write):
        changed, added = chs._ensure_gitignore_entries(tmp_path)
    assert changed is False
    assert added == []


def test_ensure_gitignore_appends_when_file_has_no_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / ".gitignore"
    path.write_text("coverage_output.txt", encoding="utf-8")
    chs._ensure_gitignore_entries(tmp_path)
    raw = path.read_text(encoding="utf-8")
    assert raw.rstrip("\n").endswith("commit_history.json")


def test_write_pre_commit_config_yaml_list_root(tmp_path: Path) -> None:
    p = tmp_path / ".pre-commit-config.yaml"
    p.write_text("[]\n")
    w, desc = chs._write_pre_commit_config(p, with_common_hooks=False)
    assert w and desc == "updated"
    loaded = yaml.safe_load(p.read_text())
    assert isinstance(loaded, dict)
    assert any(
        h.get("id") == "git-log-recorder"
        for r in loaded["repos"]
        for h in r.get("hooks", [])
    )


def test_install_pre_commit_hooks_post_fails(tmp_path: Path) -> None:
    with patch("fast_cli.commands.commit_history_setup.subprocess.run") as run:
        run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="post failed"),
        ]
        ok, err = chs._install_pre_commit_hooks(tmp_path)
    assert not ok
    assert err and "post failed" in err


def test_hook_already_present_skips_non_dict_hook() -> None:
    data = {
        "repos": [
            {
                "repo": "local",
                "hooks": ["not-a-dict", {"id": "git-log-recorder"}],
            }
        ]
    }
    assert chs._hook_already_present(data) is True


def test_setup_commit_log_with_common_hooks_cli(git_repo: Path) -> None:
    r = CliRunner().invoke(
        cli,
        [
            "setup-commit-log",
            "--no-install-hooks",
            "--with-common-hooks",
            "-C",
            str(git_repo),
        ],
    )
    assert r.exit_code == 0
    cfg = yaml.safe_load((git_repo / ".pre-commit-config.yaml").read_text())
    assert len(cfg["repos"]) >= 2
    assert any(
        "pre-commit-hooks" in str(r.get("repo", "")) for r in cfg["repos"]
    )


def test_decimate_unlink_file_oserror(tmp_path: Path) -> None:
    from fast_cli.commands.decimate_cmd import ArtifactDecimator

    f = tmp_path / "junk.pyc"
    f.write_bytes(b"x")
    real_unlink = Path.unlink

    def selective_unlink(self: Path, *a: object, **kw: object) -> None:
        if self.name == "junk.pyc":
            raise OSError("perm")
        return real_unlink(self, *a, **kw)

    with patch.object(Path, "unlink", selective_unlink):
        ArtifactDecimator("python", tmp_path).run()
