#!/usr/bin/env python3
"""Git Log Recorder - Captured commit metadata for FastMVC.
Logs commit details to commit_history.json in a parsable format.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fast_cli.constants import GIT_LOG_MAX_ENTRIES, GIT_LOG_RECENT_WINDOW


def get_repo_root() -> Path | None:
    """Resolve the git work tree root (works from any subdirectory)."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return Path(out) if out else None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def get_git_info():
    """Query git for the last commit info."""
    try:
        # Get last commit details
        # %H: full hash, %an: author name, %ae: author email, %ad: author date, %s: subject
        cmd = ["git", "log", "-1", "--pretty=format:%H|%an|%ae|%ad|%s"]
        output = subprocess.check_output(cmd).decode("utf-8").strip()
        parts = output.split("|")

        # Get changed files
        files_cmd = [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            parts[0],
        ]
        files = subprocess.check_output(files_cmd).decode("utf-8").strip().split("\n")

        return {
            "hash": parts[0],
            "author": parts[1],
            "email": parts[2],
            "date": parts[3],
            "message": parts[4],
            "files": [f for f in files if f],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Error capturing git info: {e}")
        return None


def main():
    """Execute main operation.

    Returns:
        The result of the operation.
    """
    root_path = get_repo_root()
    if not root_path:
        print("Error: not a git repository (or git is not available).")
        return

    log_file = root_path / "commit_history.json"
    legacy = root_path / "GIT_METADATA.json"
    if not log_file.exists() and legacy.exists():
        try:
            legacy.rename(log_file)
        except OSError:
            pass

    metadata = get_git_info()

    if not metadata:
        return

    # Load existing logs or start new array
    logs: List[Dict[str, Any]] = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                parsed = json.load(f)
                if isinstance(parsed, list):
                    logs = parsed
        except:
            logs = []

    # Update or Add (prevent duplicates if hook runs twice)
    # Check if this hash is already in the last 5 logs (common race condition)
    hashes = [l.get("hash") for l in logs[:GIT_LOG_RECENT_WINDOW]]
    if metadata["hash"] not in hashes:
        logs.insert(0, metadata)
        # Keep last 100 commits
        processed_logs = logs[:GIT_LOG_MAX_ENTRIES]

        with open(log_file, "w") as f:
            json.dump(processed_logs, f, indent=2)

        print(f"  ● Commit logged to {log_file}")


if __name__ == "__main__":
    main()
