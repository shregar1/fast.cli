# Checkpoints (`fast checkpoint`)

The **`fast checkpoint`** command keeps a small **JSON ledger** of git commit markers so you can **remember safe points** and **revert** with confidence when something goes wrong.

## Where the file lives

`checkpoint.json` is written at the **git repository root** (the directory that contains `.git`), no matter which subdirectory you run `fast` from.

Example:

```text
/Users/you/muse.app/mobile.muse.app/   ← git root
├── .git/
├── checkpoint.json                    ← created here
├── src/
└── ...
```

If you are not inside a git work tree, the command exits with an error.

## File shape

`checkpoint.json` is plain JSON:

```json
{
  "version": 1,
  "checkpoints": [
    {
      "id": "cp-0001",
      "created_at": "2026-03-28T12:34:56.789012+00:00",
      "git_commit": "full-sha…",
      "git_commit_short": "abc1234",
      "branch": "main",
      "message": "Before big refactor",
      "dirty": false
    }
  ]
}
```

- **`dirty`**: `true` if the working tree had uncommitted changes when you saved. The stored SHA is still **HEAD**; `git reset --hard` will **not** bring back uncommitted work.

## Commands

| Command | Purpose |
|--------|---------|
| `fast checkpoint save [-m "note"]` | Append a checkpoint for **current HEAD**. Fails if the tree is dirty unless you pass **`--allow-dirty`**. |
| `fast checkpoint list` | Print all checkpoints in a table. |
| `fast checkpoint show <id>` | Show metadata and **suggested git commands** (`git reset --hard …`, `git checkout …`). |
| `fast checkpoint revert <id>` | By default: **print** `git reset --hard <sha>` only (dry run). With **`--execute`**: run it after confirmation (use **`--yes`** to skip the prompt). |

### Examples

```bash
cd /path/to/your/repo

# After a good test run or release tag
fast checkpoint save -m "Green tests before auth refactor"

# Later, see what you saved
fast checkpoint list
fast checkpoint show cp-0001

# Inspect the command (no changes)
fast checkpoint revert cp-0001

# Actually reset (destructive)
fast checkpoint revert cp-0001 --execute --yes
```

## Safety notes

- **Revert is destructive.** `git reset --hard` discards uncommitted changes and moves the current branch. Prefer **`revert` without `--execute`** first, or use **`show`** to copy commands.
- **Not a backup:** Checkpoints only store **commit SHAs**. They do not snapshot untracked files or the working tree. Commit or stash important work before risky changes.
- **Version control:** You may commit `checkpoint.json` to share team “known good” points, or add it to `.gitignore` if it is personal.

## Website / PyPI

This page lives in the **fastmvc-cli** repository (`docs/CHECKPOINTS.md`). On GitHub, open the same path in the default branch; PyPI’s **Project-URL → Documentation** may point to **Getting started**—link here from your own site or README as needed.
