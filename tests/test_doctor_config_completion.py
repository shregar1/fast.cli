"""Tests for doctor, completion, and user defaults config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.user_config import load_user_defaults


def test_load_user_defaults_missing() -> None:
    assert load_user_defaults() == {}


def test_load_user_defaults_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fastx_cli.user_config.config_dir", lambda: tmp_path / "fastmvc")
    p = tmp_path / "fastmvc" / "defaults.toml"
    p.parent.mkdir(parents=True)
    p.write_text(
        '[defaults]\nauthor = "Ada"\nauthor_email = "a@b.co"\nvenv_name = ".venv"\n',
        encoding="utf-8",
    )
    d = load_user_defaults()
    assert d.get("author") == "Ada"
    assert d.get("author_email") == "a@b.co"
    assert d.get("venv_name") == ".venv"


def test_doctor_exits_zero() -> None:
    r = CliRunner().invoke(cli, ["doctor"])
    assert r.exit_code == 0


def test_check_env_alias() -> None:
    r = CliRunner().invoke(cli, ["check-env"])
    assert r.exit_code == 0


def test_completion_requires_fastx_on_path() -> None:
    with patch("fastx_cli.commands.completion_cmd.shutil.which", return_value=None):
        r = CliRunner().invoke(cli, ["completion", "bash"])
        assert r.exit_code == 1


def test_completion_success_mocked() -> None:
    with patch("fastx_cli.commands.completion_cmd.shutil.which", return_value="/x/fast"):
        with patch("fastx_cli.commands.completion_cmd.subprocess.run") as run:
            run.return_value = MagicMock(
                returncode=0,
                stdout="# completion script\n",
                stderr="",
            )
            r = CliRunner().invoke(cli, ["completion", "bash"])
    assert r.exit_code == 0
    assert "completion script" in r.output


def test_add_middleware_info() -> None:
    r = CliRunner().invoke(cli, ["add", "middleware"])
    assert r.exit_code == 0
    assert "not bundled" in r.output.lower() or "bundled" in r.output.lower()


def test_add_auth_and_test() -> None:
    for sub in ("auth", "test"):
        r = CliRunner().invoke(cli, ["add", sub])
        assert r.exit_code == 0


def test_user_config_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_home))
    from fastx_cli import user_config as uc

    assert uc.config_dir() == cfg_home / "fastmvc"
    p = cfg_home / "fastmvc" / "defaults.toml"
    p.parent.mkdir(parents=True)
    p.write_text('[defaults]\nauthor = "Z"\n', encoding="utf-8")
    assert uc.load_user_defaults().get("author") == "Z"


def test_user_config_bad_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fastx_cli.user_config.config_dir", lambda: tmp_path / "fastmvc"
    )
    p = tmp_path / "fastmvc" / "defaults.toml"
    p.parent.mkdir(parents=True)
    p.write_text("not toml {{{", encoding="utf-8")
    assert load_user_defaults() == {}


def test_user_config_read_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fastx_cli.user_config.config_dir", lambda: tmp_path / "fastmvc"
    )
    p = tmp_path / "fastmvc" / "defaults.toml"
    p.parent.mkdir(parents=True)
    p.write_text("[defaults]\nx=1\n", encoding="utf-8")

    def _read(*a: object, **k: object) -> str:
        raise OSError("x")

    with patch.object(Path, "read_text", _read):
        assert load_user_defaults() == {}


def test_user_config_non_dict_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fastx_cli.user_config.config_dir", lambda: tmp_path / "fastmvc"
    )
    p = tmp_path / "fastmvc" / "defaults.toml"
    p.parent.mkdir(parents=True)
    p.write_text("[]\n", encoding="utf-8")
    assert load_user_defaults() == {}


def test_user_config_defaults_not_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "defaults.toml"
    p.write_text("x=1\n", encoding="utf-8")
    monkeypatch.setattr("fastx_cli.user_config.defaults_path", lambda: p)

    def _loads(_s: str) -> dict:
        return {"defaults": "not-a-table"}

    monkeypatch.setattr("fastx_cli.user_config.tomllib.loads", _loads)
    assert load_user_defaults() == {}


def test_user_config_loads_returns_non_dict_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "defaults.toml"
    p.write_text("ignored\n", encoding="utf-8")
    monkeypatch.setattr("fastx_cli.user_config.defaults_path", lambda: p)
    monkeypatch.setattr("fastx_cli.user_config.tomllib.loads", lambda _s: [])
    assert load_user_defaults() == {}


def test_completion_subprocess_timeout() -> None:
    import subprocess as sp

    with patch("fastx_cli.commands.completion_cmd.shutil.which", return_value="/x/fast"):
        with patch(
            "fastx_cli.commands.completion_cmd.subprocess.run",
            side_effect=sp.TimeoutExpired("x", 1),
        ):
            r = CliRunner().invoke(cli, ["completion", "zsh"])
    assert r.exit_code == 1


def test_completion_subprocess_failed() -> None:
    with patch("fastx_cli.commands.completion_cmd.shutil.which", return_value="/x/fast"):
        with patch("fastx_cli.commands.completion_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stdout="", stderr="bad")
            r = CliRunner().invoke(cli, ["completion", "fish"])
    assert r.exit_code == 1


def test_completion_empty_script() -> None:
    with patch("fastx_cli.commands.completion_cmd.shutil.which", return_value="/x/fast"):
        with patch("fastx_cli.commands.completion_cmd.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="   \n", stderr="")
            r = CliRunner().invoke(cli, ["completion", "bash"])
    assert r.exit_code == 1


def test_doctor_optional_dist_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib import metadata

    def _ver(_name: str) -> str:
        raise metadata.PackageNotFoundError()

    monkeypatch.setattr(metadata, "version", _ver)
    r = CliRunner().invoke(cli, ["doctor"])
    assert r.exit_code == 0


def test_doctor_git_missing_from_path(monkeypatch: pytest.MonkeyPatch) -> None:
    real_which = __import__("shutil").which

    def _which(cmd: str) -> str | None:
        if cmd == "git":
            return None
        return real_which(cmd)

    monkeypatch.setattr("fastx_cli.commands.doctor_cmd.shutil.which", _which)
    r = CliRunner().invoke(cli, ["doctor"])
    assert r.exit_code == 0
    assert "missing" in r.output.lower() or "git" in r.output.lower()
    assert "suggested" in r.output.lower()


def test_doctor_tool_hints() -> None:
    from fastx_cli.commands import doctor_cmd as dc

    git_hint = dc._tool_install_hint("git")
    assert "git" in git_hint.lower() or "install" in git_hint.lower()
    assert "pip install alembic" in dc._tool_install_hint("alembic")
    assert "pre-commit" in dc._tool_install_hint("pre-commit").lower()
    assert "python" in dc._tool_install_hint("python3").lower()
    assert "fastx-cli" in dc._optional_install_hint("questionary").lower()


@pytest.mark.parametrize(
    ("plat", "needle"),
    [
        ("win32", "git-scm.com"),
        ("darwin", "brew"),
        ("linux", "apt"),
    ],
)
def test_doctor_git_hint_by_platform(
    plat: str, needle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastx_cli.commands import doctor_cmd as dc

    monkeypatch.setattr("fastx_cli.commands.doctor_cmd.sys.platform", plat)
    assert needle in dc._tool_install_hint("git")


def test_doctor_unknown_tool_hint() -> None:
    from fastx_cli.commands import doctor_cmd as dc

    assert "package manager" in dc._tool_install_hint("unknown").lower()


def test_doctor_ready_panel_all_green(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fastx_cli.commands.doctor_cmd.shutil.which",
        lambda _exe: "/mock/bin/tool",
    )
    monkeypatch.setattr(
        "fastx_cli.commands.doctor_cmd.importlib.util.find_spec",
        lambda _mod: object(),
    )
    monkeypatch.setattr(
        "fastx_cli.commands.doctor_cmd.metadata.version",
        lambda _n: "9.9.9",
    )

    r = CliRunner().invoke(cli, ["doctor"])
    assert r.exit_code == 0
    assert "good shape" in r.output.lower()


def test_quickstart_applies_cfg_venv_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    from fastx_cli.project_generation import ProjectGenerationOrchestrator

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "fastx_cli.project_generation.load_user_defaults",
        lambda: {"venv_name": "  .extra  "},
    )
    orch = ProjectGenerationOrchestrator()
    with patch.object(orch, "_execute_pipeline") as ex:
        orch.run_quickstart("qsproj", ".venv", False)
    ctx = ex.call_args[0][1]
    assert ctx["venv_name"] == ".extra"


def test_generate_merges_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fastx_cli.commands.generate_cmd.load_user_defaults",
        lambda: {
            "author": "FromCfg",
            "author_email": "cfg@e.co",
            "description": "From file",
            "venv_name": "venv",
        },
    )
    with patch(
        "fastx_cli.project_generation.ProjectGenerationOrchestrator._execute_pipeline"
    ):
        r = CliRunner().invoke(
            cli,
            [
                "generate",
                "--name",
                "p",
                "--path",
                str(tmp_path / "out"),
                "--no-venv",
                "--no-install-deps",
            ],
        )
    assert r.exit_code == 0
