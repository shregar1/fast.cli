"""``fast checkpoint`` — record git commit markers in ``checkpoint.json`` for safe rollback hints."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from fast_cli.output import output

CHECKPOINT_FILENAME = "checkpoint.json"
SCHEMA_VERSION = 1


def _find_git_root(start: Path) -> Path | None:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return None


def _run_git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise click.ClickException(
            r.stderr.strip() or f"git {' '.join(args)} failed (exit {r.returncode})"
        )
    return r.stdout.strip()


def _load_checkpoint_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": SCHEMA_VERSION, "checkpoints": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise click.ClickException(f"Cannot read {path}: {e}") from e
    if not isinstance(data, dict):
        raise click.ClickException(f"Invalid checkpoint file (expected object): {path}")
    cps = data.get("checkpoints")
    if cps is None:
        data["checkpoints"] = []
    elif not isinstance(cps, list):
        raise click.ClickException(f"Invalid checkpoint file (checkpoints must be a list): {path}")
    data.setdefault("version", SCHEMA_VERSION)
    return data


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(raw, encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise click.ClickException(f"Cannot write {path}: {e}") from e


def register_checkpoint_command(cli: click.Group) -> None:
    """Register ``checkpoint`` on the root group."""

    @cli.group("checkpoint")
    def checkpoint_group() -> None:
        """Record named git commit markers in checkpoint.json for rollback reference."""
        pass

    @checkpoint_group.command("save")
    @click.option(
        "-m",
        "--message",
        default="",
        help="Optional note stored with this checkpoint.",
    )
    @click.option(
        "--allow-dirty/--no-allow-dirty",
        default=False,
        help="Allow saving when the working tree has uncommitted changes.",
    )
    def save(message: str, allow_dirty: bool) -> None:
        """Append a checkpoint for the current HEAD commit."""
        root = _find_git_root(Path.cwd())
        if root is None:
            raise click.ClickException(
                "Not inside a git repository. Run from a project root (or subdirectory) "
                "that contains a .git directory."
            )
        head = _run_git(["rev-parse", "HEAD"], root)
        short = _run_git(["rev-parse", "--short", "HEAD"], root)
        branch = _run_git(["branch", "--show-current"], root) or "(detached)"
        dirty_out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        dirty = bool(dirty_out.stdout.strip())

        if dirty and not allow_dirty:
            raise click.ClickException(
                "Working tree is dirty (uncommitted changes). Commit or stash first, "
                "or pass --allow-dirty to record HEAD anyway (revert will not restore "
                "uncommitted work)."
            )

        cfile = root / CHECKPOINT_FILENAME
        data = _load_checkpoint_file(cfile)
        checkpoints: list[dict[str, Any]] = data["checkpoints"]
        n = len(checkpoints) + 1
        cp_id = f"cp-{n:04d}"
        entry = {
            "id": cp_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": head,
            "git_commit_short": short,
            "branch": branch,
            "message": message.strip() or None,
            "dirty": dirty,
        }
        checkpoints.append(entry)
        data["checkpoints"] = checkpoints
        data["version"] = SCHEMA_VERSION
        _atomic_write_json(cfile, data)
        output.print_success(f"Checkpoint {cp_id} saved at {cfile}")
        output.console.print(f"  [dim]commit[/dim]  {short}  [dim]branch[/dim]  {branch}")
        if dirty:
            output.print_warning("Recorded with a dirty tree; only the commit SHA is stored.")

    @checkpoint_group.command("list")
    def list_cmd() -> None:
        """List checkpoints from checkpoint.json in the current git repository."""
        root = _find_git_root(Path.cwd())
        if root is None:
            raise click.ClickException("Not inside a git repository.")
        cfile = root / CHECKPOINT_FILENAME
        data = _load_checkpoint_file(cfile)
        checkpoints: list[Any] = data["checkpoints"]
        if not checkpoints:
            output.print_info(f"No checkpoints in {cfile}. Use `fast checkpoint save`.")
            return
        table = Table(title=f"Checkpoints ({cfile.name})", box=None)
        table.add_column("ID", style="cyan")
        table.add_column("When (UTC)", style="dim")
        table.add_column("Commit", style="green")
        table.add_column("Branch")
        table.add_column("Note")
        for cp in checkpoints:
            if not isinstance(cp, dict):
                continue
            table.add_row(
                str(cp.get("id", "—")),
                str(cp.get("created_at", "—"))[:19].replace("T", " "),
                str(cp.get("git_commit_short", cp.get("git_commit", "—")))[:12],
                str(cp.get("branch", "—")),
                (cp.get("message") or "—")[:40],
            )
        output.console.print(table)

    @checkpoint_group.command("show")
    @click.argument("checkpoint_id")
    def show(checkpoint_id: str) -> None:
        """Show one checkpoint and suggested git commands to return to it."""
        root = _find_git_root(Path.cwd())
        if root is None:
            raise click.ClickException("Not inside a git repository.")
        cfile = root / CHECKPOINT_FILENAME
        data = _load_checkpoint_file(cfile)
        for cp in data["checkpoints"]:
            if isinstance(cp, dict) and cp.get("id") == checkpoint_id:
                sha = cp.get("git_commit")
                if not sha:
                    raise click.ClickException("Checkpoint has no git_commit.")
                output.console.print(
                    f"[bold]{checkpoint_id}[/bold]  →  [green]{cp.get('git_commit_short', sha[:7])}[/green]  "
                    f"({cp.get('branch', '?')})"
                )
                output.console.print(f"  [dim]file[/dim] {cfile}")
                output.console.print()
                output.print_info("To move your branch back to this commit (destructive):")
                output.console.print(f"  [cyan]git reset --hard {sha}[/cyan]")
                output.console.print()
                output.print_info("Or inspect without moving branch:")
                output.console.print(f"  [cyan]git checkout {sha}[/cyan]")
                return
        raise click.ClickException(f"No checkpoint named {checkpoint_id!r}.")

    @checkpoint_group.command("revert")
    @click.argument("checkpoint_id")
    @click.option(
        "--execute/--no-execute",
        default=False,
        help="Actually run git reset --hard (otherwise only print the command).",
    )
    @click.option(
        "--yes",
        is_flag=True,
        default=False,
        help="Skip confirmation when using --execute.",
    )
    def revert(checkpoint_id: str, execute: bool, yes: bool) -> None:
        """Show or run git reset --hard to a saved checkpoint commit."""
        root = _find_git_root(Path.cwd())
        if root is None:
            raise click.ClickException("Not inside a git repository.")
        cfile = root / CHECKPOINT_FILENAME
        data = _load_checkpoint_file(cfile)
        sha = None
        for cp in data["checkpoints"]:
            if isinstance(cp, dict) and cp.get("id") == checkpoint_id:
                sha = cp.get("git_commit")
                break
        if not sha:
            raise click.ClickException(f"No checkpoint named {checkpoint_id!r}.")
        cmd = f"git reset --hard {sha}"
        if not execute:
            output.print_warning("Dry run — no changes made.")
            output.console.print(f"  [cyan]{cmd}[/cyan]")
            output.console.print()
            output.print_info("Re-run with --execute to apply (use --yes to skip prompt).")
            return
        if not yes and not click.confirm(
            f"This will discard uncommitted work and reset {root} to {sha[:7]}. Continue?",
            default=False,
        ):
            output.print_error("Aborted.")
            raise click.Abort()
        r = subprocess.run(
            ["git", "reset", "--hard", sha],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise click.ClickException(r.stderr.strip() or "git reset --hard failed")
        output.print_success(f"Reset to {checkpoint_id} ({sha[:7]})")
