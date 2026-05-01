"""``fastx audit`` — security audit scanner for FastX projects."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

Status = Literal["pass", "warn", "fail"]


@dataclass
class CheckResult:
    """Outcome of a single security check."""

    name: str
    status: Status
    message: str
    file: str | None = None
    line: int | None = None


@dataclass
class AuditReport:
    """Aggregated audit results."""

    results: list[CheckResult] = field(default_factory=list)

    # -- counts ---------------------------------------------------------------

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    # -- serialisation --------------------------------------------------------

    def to_dicts(self) -> list[dict]:
        out: list[dict] = []
        for r in self.results:
            d: dict = {
                "name": r.name,
                "status": r.status,
                "message": r.message,
            }
            if r.file:
                d["file"] = r.file
            if r.line is not None:
                d["line"] = r.line
            out.append(d)
        return out


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("password", re.compile(r"""(?:password|passwd)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)),
    ("secret_key", re.compile(r"""secret_key\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)),
    ("api_key", re.compile(r"""api_key\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)),
    ("token", re.compile(r"""(?:token|auth_token|access_token)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)),
]

_SQL_KEYWORDS = re.compile(
    r"""f['"].*\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b""",
    re.IGNORECASE,
)

_SECURITY_PACKAGES = {
    "fastapi", "starlette", "uvicorn", "pyjwt", "python-jose",
    "cryptography", "bcrypt", "passlib", "sqlalchemy", "httpx",
    "requests", "django", "flask",
}


def _collect_py_files(root: Path) -> list[Path]:
    """Return all ``.py`` files under *root*, skipping common non-project dirs."""
    skip = {".venv", "venv", "node_modules", "__pycache__", ".git", ".tox", "dist", "build"}
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        files.append(p)
    return files


def check_hardcoded_secrets(root: Path, report: AuditReport) -> None:
    """Scan .py files for hardcoded secrets."""
    findings: list[CheckResult] = []
    for py in _collect_py_files(root):
        try:
            lines = py.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            # skip comments
            stripped = text.lstrip()
            if stripped.startswith("#"):
                continue
            for label, pat in _SECRET_PATTERNS:
                if pat.search(text):
                    # ignore lines that read from env / config
                    if "os.environ" in text or "os.getenv" in text or "settings." in text.lower():
                        continue
                    findings.append(
                        CheckResult(
                            name="hardcoded-secret",
                            status="fail",
                            message=f"Possible hardcoded {label}",
                            file=str(py.relative_to(root)),
                            line=lineno,
                        )
                    )

    if findings:
        report.results.extend(findings)
    else:
        report.results.append(
            CheckResult(name="hardcoded-secret", status="pass", message="No hardcoded secrets detected")
        )


def check_outdated_deps(report: AuditReport) -> None:
    """Flag outdated security-relevant packages."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            report.results.append(
                CheckResult(name="outdated-deps", status="warn", message="Could not determine outdated packages")
            )
            return
        outdated = json.loads(proc.stdout) if proc.stdout.strip() else []
    except Exception:
        report.results.append(
            CheckResult(name="outdated-deps", status="warn", message="Failed to run pip list --outdated")
        )
        return

    flagged = [p for p in outdated if p.get("name", "").lower() in _SECURITY_PACKAGES]
    if flagged:
        for pkg in flagged:
            report.results.append(
                CheckResult(
                    name="outdated-deps",
                    status="warn",
                    message=(
                        f"{pkg['name']} {pkg.get('version', '?')} -> "
                        f"{pkg.get('latest_version', '?')} (security-relevant)"
                    ),
                )
            )
    else:
        report.results.append(
            CheckResult(name="outdated-deps", status="pass", message="Security-relevant packages are up to date")
        )


def check_security_headers(root: Path, report: AuditReport) -> None:
    """Check if CORS, CSP, and HSTS middleware are configured."""
    all_text = ""
    for py in _collect_py_files(root):
        try:
            all_text += py.read_text(errors="ignore") + "\n"
        except OSError:
            continue

    missing: list[str] = []
    if "CORSMiddleware" not in all_text:
        missing.append("CORS middleware")
    if "CSP" not in all_text and "Content-Security-Policy" not in all_text:
        missing.append("Content-Security-Policy header")
    if "HSTS" not in all_text and "Strict-Transport-Security" not in all_text:
        missing.append("HSTS (Strict-Transport-Security) header")

    if missing:
        report.results.append(
            CheckResult(
                name="security-headers",
                status="warn",
                message=f"Missing: {', '.join(missing)}",
            )
        )
    else:
        report.results.append(
            CheckResult(name="security-headers", status="pass", message="CORS, CSP, and HSTS configured")
        )


def check_sql_injection(root: Path, report: AuditReport) -> None:
    """Scan for raw SQL string formatting via f-strings."""
    findings: list[CheckResult] = []
    for py in _collect_py_files(root):
        try:
            lines = py.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            stripped = text.lstrip()
            if stripped.startswith("#"):
                continue
            if _SQL_KEYWORDS.search(text):
                findings.append(
                    CheckResult(
                        name="sql-injection",
                        status="fail",
                        message="Possible SQL injection — raw SQL in f-string",
                        file=str(py.relative_to(root)),
                        line=lineno,
                    )
                )

    if findings:
        report.results.extend(findings)
    else:
        report.results.append(
            CheckResult(name="sql-injection", status="pass", message="No raw SQL f-string patterns detected")
        )


def check_debug_mode(root: Path, report: AuditReport) -> None:
    """Check for DEBUG=True or reload=True in production configs."""
    findings: list[CheckResult] = []
    debug_pat = re.compile(r"""\bDEBUG\s*=\s*True\b""")
    reload_pat = re.compile(r"""\breload\s*=\s*True\b""")

    for py in _collect_py_files(root):
        try:
            lines = py.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            stripped = text.lstrip()
            if stripped.startswith("#"):
                continue
            if debug_pat.search(text):
                findings.append(
                    CheckResult(
                        name="debug-mode",
                        status="warn",
                        message="DEBUG=True found — ensure this is not active in production",
                        file=str(py.relative_to(root)),
                        line=lineno,
                    )
                )
            if reload_pat.search(text):
                findings.append(
                    CheckResult(
                        name="debug-mode",
                        status="warn",
                        message="reload=True found — should be disabled in production",
                        file=str(py.relative_to(root)),
                        line=lineno,
                    )
                )

    if findings:
        report.results.extend(findings)
    else:
        report.results.append(
            CheckResult(name="debug-mode", status="pass", message="No DEBUG/reload flags detected")
        )


def check_env_in_git(root: Path, report: AuditReport) -> None:
    """Check if .env is listed in .gitignore."""
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        report.results.append(
            CheckResult(name="env-in-git", status="warn", message=".gitignore not found — .env may be tracked")
        )
        return
    try:
        content = gitignore.read_text(errors="ignore")
    except OSError:
        report.results.append(
            CheckResult(name="env-in-git", status="warn", message="Could not read .gitignore")
        )
        return

    # Check for .env entry (exact line or pattern)
    for line in content.splitlines():
        stripped = line.strip()
        if stripped in (".env", ".env*", ".env.*", "*.env"):
            report.results.append(
                CheckResult(name="env-in-git", status="pass", message=".env is in .gitignore")
            )
            return

    report.results.append(
        CheckResult(name="env-in-git", status="fail", message=".env is NOT listed in .gitignore")
    )


def check_weak_jwt(root: Path, report: AuditReport) -> None:
    """Check for weak JWT configuration (short expiry, weak algorithms)."""
    weak_algos = {"HS256", "none"}
    short_expiry_pat = re.compile(r"""(?:exp|expire|expiry|ttl)\s*=\s*(\d+)""", re.IGNORECASE)

    findings: list[CheckResult] = []
    for py in _collect_py_files(root):
        try:
            lines = py.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            stripped = text.lstrip()
            if stripped.startswith("#"):
                continue
            # Weak algorithm
            for algo in weak_algos:
                if f'algorithm="{algo}"' in text or f"algorithm='{algo}'" in text:
                    findings.append(
                        CheckResult(
                            name="weak-jwt",
                            status="warn",
                            message=f"Weak JWT algorithm: {algo}",
                            file=str(py.relative_to(root)),
                            line=lineno,
                        )
                    )
            # "none" algorithm
            if re.search(r"""algorithms?\s*=\s*\[?\s*['"]none['"]""", text, re.IGNORECASE):
                findings.append(
                    CheckResult(
                        name="weak-jwt",
                        status="fail",
                        message="JWT 'none' algorithm detected — critical vulnerability",
                        file=str(py.relative_to(root)),
                        line=lineno,
                    )
                )
            # Short expiry (< 60 seconds)
            m = short_expiry_pat.search(text)
            if m and "jwt" in text.lower():
                val = int(m.group(1))
                if val < 60:
                    findings.append(
                        CheckResult(
                            name="weak-jwt",
                            status="warn",
                            message=f"JWT expiry very short ({val}s) — may cause issues",
                            file=str(py.relative_to(root)),
                            line=lineno,
                        )
                    )

    if findings:
        report.results.extend(findings)
    else:
        report.results.append(
            CheckResult(name="weak-jwt", status="pass", message="No weak JWT configuration detected")
        )


def check_rate_limiting(root: Path, report: AuditReport) -> None:
    """Check if rate limiting middleware is configured."""
    all_text = ""
    for py in _collect_py_files(root):
        try:
            all_text += py.read_text(errors="ignore") + "\n"
        except OSError:
            continue

    rate_limit_indicators = [
        "RateLimitMiddleware",
        "slowapi",
        "SlowAPI",
        "Limiter",
        "rate_limit",
        "ratelimit",
        "throttle",
        "ThrottleMiddleware",
    ]

    for indicator in rate_limit_indicators:
        if indicator in all_text:
            report.results.append(
                CheckResult(name="rate-limiting", status="pass", message="Rate limiting appears configured")
            )
            return

    report.results.append(
        CheckResult(
            name="rate-limiting",
            status="warn",
            message="No rate limiting middleware detected — consider adding slowapi or similar",
        )
    )


def check_open_cors(root: Path, report: AuditReport) -> None:
    """Check for allow_origins=["*"] in production."""
    findings: list[CheckResult] = []
    open_cors_pat = re.compile(r"""allow_origins\s*=\s*\[\s*['"\*'"]\s*\]""")

    for py in _collect_py_files(root):
        try:
            lines = py.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            stripped = text.lstrip()
            if stripped.startswith("#"):
                continue
            if open_cors_pat.search(text):
                findings.append(
                    CheckResult(
                        name="open-cors",
                        status="warn",
                        message='allow_origins=["*"] — CORS is fully open',
                        file=str(py.relative_to(root)),
                        line=lineno,
                    )
                )

    if findings:
        report.results.extend(findings)
    else:
        report.results.append(
            CheckResult(name="open-cors", status="pass", message="No open CORS wildcard origins detected")
        )


# ---------------------------------------------------------------------------
# Auto-fix helpers
# ---------------------------------------------------------------------------

def _autofix_env_in_git(root: Path) -> bool:
    """Append ``.env`` to ``.gitignore`` if missing."""
    gitignore = root / ".gitignore"
    try:
        if gitignore.exists():
            content = gitignore.read_text(errors="ignore")
            if not content.endswith("\n"):
                content += "\n"
            content += ".env\n"
            gitignore.write_text(content)
        else:
            gitignore.write_text(".env\n")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

_STATUS_ICON = {"pass": "[green]PASS[/green]", "warn": "[yellow]WARN[/yellow]", "fail": "[red]FAIL[/red]"}


def _format_text(report: AuditReport) -> None:
    """Print results to the console using Rich."""
    output.console.print()
    output.console.print("[bold cyan]Security Audit Report[/bold cyan]")
    output.console.print()

    for r in report.results:
        icon = _STATUS_ICON[r.status]
        location = ""
        if r.file:
            location = f" [dim]({r.file}"
            if r.line is not None:
                location += f":{r.line}"
            location += ")[/dim]"
        output.console.print(f"  {icon}  {r.message}{location}")

    output.console.print()
    output.console.print(
        f"[bold]Summary:[/bold] "
        f"[green]{report.pass_count} passed[/green], "
        f"[yellow]{report.warn_count} warnings[/yellow], "
        f"[red]{report.fail_count} failed[/red]"
    )
    output.console.print()


def _format_json(report: AuditReport) -> None:
    """Print results as JSON."""
    data = {
        "results": report.to_dicts(),
        "summary": {
            "pass": report.pass_count,
            "warn": report.warn_count,
            "fail": report.fail_count,
        },
    }
    click.echo(json.dumps(data, indent=2))


def _format_markdown(report: AuditReport) -> None:
    """Print results as Markdown."""
    lines = ["# Security Audit Report", ""]
    lines.append("| Status | Check | Message | Location |")
    lines.append("|--------|-------|---------|----------|")
    for r in report.results:
        status_label = r.status.upper()
        location = ""
        if r.file:
            location = r.file
            if r.line is not None:
                location += f":{r.line}"
        lines.append(f"| {status_label} | {r.name} | {r.message} | {location} |")
    lines.append("")
    lines.append(
        f"**Summary:** {report.pass_count} passed, "
        f"{report.warn_count} warnings, {report.fail_count} failed"
    )
    click.echo("\n".join(lines))


_FORMATTERS = {
    "text": _format_text,
    "json": _format_json,
    "markdown": _format_markdown,
}


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command("audit")
@click.option("--fix", is_flag=True, help="Auto-fix issues where possible")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "markdown"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--strict", is_flag=True, help="Treat warnings as errors (exit code 1)")
def audit_cmd(fix: bool, fmt: str, strict: bool) -> None:
    """Run security audit checks on the current FastX project.

    \b
    Examples:
        fastx audit                  # Run all security checks
        fastx audit --fix            # Auto-fix what's possible
        fastx audit --format json    # JSON output
        fastx audit --strict         # Warnings become errors
    """
    root = resolve_fastmvc_project_root(Path.cwd())
    report = AuditReport()

    # Run all checks
    check_hardcoded_secrets(root, report)
    check_outdated_deps(report)
    check_security_headers(root, report)
    check_sql_injection(root, report)
    check_debug_mode(root, report)
    check_env_in_git(root, report)
    check_weak_jwt(root, report)
    check_rate_limiting(root, report)
    check_open_cors(root, report)

    # Auto-fix pass
    if fix:
        fixed: list[str] = []
        for r in report.results:
            if r.name == "env-in-git" and r.status in ("fail", "warn"):
                if _autofix_env_in_git(root):
                    r.status = "pass"
                    r.message = ".env added to .gitignore (auto-fixed)"
                    fixed.append("env-in-git")

        if fixed and fmt == "text":
            output.console.print(f"[bold green]Auto-fixed:[/bold green] {', '.join(fixed)}")

    # Output
    _FORMATTERS[fmt](report)

    # Exit code
    if report.fail_count > 0:
        sys.exit(1)
    if strict and report.warn_count > 0:
        sys.exit(1)


def register_audit(cli: click.Group) -> None:
    """Register the ``audit`` command on the root CLI group."""
    cli.add_command(audit_cmd)
