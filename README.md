# fastmvc-cli

**FastMVC CLI** — a console toolkit for generating FastAPI / FastMVC projects, scaffolding APIs, running database migrations, and maintaining a few operational utilities.

Install from PyPI as **`fastmvc-cli`** (the name **`fast-cli`** on PyPI is a separate project you do not control). After install, use the **`fast`** command (shortest), or **`fast-cli`** / **`fastmvc`** scripts — same as before.

## Why FastMVC?

**FastMVC** is opinionated structure for production **FastAPI** apps: controllers, services, DTOs, and migrations live in predictable places so teams spend less time debating folders and more time shipping. This package is the **front door**—**`fast`** scaffolds projects (**`generate`**, **`quickstart`**), adds versioned APIs (**`add resource`**), wraps **Alembic** (**`db`**), and plugs into the optional **`fast-*`** stack (caching, tasks, dashboards) when you need it.

It does **not** replace FastAPI; it **organizes** how you build on it. If you want raw minimalism, use FastAPI alone. If you want **convention + velocity** for backend teams, use FastMVC—and start with **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** (~15 minutes from install to a generated tree).

**[Roadmap](docs/ROADMAP.md)** · **[Examples](examples/README.md)** · **Dev container:** open this repo in VS Code → “Reopen in Container” (see [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)).

---

## Contents

