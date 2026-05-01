"""``fastx changelog`` — auto-generate changelog from conventional commits."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from typing import Optional

import click


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mapping of conventional-commit prefix to human-readable section header.
COMMIT_TYPE_HEADERS: dict[str, str] = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "refactor": "Refactoring",
    "test": "Tests",
    "chore": "Chores",
    "perf": "Performance",
    "ci": "CI",
    "build": "Build",
    "style": "Style",
}

# Regex to parse a conventional commit subject line.
# Matches:  type(scope): description  or  type: description
_CC_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)"       # type
    r"(?:\((?P<scope>[^)]*)\))?"   # optional (scope)
    r"!?"                          # optional ! for breaking
    r":\s*(?P<desc>.+)$"           # : description
)

_BREAKING_RE = re.compile(r"^BREAKING[\s_-]?CHANGE", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _git(args: list[str]) -> str:
    """Run a git command and return stripped stdout.  Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _latest_tag() -> Optional[str]:
    """Return the most recent tag (by creator-date), or *None*."""
    try:
        out = _git(["tag", "--sort=-creatordate"])
    except click.ClickException:
        return None
    tags = [t for t in out.splitlines() if t.strip()]
    return tags[0] if tags else None


def _get_commits(from_ref: Optional[str], to_ref: str) -> list[dict]:
    """Return a list of commit dicts between *from_ref* and *to_ref*.

    Each dict has keys: ``hash``, ``subject``, ``author``, ``date``.
    """
    fmt = "%H|%s|%an|%aI"
    if from_ref:
        range_spec = f"{from_ref}..{to_ref}"
    else:
        range_spec = to_ref
    out = _git(["log", f"--format={fmt}", range_spec])
    if not out:
        return []

    commits: list[dict] = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        commits.append({
            "hash": parts[0],
            "subject": parts[1],
            "author": parts[2],
            "date": parts[3],
        })
    return commits


def _parse_commit(commit: dict) -> dict:
    """Augment a commit dict with parsed conventional-commit fields.

    Adds ``type``, ``scope``, ``description``, ``breaking``, and
    ``short_hash``.
    """
    subject = commit["subject"]
    commit["short_hash"] = commit["hash"][:7]
    commit["breaking"] = False

    # Check for BREAKING CHANGE prefix
    if _BREAKING_RE.match(subject):
        commit["type"] = "breaking"
        commit["scope"] = None
        commit["description"] = subject
        commit["breaking"] = True
        return commit

    m = _CC_RE.match(subject)
    if m:
        commit["type"] = m.group("type").lower()
        commit["scope"] = m.group("scope")
        commit["description"] = m.group("desc")
        # A trailing `!` before the colon signals a breaking change
        if "!" in subject.split(":")[0]:
            commit["breaking"] = True
    else:
        commit["type"] = "other"
        commit["scope"] = None
        commit["description"] = subject

    return commit


def _group_commits(commits: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Group parsed commits into breaking changes and type-based sections.

    Returns ``(breaking, groups)`` where *groups* maps header names to
    lists of commits.
    """
    breaking: list[dict] = []
    groups: dict[str, list[dict]] = {}

    for c in commits:
        if c.get("breaking"):
            breaking.append(c)
            # Also include in its type group (unless pure BREAKING CHANGE line)
            if c["type"] == "breaking":
                continue

        header = COMMIT_TYPE_HEADERS.get(c["type"])
        if header is None:
            header = "Other"
        groups.setdefault(header, []).append(c)

    return breaking, groups


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_markdown(
    version: Optional[str],
    breaking: list[dict],
    groups: dict[str, list[dict]],
) -> str:
    """Render changelog sections as Markdown."""
    lines: list[str] = []

    # Header
    version_label = version or "Unreleased"
    today = date.today().isoformat()
    lines.append(f"## [{version_label}] - {today}")
    lines.append("")

    # Breaking changes (highlighted at top)
    if breaking:
        lines.append("### BREAKING CHANGES")
        lines.append("")
        for c in breaking:
            lines.append(f"- {c['description']} (`{c['short_hash']}`)")
        lines.append("")

    # Grouped sections — iterate in the order defined by COMMIT_TYPE_HEADERS,
    # then append any extra groups (e.g. "Other") at the end.
    ordered_headers = list(COMMIT_TYPE_HEADERS.values())
    seen: set[str] = set()

    for header in ordered_headers:
        if header not in groups:
            continue
        seen.add(header)
        lines.append(f"### {header}")
        lines.append("")
        for c in groups[header]:
            scope = f"**{c['scope']}:** " if c.get("scope") else ""
            lines.append(f"- {scope}{c['description']} (`{c['short_hash']}`)")
        lines.append("")

    for header, commits in groups.items():
        if header in seen:
            continue
        lines.append(f"### {header}")
        lines.append("")
        for c in commits:
            scope = f"**{c['scope']}:** " if c.get("scope") else ""
            lines.append(f"- {scope}{c['description']} (`{c['short_hash']}`)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_json(
    version: Optional[str],
    breaking: list[dict],
    groups: dict[str, list[dict]],
) -> str:
    """Render changelog as a JSON object."""
    payload: dict = {
        "version": version or "Unreleased",
        "date": date.today().isoformat(),
    }

    if breaking:
        payload["breaking_changes"] = [
            {
                "description": c["description"],
                "hash": c["short_hash"],
                "author": c["author"],
            }
            for c in breaking
        ]

    sections: dict[str, list[dict]] = {}
    for header, commits in groups.items():
        sections[header] = [
            {
                "description": c["description"],
                "scope": c.get("scope"),
                "hash": c["short_hash"],
                "author": c["author"],
            }
            for c in commits
        ]
    payload["sections"] = sections

    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command("changelog")
@click.option(
    "--from", "from_ref",
    default=None,
    help="Starting git ref (default: latest tag).",
)
@click.option(
    "--to", "to_ref",
    default="HEAD",
    show_default=True,
    help="Ending git ref.",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output", "-o", "output_file",
    type=click.Path(),
    default=None,
    help="Write changelog to a file instead of stdout.",
)
@click.option(
    "--version", "version_label",
    default=None,
    help="Version label for the release header (e.g. 1.2.0).",
)
def changelog_cmd(
    from_ref: Optional[str],
    to_ref: str,
    fmt: str,
    output_file: Optional[str],
    version_label: Optional[str],
) -> None:
    """Auto-generate a changelog from conventional commits."""

    # Resolve starting ref
    if from_ref is None:
        from_ref = _latest_tag()
        if from_ref is None:
            click.echo("No tags found — using full commit history.", err=True)

    # Gather and parse commits
    raw_commits = _get_commits(from_ref, to_ref)
    if not raw_commits:
        click.echo("No commits found in the specified range.", err=True)
        sys.exit(0)

    parsed = [_parse_commit(c) for c in raw_commits]
    breaking, groups = _group_commits(parsed)

    # Format output
    if fmt == "json":
        text = _format_json(version_label, breaking, groups)
    else:
        text = _format_markdown(version_label, breaking, groups)

    # Emit
    if output_file:
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(text)
        click.echo(f"Changelog written to {output_file}", err=True)
    else:
        click.echo(text, nl=False)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_changelog(cli: click.Group) -> None:
    """Register the ``changelog`` command on the root CLI group."""
    cli.add_command(changelog_cmd)
