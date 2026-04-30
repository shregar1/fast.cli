"""Install commit history recorder (git_log_recorder + pre-commit post-commit) in any git repo."""

from __future__ import annotations

import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import click
import yaml

from fastx_cli.output import output

RECORDER_REL_PATH = Path("_maint/scripts/git_log_recorder.py")

GIT_LOG_HOOK: dict[str, Any] = {
    "id": "git-log-recorder",
    "name": "git-log-recorder",
    "entry": "python3 _maint/scripts/git_log_recorder.py",
    "language": "system",
    "always_run": True,
    "pass_filenames": False,
    "stages": ["post-commit"],
}

# Appended to the repo ``.gitignore`` by :func:`_ensure_gitignore_entries` when missing.
GITIGNORE_LINES: tuple[str, ...] = (
    "coverage_output.txt",
    "commit_history.json",
)
GITIGNORE_MARKER = "# fast-cli setup-commit-log"


COMMON_HOOKS_REPO: dict[str, Any] = {
    "repo": "https://github.com/pre-commit/pre-commit-hooks",
    "rev": "v4.5.0",
    "hooks": [
        {"id": "trailing-whitespace"},
        {"id": "end-of-file-fixer"},
        {"id": "check-yaml"},
        {"id": "check-json"},
        {"id": "check-merge-conflict"},
    ],
}


def _git_toplevel(start: Path) -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return Path(out) if out else None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _bundled_recorder_source() -> str:
    return resources.files("fastx_cli.bundled").joinpath("git_log_recorder.py").read_text(
        encoding="utf-8"
    )


def _repos_list(data: dict[str, Any]) -> list[Any]:
    repos = data.get("repos")
    if not isinstance(repos, list):
        repos = []
        data["repos"] = repos
    return repos


def _hook_already_present(data: dict[str, Any]) -> bool:
    for repo in _repos_list(data):
        if not isinstance(repo, dict):
            continue
        hooks = repo.get("hooks")
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if isinstance(hook, dict) and hook.get("id") == "git-log-recorder":
                return True
    return False


def _ensure_local_git_log_hook(data: dict[str, Any]) -> bool:
    """Insert the git-log-recorder hook into *data* if missing. Returns whether *data* changed."""
    repos = _repos_list(data)

    if _hook_already_present(data):
        return False

    for repo in repos:
        if isinstance(repo, dict) and repo.get("repo") == "local":
            hooks = repo.get("hooks")
            if not isinstance(hooks, list):
                hooks = []
                repo["hooks"] = hooks
            hooks.append(dict(GIT_LOG_HOOK))
            return True

    repos.append({"repo": "local", "hooks": [dict(GIT_LOG_HOOK)]})
    return True


def _write_pre_commit_config(
    path: Path,
    *,
    with_common_hooks: bool,
) -> tuple[bool, str]:
    """Update or create ``.pre-commit-config.yaml``. Returns (written, description)."""
    if not path.exists():
        if with_common_hooks:
            data: dict[str, Any] = {
                "repos": [
                    dict(COMMON_HOOKS_REPO),
                    {"repo": "local", "hooks": [dict(GIT_LOG_HOOK)]},
                ]
            }
        else:
            data = {"repos": [{"repo": "local", "hooks": [dict(GIT_LOG_HOOK)]}]}
        path.write_text(
            _dump_yaml(data),
            encoding="utf-8",
        )
        return True, "created"

    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        raise click.ClickException(
            f"Could not parse {path}: {e}\nFix the file or rename it, then run this command again."
        ) from e

    if not isinstance(data, dict):
        data = {}

    if _hook_already_present(data):
        return False, "already present"

    changed = _ensure_local_git_log_hook(data)
    if not changed:
        return False, "unchanged"

    path.write_text(_dump_yaml(data), encoding="utf-8")
    return True, "updated"


def _dump_yaml(data: dict[str, Any]) -> str:
    dumped = yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    if not dumped.endswith("\n"):
        dumped += "\n"
    return dumped


def _gitignore_non_comment_lines(text: str) -> set[str]:
    """Return stripped non-empty, non-comment lines for duplicate detection."""
    out: set[str] = set()
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out


