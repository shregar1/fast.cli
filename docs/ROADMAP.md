# Roadmap

Informal priorities for **fastmvc-cli** and how it surfaces the FastMVC stack. Nothing here is a fixed commitment; track releases in [CHANGELOG.md](../CHANGELOG.md).

## Near term

- **Doctor UX** — Actionable install hints for missing tools and optional packages (landed incrementally).
- **Docs** — Keep **Getting started** aligned with `generate` / `quickstart` behavior and template output.
- **CI** — Broad Python + OS matrix and subprocess smoke tests for real entry points.

## Medium term

- **Examples** — Official sample repos (auth, CRUD, background tasks) linked from the org README.
- **Editor story** — Documented VS Code / Dev Container flows for generated projects.
- **Versioning** — Clear notes when bumping **`fast-*`** lower bounds in `pyproject.toml`.

## Longer term

- **Observability** — Surface logging / tracing hooks in generated apps (coordination with **fast-mvc** templates).
- **Testing** — Optional `fast test` or documented pytest patterns matching generated layout.

Suggestions welcome via [GitHub Issues](https://github.com/fastmvc/fast.cli/issues) (use the repo URL from `pyproject.toml` if it differs).
