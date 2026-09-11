# AGENTS.md

Instructions for any coding agent working in this repository. Canonical for both
Claude Code (via `CLAUDE.md`, which imports this file) and Codex (which reads
this file directly).

## What this repository is

A fork of [IDAES/idaes-pse](https://github.com/IDAES/idaes-pse) at `70a8f4fe1`
(v2.13.0rc0), integrating Rust [Arrow](https://arrow.apache.org/) and
[DataFusion](https://datafusion.apache.org/) into data-heavy parts of the
framework. Not an official IDAES release; see `FORK.md`.

The Python tree under `idaes/` keeps upstream's layout **deliberately**, so
changes stay mappable to upstream and merges stay cheap.

## Start here, every session

```bash
just doctor        # is this working copy able to do work?
just bootstrap     # if it complains -- idempotent, safe to re-run
just --list        # the command surface
```

`just --list` is the contract. Prefer a recipe over an ad hoc command: recipes
own the feature flags, profiles, report paths and tool paths, so they can change
without you re-learning them. If no recipe fits, say so rather than improvising
a long command line.

`direnv` activates the environment on `cd` (run `direnv allow` once). It never
installs or downloads — `just bootstrap` does that, visibly.

## Prime directives

1. **Do not restructure `idaes/`.** Added files are cheap; modified upstream
   files are recurring cost at every merge. `just divergence` measures it.
2. **Every accelerated function keeps its Python implementation.** `idaes/accel/`
   dispatches between them. Deleting the Python path is a separate, deliberate
   decision, never a side effect.
3. **Parity is bit-exact by default.** A loosened tolerance requires a written
   justification in the `ParityCase`; `parity.register()` enforces that.
4. **Report a failure count with its baseline.** "34 failed" is not information
   until you know whether the baseline was 34.
5. **Use the tool from `.venv`, never `$PATH`.** Versions are pinned in
   `pyproject.toml` under `[dependency-groups]`.

## Repository map

| Path | What it is | How to treat it |
|---|---|---|
| `idaes/` | Upstream Python, ~874 files | Edit narrowly and only where needed |
| `idaes/accel/` | Fork-authored dispatch layer + parity harness | Ours; full strictness applies |
| `rust/` | The entire Cargo workspace | Ours; see `rust/README.md` |
| `scripts/` | `doctor.py`, `bootstrap.sh`, baseline and lint helpers | Ours |
| `sgrules/` | Custom structural lint rules (ast-grep) | Add rules here, not to ruff |
| `docs-code-update/library_ref/` | Pinned third-party API references | Read-only; reached through skills |
| `docs-code-update/authoritative_design/` | **Off-limits.** See below | Read, never write |
| `docs-code-update/plans/` | Design and implementation plans | Write plans here |

## Where authority lives

Do not restate these; cite them.

- **`docs-code-update/authoritative_design/32_repository_engineering.md`** — the
  authoritative as-is description of `pyproject.toml`, the pytest configuration,
  the marker taxonomy, coverage, headers and the CI job graph.
- **`rust/Cargo.toml` header comment** — the version pins for the Arrow/
  DataFusion stack and the reasoning for each.
- **`pyproject.toml [dependency-groups]`** — the pinned ruff/pyrefly/maturin.
- **`docs-code-update/library_ref/`** — pinned API references, routed by the
  skills in `.codex/skills/`. Use `just lib-outline <doc>` to see a document's
  chapter structure before reading it; several are 25k+ lines.

## Invariants

- **One Arrow/DataFusion type universe.** Exactly one version of `arrow`,
  `parquet`, `object_store` and `datafusion` in the graph. Two majors make
  `downcast_ref` return `None` with no compile error. Enforced by
  `just one-type-universe`, `cargo deny check bans`, and the
  `arrow-through-datafusion` ast-grep rule.
- **`panic = "unwind"`** in the release profile. PyO3 converts unwinds into
  Python exceptions; `abort` would take the interpreter down.
- **Never `target-cpu=native`.** It lets LLVM contract `a*b + c` into an FMA and
  changes floating-point results between your machine and CI.
- **Exactly one of `unit`/`component`/`integration`/`performance`** per test.
  `idaes/conftest.py::pytest_runtest_setup` hard-fails otherwise.
- **Headers:** the 12-line IDAES block on `.py` under `idaes/` (`just py-headers`),
  a 4-line SPDX header on `.rs` (`just headers-rust`).
- **`@accelerate` decorates module-level functions only.** A bound method's
  `self` would cross the FFI boundary as the first positional argument.

## Gotchas that have already cost time here

Each of these is a real incident in this repository, not a hypothetical.

- **Porting an untyped Python function means porting its coercion behaviour.**
  `prime_number_generator(2.9)` returns `[2, 3, 5]` because
  `while len(prime_list) < 2.9` stops at three. An `i64` Rust signature raised
  `TypeError` where Python returned a list. Parity unit tests missed it; the
  full suite under `IDAES_ACCEL=force` caught it.
- **`yaml.safe_load` silently accepts duplicate keys** (last wins). Adding an
  `if:` to a job that already had one disabled the guard invisibly. Run
  `just lint-workflows`.
- **A `#` line inside a `>-` folded YAML scalar is content, not a comment.** It
  gets evaluated as part of the expression.
- **GitHub Actions does not support YAML anchors.** Duplicate the block.
- **On `windows-*` runners the default shell is PowerShell.** Set `shell: bash`
  explicitly or your bash script dies with a `ParserError`.
- **The test suite needs `idaes get-extensions`.** Without it
  `idaes/core/util/functions.py` evaluates `os.path.isfile(None)` and pytest
  aborts during *collection* — every test, not just the ones needing solvers.
  `just bootstrap-solvers`.
- **Under `IDAES_ACCEL=force` coverage collapses** (the Python implementations
  stop executing). Never upload coverage from that job.
- **Ruff has no plugin API.** Custom rules go in `sgrules/` (ast-grep), not ruff.

## Verifying work — what each command actually proves

| Command | Proves | Does not prove |
|---|---|---|
| `just ci-fast` | the Rust workspace compiles, lints, and its unit tests and doctests pass | nothing about Python, features, or other targets |
| `just quality` | formatting, lint and types are no worse than baseline; repo config is valid | that the code works |
| `just py-test-noaccel` | the pure-Python path is intact | nothing about the Rust path |
| `just py-test-accel` | the Rust path behaves identically at real call sites | nothing about inputs not exercised |
| `just accel-wheel-verify` | a built wheel installs and imports in a clean environment | nothing about other platforms |
| `just miri-seeds <pkg> 32` | no UB across 32 explored interleavings | nothing about unexplored ones |
| `hyperfine` before/after | an outcome difference with a distribution | nothing about the mechanism |

Never report "tests pass" without naming the command, the mode, and the baseline.

## Off-limits: `docs-code-update/authoritative_design/`

A separate workflow owns this directory. It has its own brief
(`_scripts/AUTHOR_BRIEF.md`), a file-ownership ledger, generated inventories
under `_generated/`, and mechanically checked constraints including a banned-word
list and source anchors pinned to `70a8f4fe1`.

- **Read it** — it is the best available description of upstream's architecture.
- **Never write to it.** A `PreToolUse` hook blocks edits; that is intentional.
- It describes upstream **as-is at the pinned revision** and deliberately
  excludes this fork's work. Anything it says about `idaes/` may predate changes
  here, and it never mentions `idaes/accel/`.

## Agent runtimes

- **Claude Code** reads `CLAUDE.md`, which imports this file. Project settings,
  hooks and rules live in `.claude/`.
- **Codex** reads this file. Note that Codex runs here with
  `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`, so this
  file is its only guidance — be correspondingly careful with destructive
  commands.
- Skills in `.codex/skills/` route to the pinned references. They are shared by
  both runtimes; `just lint-skills` verifies every path still resolves.