- [Why FastMVC?](#why-fastmvc)
- [Install](#install)
- [Getting started (15 min)](docs/GETTING_STARTED.md)
- [User defaults (`defaults.toml`)](#user-defaults-defaultstoml)
- [Global options](#global-options)
- [Terminal environment](#terminal-environment)
- [Command map](#command-map)
- [Project generation](#project-generation)
- [Scaffolding (`add`)](#scaffolding-add)
- [Environment (`env`)](#environment-env)
- [Database migrations (`db`)](#database-migrations-db)
- [Documentation (`docs`)](#documentation-docs)
- [Caching (`cache`)](#caching-cache)
- [Background tasks (`tasks`)](#background-tasks-tasks)
- [Cleanup (`decimate`)](#cleanup-decimate)
- [Commit history (`setup-commit-log`)](#commit-history-setup-commit-log)
- [Checkpoints (`checkpoint`)](#checkpoints-checkpoint)
- [Legacy (`make`)](#legacy-make)
- [Related repositories](#related-repositories)
- [Layout](#layout)
- [Publishing to PyPI](#publishing-to-pypi)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Releasing](RELEASING.md) (maintainers: tags, PyPI, rollback)
- [Dependencies & supply chain](docs/DEPENDENCIES.md)
- [Security](SECURITY.md)

---

## Install

```bash
pip install fastmvc-cli
```

Interactive prompts (wizard-style flows) use **Questionary**. Install it for the full experience:

```bash
pip install "fastmvc-cli[interactive]"
```

For development and tests:

```bash
pip install "fastmvc-cli[dev]"
```

Requires **Python 3.10+**.

---

## User defaults (`defaults.toml`)

Optional file: **`~/.config/fastmvc/defaults.toml`** (or **`$XDG_CONFIG_HOME/fastmvc/defaults.toml`**). Example:

```toml
[defaults]
author = "Ada Lovelace"
author_email = "ada@example.com"
email = "ada@example.com"          # alias for author_email
description = "My default blurb"
venv_name = ".venv"
```

These values are merged into **`generate`** / **`new`** (non-interactive and interactive), **`quickstart`**, and **`run_basic`** when no better value is supplied.

---

## Global options

| Option | Description |
|--------|-------------|
| `--version` | Print the package version and exit. |
| `--help` | Show help for the root group or any subcommand. |

Discover everything at once:

```bash
fast --help
fast <command> --help
```

### Terminal environment

| Variable | Effect |
|----------|--------|
| `NO_COLOR` | Disables color ([standard](https://no-color.org/)); Rich respects it. |
| `TERM=dumb` | Minimal capability terminal (colors/styles may be reduced). |
| `FAST_CLI_MINIMAL_BANNER` | Set to `1` / `true` / `yes` for a short text banner instead of the large ASCII wordmark. |
| `COLUMNS` | Terminal width; when very narrow (&lt; 56 columns), a compact banner is used automatically. |

---

## Command map

| Area | Command | Purpose |
|------|---------|---------|
| **Projects** | `generate`, `new`, `quickstart` | Create a new FastMVC-style project (interactive or flags). |
| **Scaffold** | `add resource` | Add a versioned API operation (DTOs, repo, service, controllers). |
| **Scaffold (info)** | `add middleware`, `add auth`, `add test` | Print guidance only (templates not bundled in this package). |
| **Env** | `env` | Generate `.env` from `.env.example` in the current project. |
| **DB** | `db migrate`, `upgrade`, `downgrade`, `reset`, `history`, `status` | Alembic wrappers (run from a directory with `alembic.ini`). |
| **Docs** | `docs generate`, `docs deploy` | Generate MkDocs-style reference stubs; deploy with `mkdocs gh-deploy`. |
| **Cache** | `cache clear`, `cache invalidate` | Clear or tag-invalidate FastCaching (requires `fast_caching`). |
| **Tasks** | `tasks worker`, `list`, `status`, `dashboard` | FastTasks / `fast_platform` workers (optional). |
| **Cleanup** | `decimate` | Delete build/cache artifacts under a path. |
| **Repo tooling** | `setup-commit-log` | Install commit-history recorder + pre-commit hook in any git repo. |
| **Checkpoints** | `checkpoint save`, `list`, `show`, `revert` | Record `checkpoint.json` at the git root with safe commit SHAs; revert hints. **[Docs](docs/CHECKPOINTS.md)** |
| **Diagnostics** | `doctor`, `check-env` | Python version, PATH tools (git, alembic, pre-commit), optional deps. |
| **Shell** | `completion bash|zsh|fish` | Print Click 8 tab-completion script (requires `fast` on PATH). |
| **Legacy** | `make` | Deprecated; forwards to `add` or `env`. |

---

## Project generation

Commands: **`generate`**, **`new`** (alias), **`quickstart`**.

### Behavior

- **`generate`** / **`new`**: If you pass **both** `--name` and `--path`, the CLI runs non-interactively from those options. If either is missing, it starts the **interactive** generator.
- **`quickstart`**: Creates a project with defaults (project name defaults to `my_fastapi_project` unless you set `--name`).

### Options (`generate` / `new`)

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--name` | `-n` | — | Project name. |
| `--path` | `-p` | — | Target directory (use `.` for current dir). |
| `--author` | `-a` | — | Author name. |
| `--email` | `-e` | — | Author email. |
| `--description` | `-d` | — | Short project description. |
| `--version` | `-v` | `0.1.0` | Initial project version string. |
| `--venv` / `--no-venv` | — | `venv` on | Create a virtual environment. |
| `--venv-name` | — | `.venv` | Virtualenv directory name. |
| `--install-deps` / `--no-install-deps` | — | install on | Install dependencies after generation. |

### Options (`quickstart`)

| Option | Default | Description |
|--------|---------|-------------|
| `--name` | `my_fastapi_project` | Project name. |
| `--venv-name` | `.venv` | Virtualenv directory name. |
| `--install-deps` / `--no-install-deps` | install on | Install dependencies after generation. |

### Examples

```bash
fast generate
fast new --name my_api --path ./my_api
fast quickstart --name demo_api
```

---

## Scaffolding (`add`)

Command: **`add resource`**.

Scaffolds a **single versioned operation** in an existing FastMVC layout: request/response DTOs, repository, service, dependency provider, core controller, and FastAPI-facing API controller. The CLI must find `abstractions/controller.py` at the resolved project root.

### Options

| Option | Shorthand | Required | Default | Description |
|--------|-----------|----------|---------|-------------|
| `--folder` | `-f` | yes | — | Folder segment (e.g. `user`, `auth`). |
| `--resource` | `-r` | yes | — | Operation name (e.g. `fetch`, `create`). |
| `--version` | `-v` | no | `v1` | API version (`v1`, `v2`, …). |
| `--crud` / `--no-crud` | — | no | CRUD on | Reserved for future template variants. |

### Example

```bash
cd /path/to/your/fastmvc/project
fast add resource --folder user --resource create --version v1
```

---

## Environment (`env`)

Command: **`env`**.

Generates a **`.env`** file from **`.env.example`** at the resolved FastMVC project root. Fails if `.env` already exists or `.env.example` is missing (see `ProjectBootstrap` in the codebase).

```bash
fast env
```

---

## Database migrations (`db`)

Group: **`db`**. These commands are thin wrappers around the **`alembic`** CLI. Run them from a project directory that contains **`alembic.ini`** (typical FastMVC layout). Install Alembic in that environment: `pip install alembic`.

### `db migrate`

Create a new revision.

| Option | Shorthand | Description |
|--------|-----------|-------------|
| `--message` | `-m` | **Required.** Migration message. |
| `--autogenerate` / `--no-autogenerate` | — | Autogenerate from models (default: on). |

```bash
fast db migrate -m "Add users table"
```

### `db upgrade`

Apply migrations.

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--revision` | `-r` | `head` | Revision to upgrade to. |

```bash
fast db upgrade
fast db upgrade -r head
```

### `db downgrade`

Rollback migrations.

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--revision` | `-r` | `-1` | Target revision (default one step back). |

Confirms before running (Questionary or Click confirm).

### `db reset`

**Destructive:** drops all tables (downgrade to base) and reapplies migrations to `head`.

| Option | Description |
|--------|-------------|
| `--seed` / `--no-seed` | If `--seed`, runs `scripts/seed.py` when present. |

Requires typing **`RESET`** to confirm.

### `db history`

Show migration history.

| Option | Shorthand | Description |
|--------|-----------|-------------|
| `--verbose` / `--no-verbose` | `-v` | More detail from `alembic history`. |

### `db status`

Show current revision, heads, and whether migrations are pending.

---

## Documentation (`docs`)

Group: **`docs`**.

### `docs generate`

Walks **`apis/`** and **`dtos/`** and writes Markdown under **`docs/api/`** (e.g. `endpoints.md`, `dtos.md`, optional `ecosystem.md` for sibling `fast_*` packages). Uses mkdocstrings-style `:::` directives for a later MkDocs build.

```bash
fast docs generate
```

### `docs deploy`

Runs **`mkdocs gh-deploy`** with an optional commit message.

| Option | Shorthand | Default |
|--------|-----------|---------|
| `--message` | `-m` | `Deploy documentation` |

```bash
fast docs deploy -m "Update API docs"
```

---

## Caching (`cache`)

Group: **`cache`**. Requires the **`fast_caching`** package importable in your environment.

### `cache clear`

Purge all resident cache data via the backend.

### `cache invalidate`

Invalidate by tag names.

```bash
fast cache invalidate user-list product-cache
```

---

## Background tasks (`tasks`)

Group: **`tasks`**. Uses **`fast_platform`** task APIs when available.

| Command | Description |
|---------|-------------|
| `tasks worker` | Start a background worker. `--concurrency` / `-c` (default `10`). |
| `tasks list` | List registered task definitions. |
| `tasks status <task_id>` | Show status for one job. |
| `tasks dashboard` | Live table (refresh `--refresh` / `-r` ms, default `1000`). Ctrl+C to exit. |

```bash
fast tasks worker -c 8
fast tasks dashboard -r 2000
```

---

## Cleanup (`decimate`)

Command: **`decimate [LANGUAGE] [PATH]`**.

**Destructive:** removes build/cache artifacts matching built-in patterns. Defaults: language `python`, path `.`.

Supported language keys include **`python`**, **`java`**, **`rust`** (see `ARTIFACTS_BY_LANGUAGE` in `fast_cli.constants`). Virtualenv directories such as `.venv` are skipped during traversal.

```bash
fast decimate python .
fast decimate rust ./my-crate
```

---

## Commit history (`setup-commit-log`)

Command: **`setup-commit-log`**.

Installs the bundled **`git_log_recorder.py`** into **`_maint/scripts/`**, merges a **local** pre-commit hook into **`.pre-commit-config.yaml`** (post-commit stage), and ensures **`.gitignore`** lists:

- `coverage_output.txt`
- `commit_history.json`

| Option | Description |
|--------|-------------|
| `-C`, `--path` | Git repository root (default: current directory). |
| `--install-hooks` / `--no-install-hooks` | Run `pre-commit install` and `pre-commit install --hook-type post-commit` (default: install). |
| `--with-common-hooks` | When **creating** a new `.pre-commit-config.yaml`, also add common hooks (trim whitespace, YAML/JSON checks, etc.). |

```bash
fast setup-commit-log
fast setup-commit-log -C /path/to/repo --no-install-hooks
fast setup-commit-log --with-common-hooks
```

If you skip automatic install:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type post-commit
```

Each commit appends metadata to **`commit_history.json`** at the repository root.

---

## Checkpoints (`checkpoint`)

Record **safe git commit markers** in **`checkpoint.json`** at the **git repository root** (same idea as `mobile.muse.app/checkpoint.json`). Use this before risky refactors so you can **`git reset --hard`** back to a known SHA with clear, documented steps.

Full reference: **[docs/CHECKPOINTS.md](docs/CHECKPOINTS.md)** (also linked from PyPI as **Checkpoints**).

| Command | Description |
|--------|-------------|
| `fast checkpoint save [-m "note"]` | Store current **HEAD** (fails if working tree is dirty unless `--allow-dirty`). |
| `fast checkpoint list` | Show saved checkpoints. |
| `fast checkpoint show <id>` | Print metadata and suggested `git` commands. |
| `fast checkpoint revert <id>` | Dry-run by default; add **`--execute`** to run `git reset --hard` (confirm with **`--yes`** to skip prompt). |

```bash
cd /path/to/your/git/repo
fast checkpoint save -m "Stable before API rewrite"
fast checkpoint list
fast checkpoint show cp-0001
fast checkpoint revert cp-0001              # prints command only
fast checkpoint revert cp-0001 --execute --yes
```

---

## Legacy (`make`)

Command: **`make <resource|env>`**.

Deprecated. Use **`add`** or **`env`** instead.

- `make resource <name>` forwards to `add resource` with fixed defaults.
- `make env` invokes `env`.

---

## Related repositories

| | |
|--|--|
| **FastMVC framework** (sibling checkout) | `../fast_mvc` |
| **GitHub** | [github.com/shregar1/fast.mvc](https://github.com/shregar1/fast.mvc) |

This repo’s **`package metadata`** references [github.com/fastmvc/fast.cli](https://github.com/fastmvc/fast.cli). The PyPI distribution is **`fastmvc-cli`**.

---

## Publishing to PyPI

The PyPI project name is **`fastmvc-cli`** (`name` in `pyproject.toml`). Create it under your PyPI account on first successful upload. Bump **`__version__`** in `fast_cli/__init__.py` before each release.

**Maintainer checklist** (tags, CI, wheel smoke test, rollback): **[RELEASING.md](RELEASING.md)**.

### Troubleshooting uploads

If you see **`403 Forbidden`** and a message like *isn’t allowed to upload to project `some-name`*:

- The **PyPI project name** may already exist and be owned by another account (pick a name you control — this repo publishes **`fastmvc-cli`**, not **`fast-cli`**).
- Your **API token** may be scoped to a **different** PyPI project or to the account without permission for this project. Create a token **scoped to `fastmvc-cli`** (or use an **entire-account** token) under [API tokens](https://pypi.org/manage/account/token/), and retry.
- **Trusted publishing** (GitHub Actions) does not use a token; ensure the **pending publisher** on PyPI matches this repo and **`publish-pypi.yml`**.

Ask the maintainer of the target project to add you as a collaborator if you need to upload to their package.

**GitHub Actions** uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) (OpenID Connect) — no PyPI token stored in the repo. **Local** uploads still use a [PyPI API token](https://pypi.org/manage/account/token/) with Twine.

### Local build and upload

Install build tools (included in the **`dev`** extra):

```bash
pip install "fastmvc-cli[dev]"   # or: pip install build twine
python -m build               # writes dist/fast_cli-*.tar.gz and .whl
twine check dist/*
```

Upload with your token. The username must be exactly **`__token__`**; the password is the **full token** (including the `pypi-` prefix):

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD='pypi-AgEIcHlwaS5vcmc...'   # paste your token
twine upload dist/*
```

On one line:

```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD='pypi-…' twine upload dist/*
```

Never commit the token or add it to the repo—use shell exports or a password manager.

### GitHub Actions (trusted publishing)

The workflow **`.github/workflows/publish-pypi.yml`** runs when you push a tag matching **`v*`** (for example `v1.5.1`). It publishes with **OIDC** (`id-token: write`); you do **not** need a **`PYPI_API_TOKEN`** secret for this path.

**One-time:** In PyPI → your project → **Manage** → **Publishing** → add a **pending publisher**: type **GitHub**, set the repository and workflow file **`publish-pypi.yml`**, and save. See [PyPI: adding a GitHub publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

Then:

```bash
git tag v1.5.1
git push origin v1.5.1
```

The tag should match **`__version__`** in `fast_cli/__init__.py`.

---

## Layout

```
fast.cli/
├── fast_cli/
│   ├── app.py              # CLI entry point
│   ├── bundled/          # git_log_recorder.py (source for setup-commit-log)
│   └── commands/         # Command groups and implementations
├── _maint/scripts/       # Optional copy in other repos (see setup-commit-log)
├── .pre-commit-config.yaml
└── …
```

For maintainer notes, see **`_maint/README.md`**.
