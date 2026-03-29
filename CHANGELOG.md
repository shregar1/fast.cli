# Changelog

All notable changes to **fastmvc-cli** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`fast checkpoint`** — `save` / `list` / `show` / `revert` with **`checkpoint.json`** at the git root; **[docs/CHECKPOINTS.md](docs/CHECKPOINTS.md)**; PyPI **Checkpoints** URL.
- **docs/GETTING_STARTED.md** — ~15-minute path: install → quickstart/generate → doctor → next steps.
- **docs/ROADMAP.md** — Informal product/CLI roadmap.
- **examples/README.md** — How “official” examples are produced via `fast quickstart` / `fast generate`.
- **.devcontainer/devcontainer.json** — Python 3.12 dev container with editable `[dev]` install.
- **`fast doctor`** — “Ready” panel when checks pass; **Suggested next steps** panel with install hints for missing PATH tools and optional packages.

- **RELEASING.md** — Maintainer release checklist, PyPI verification, rollback (yank / patch).
- **docs/DEPENDENCIES.md** — Trust boundaries and pinning guidance for the `fast-*` stack.
- **CI** — **`smoke`** job (Linux + Windows, Python 3.11–3.12) running subprocess CLI tests (`tests/test_smoke_cli.py`) with `--no-cov`.
- **Publish workflow** — Runs the full test suite before build; **smoke-installs** the built wheel then uploads to PyPI.
- **Terminal UX** — Compact banner when `FAST_CLI_MINIMAL_BANNER=1` or terminal width `< 56` columns; ASCII-friendly subtitle when stdout encoding is ASCII; tests in `tests/test_terminal_output.py`.

### Changed

- **README** — **Why FastMVC?** positioning, links to getting started, roadmap, examples, dev container.
- **`project.urls` Documentation** — Points to **docs/GETTING_STARTED.md** on GitHub.
- **SECURITY.md** — Supply-chain notes, dependency posture, and response expectations.

## [1.5.0] — 2026-03-28

### Added

- Initial public release track: `fast`, `fast-cli`, `fastmvc` entry points; project generation;
  `add resource`, `db`, `docs`, `cache`, `tasks`, `decimate`, `setup-commit-log`; user defaults
  (`~/.config/fastmvc/defaults.toml`); `doctor` / `check-env`; `completion`; PyPI distribution
  **fastmvc-cli**.
