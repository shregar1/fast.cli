# Changelog

All notable changes to **fastmvc-cli** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Actions CI: **`test`** job (pytest + coverage on PRs / pushes to `main` / `master`).
- GitHub Actions **`lint`** job (**Ruff** + **Mypy**).
- `CHANGELOG.md` in **`[project.urls]`**; **`py.typed`** (PEP 561).
- `CONTRIBUTING.md`, `SECURITY.md`, Dependabot (weekly `pip` + GitHub Actions), expanded PyPI troubleshooting in README.

## [1.5.0] — 2026-03-28

### Added

- Initial public release track: `fast`, `fast-cli`, `fastmvc` entry points; project generation;
  `add resource`, `db`, `docs`, `cache`, `tasks`, `decimate`, `setup-commit-log`; user defaults
  (`~/.config/fastmvc/defaults.toml`); `doctor` / `check-env`; `completion`; PyPI distribution
  **fastmvc-cli**.