def _ensure_gitignore_entries(root: Path) -> tuple[bool, list[str]]:
    """Append ``GITIGNORE_LINES`` to ``.gitignore`` when not already listed.

    Returns
    -------
    changed
        Whether the file was modified.
    added
        Basenames that were appended (may be empty if nothing to do).
    """
    path = root / ".gitignore"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    present = _gitignore_non_comment_lines(content)
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if not missing:
        return False, []

    parts: list[str] = []
    if content and not content.endswith("\n"):
        parts.append("\n")
    elif content:
        parts.append("\n")
    if GITIGNORE_MARKER not in content:
        parts.append(f"{GITIGNORE_MARKER}\n")
    for line in missing:
        parts.append(f"{line}\n")
    try:
        path.write_text(content + "".join(parts), encoding="utf-8")
    except OSError as e:
        output.print_warning(f"Could not update .gitignore: {e}")
        return False, []
    return True, missing


def _install_pre_commit_hooks(repo: Path) -> tuple[bool, str | None]:
    """Run ``pre-commit install`` and ``post-commit`` installs. Returns (ok, stderr_or_none)."""
    try:
        base = subprocess.run(
            ["pre-commit", "install"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        post = subprocess.run(
            ["pre-commit", "install", "--hook-type", "post-commit"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return False, "pre-commit not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "pre-commit install timed out"

    if base.returncode != 0 or post.returncode != 0:
        err = (base.stderr or "") + (post.stderr or "")
        return False, err.strip() or "pre-commit install failed"

    return True, None


def register_commit_history_setup(cli: click.Group) -> None:
    """Register ``setup-commit-log`` on the root ``cli`` group."""

    @cli.command("setup-commit-log")
    @click.option(
        "-C",
        "--path",
        "repo_path",
        type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
        default=".",
        help="Git repository root (default: current directory).",
    )
    @click.option(
        "--install-hooks/--no-install-hooks",
        default=True,
        help="Run pre-commit install (commit + post-commit hooks) when pre-commit is available.",
    )
    @click.option(
        "--with-common-hooks",
        is_flag=True,
        help="When creating a new .pre-commit-config.yaml, also add pre-commit-hooks (trim, YAML/JSON checks, etc.).",
    )
    def setup_commit_log(
        repo_path: Path,
        install_hooks: bool,
        with_common_hooks: bool,
    ) -> None:
        """Install commit_history.json recorder: _maint script + pre-commit post-commit hook."""
        start = repo_path.resolve()
        root = _git_toplevel(start)
        if not root:
            output.print_error(
                f"Not a git repository (or git unavailable): {start}"
            )
            raise SystemExit(1)

        script_dest = root / RECORDER_REL_PATH
        script_dest.parent.mkdir(parents=True, exist_ok=True)
        init_py = script_dest.parent / "__init__.py"
        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")

        source = _bundled_recorder_source()
        script_dest.write_text(source, encoding="utf-8")
        try:
            script_dest.chmod(script_dest.stat().st_mode | 0o111)
        except OSError:
            pass
        output.print_success(f"Wrote {script_dest.relative_to(root)}")

        cfg = root / ".pre-commit-config.yaml"
        try:
            written, desc = _write_pre_commit_config(
                cfg, with_common_hooks=with_common_hooks
            )
        except click.ClickException as e:
            output.print_error(str(e))
            raise SystemExit(1) from e

        if written:
            output.print_success(f".pre-commit-config.yaml {desc}")
        else:
            output.print_info(f".pre-commit-config.yaml: git-log-recorder hook {desc}")

        gi_changed, gi_added = _ensure_gitignore_entries(root)
        if gi_changed:
            output.print_success(f"Updated .gitignore ({', '.join(gi_added)})")

        if install_hooks:
            ok, err = _install_pre_commit_hooks(root)
            if ok:
                output.print_success("pre-commit hooks installed (commit + post-commit)")
            else:
                output.print_warning(
                    "Could not run pre-commit install automatically."
                    + (f" ({err})" if err else "")
                )
                output.print_info(
                    "Install manually: pip install pre-commit && "
                    "pre-commit install && pre-commit install --hook-type post-commit"
                )
        else:
            output.print_info(
                "Skipped pre-commit install (--no-install-hooks). "
                "Run: pre-commit install && pre-commit install --hook-type post-commit"
            )

        output.print_info(
            "Each commit appends metadata to commit_history.json at the repository root."
        )
