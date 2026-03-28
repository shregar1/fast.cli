# Getting started — about 15 minutes

This guide gets you from **zero** to a **generated FastMVC project**, a **healthy toolchain check**, and a clear **next step**. It assumes a normal laptop with **Python 3.10+** and **pip**.

## 1. Install the CLI (2 min)

```bash
pip install "fastmvc-cli[interactive]"
```

The **`[interactive]`** extra installs **Questionary** so `fast generate` can run the full wizard. Without it, the CLI falls back to simpler prompts.

Optional: verify the install:

```bash
fast --version
fast doctor
```

## 2. Scaffold a project (5–10 min)

**Fastest path** — non-interactive defaults in the current directory tree:

```bash
mkdir ~/playground && cd ~/playground
fast quickstart --name my_api
```

**Full wizard** — prompts for paths, author, Python version, venv, etc.:

```bash
fast generate
```

**Explicit flags** (CI / scripts):

```bash
fast new --name my_api --path ./my_api --email you@example.com
```

Follow the on-screen steps: choose a project name, target folder, and whether to create a venv and install dependencies. When generation finishes, the CLI prints **next steps** (cd, activate venv, copy `.env`, run the app).

## 3. Sanity-check your environment (1 min)

From anywhere:

```bash
fast doctor
```

You should see **Python**, **fast_cli** version, **PATH tools** (git, alembic, pre-commit, …), and **optional Python packages**. If something is missing, **`doctor`** suggests install commands.

## 4. Open the generated project (5+ min)

```bash
cd my_api   # or the path you chose
```

Typical follow-ups (exact commands appear in the CLI output after generation):

1. **Activate** the virtual environment (`source .venv/bin/activate` on Unix).
2. **Copy** `.env.example` → `.env` and adjust secrets.
3. **Run** the application (often `python app.py` or `uvicorn` — see the generated README).

Open **`http://localhost:8000/docs`** (or the port your template uses) for the interactive API docs.

## 5. Go deeper

| Goal | Command / doc |
|------|----------------|
| Add a versioned API operation | `fast add resource --folder … --resource …` (from project root) |
| Database migrations | `fast db migrate` / `fast db upgrade` (with `alembic.ini` in tree) |
| API reference stubs | `fast docs generate` |
| Shell tab completion | `fast completion bash` (or `zsh` / `fish`) |

See the main **[README](../README.md)** for the full command map.

## See it run (optional)

Record or share a terminal session with [asciinema](https://asciinema.org/) (`asciinema rec`, then `asciinema upload`) and link it from your README or docs.
