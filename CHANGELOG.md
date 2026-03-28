# Changelog

All notable changes to **fastmvc-cli** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **RELEASING.md** — Maintainer release checklist, PyPI verification, rollback (yank / patch).
- **docs/DEPENDENCIES.md** — Trust boundaries and pinning guidance for the `fast-*` stack.
- **CI** — **`smoke`** job (Linux + Windows, Python 3.11–3.12) running subprocess CLI tests (`tests/test_smoke_cli.py`) with `--no-cov`.
- **Publish workflow** — Runs the full test suite before build; **smoke-installs** the built wheel then uploads to PyPI.
- **Terminal UX** — Compact banner when `FAST_CLI_MINIMAL_BANNER=1` or terminal width `< 56` columns; ASCII-friendly subtitle when stdout encoding is ASCII; tests in `tests/test_terminal_output.py`.

### Changed

- **SECURITY.md** — Supply-chain notes, dependency posture, and response expectations.

## [1.5.0] — 2026-03-28

### Added

- Initial public release track: `fast`, `fast-cli`, `fastmvc` entry points; project generation;
  `add resource`, `db`, `docs`, `cache`, `tasks`, `decimate`, `setup-commit-log`; user defaults
  (`~/.config/fastmvc/defaults.toml`); `doctor` / `check-env`; `completion`; PyPI distribution
  **fastmvc-cli**.
