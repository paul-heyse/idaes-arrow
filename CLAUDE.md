@AGENTS.md

# Claude Code specifics

Everything above applies. This file adds only what is Claude-specific.

A real file rather than a symlink to `AGENTS.md`: `windows-2022` is in the CI
matrix, and symlinks do not survive a checkout there without developer mode.

## At the start of a session

The `SessionStart` hook runs `scripts/doctor.py`, so the environment status is
already in context. If it reported a blocking issue, fix that before anything
else — a failing `just py-test` with no solver binaries is a wasted loop.

## What is configured for you

- **`.claude/settings.json`** — read-only commands are pre-approved; `git push`,
  `git commit` and any publish command ask; writes under
  `docs-code-update/authoritative_design/`, `.git/` and `rust/target/` are denied.
- **`.claude/hooks/`** — `SessionStart` runs the doctor; `PostToolUse` formats
  the file you just edited with the pinned `ruff`/`cargo fmt`, so formatting-only
  CI failures cannot happen; `PreToolUse` blocks writes to protected paths.
- **`.claude/rules/`** — path-scoped guidance that loads only when you touch
  matching files: `rust.md`, `python-accel.md`, `upstream.md`, `ci.md`.
- **`.claude/skills`** is a symlink to `.codex/skills`, so both runtimes read one
  copy and cannot drift. On Windows without developer mode git checks that out as
  a text file rather than a link; if your skills are missing there, that is why —
  copy the directory instead. `just lint-skills` verifies every reference path.

## Use plan mode when

The change spans both languages, touches the FFI boundary, or modifies a file
under `idaes/` that upstream also maintains. The merge cost of an upstream edit
is high enough to be worth a plan.

## Subagents available

- `parity-auditor` — hunts Python/Rust divergence, especially argument coercion
  and input mutation. That class of bug has already shipped here once.
- `ci-doctor` — reads a failing workflow run, isolates the step, proposes the
  minimal fix.

## Writing plans

Put them in `docs-code-update/plans/`, not `~/.claude/plans/`. Plans in your home
directory are invisible to Codex and to the next session; in the repo they are
readable by both and reviewable in a pull request. `just plan <name>` creates a
stub.
