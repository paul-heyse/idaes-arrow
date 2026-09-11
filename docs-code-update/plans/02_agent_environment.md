# Agent-driven development environment for `paul-heyse/idaes-arrow`

## Context

The fork exists and the Rust/Arrow acceleration layer is live — fork setup, the `rust/` workspace,
the `idaes/accel/` dispatch layer with its parity harness, and four CI workflows are committed and
pushed. What does **not** exist is the scaffolding that lets an agent — Claude Code or Codex — enter
this repository and be immediately productive and safe. Measured, not assumed:

| Finding | Evidence |
|---|---|
| No agent instruction file of any kind | tree-wide `find` for `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md` → **zero hits** |
| `.claude/` is empty; `.agents/skills/` is empty | `ls -lAR .claude` → `total 0` |
| All 10 `.codex/skills/` are broken | every `SKILL.md` points at `docs/library_ref/…`; the corpus is at `docs-code-update/library_ref/…`. **26 referenced paths, 26 broken.** 23 resolve after the prefix fix; 3 name files that exist nowhere |
| Skills call a command that does not exist | 6 skills say "read chapters with `just lib-outline`"; there is no such recipe |
| No environment at all | no `.venv`; `~/.idaes/bin` is **empty** — solver/library binaries were never downloaded |
| Quality tools are stale and unpinned | `~/.local/bin/ruff` is **0.14.2** vs **0.16.7** current; `~/.local/bin/pyrefly` is **0.51.1** vs **1.3.0** current. Neither appears in `pyproject.toml` |
| direnv is installed and hooked, but unused here | direnv 2.32.1, `eval "$(direnv hook bash)"` at `~/.bashrc:142`; no `.envrc` in the repo |
| Two CI bugs from the last phase are still red | `Accel parity` fails on all four cells |

Both CI failures are environment-bootstrap problems, so they are in scope:

- **Linux** (`off` *and* `force`): `idaes/tests/test_cbrt.py` fails at **collection** with
  `TypeError: stat: path should be string… not NoneType`. `idaes/core/util/functions.py:21` calls
  `os.path.isfile(find_library("functions"))`, and with no extensions installed `find_library`
  returns `None`. A usable IDAES environment is `pip install -e .` **plus `idaes get-extensions`**.
- **Windows** (both cells): `Create environment` died with a PowerShell `ParserError`. My rewrite of
  that job dropped the job-level `shell: bash`, so a bash script was handed to PowerShell.

Wanted outcome: one command to build a working environment, one command to prove it, one file that
tells any agent what is true here, and mechanical gates that catch the classes of mistake this
project has already made.

## Decisions locked (from user)

| Decision | Choice |
|---|---|
| Formatter | **ruff format, applied to the whole repo now** (226 of 887 files change) |
| Linter | **ruff replaces pylint + flake8; strict everywhere + a suppression baseline** |
| Type checker | **pyrefly, whole repo, strict, with an error baseline** |
| `.envrc` behaviour | **Detect and report; never mutate.** No network I/O on `cd` |
| Skill doc paths | **`docs/library_ref/` → `docs-code-update/library_ref/`** |
| Tool versions | **ruff and pyrefly pinned in `pyproject.toml` at latest**, resolved from `.venv` |

## Two things to read before approving

### 1. Every number below was measured with stale tools

The findings — 3,224 ruff violations, 49,891 pyrefly errors — came from ruff **0.14.2** and pyrefly
**0.51.1**, which is what is on `PATH`. Current are ruff **0.16.7** and pyrefly **1.3.0**. Pyrefly in
particular crossed a major version, so both its diagnostics *and its config schema* may differ.

**Step one of implementation is to pin the current versions, re-measure, and only then write the
config and baselines.** Treat every count here as an order-of-magnitude guide, not a target.

This is also why the tools get pinned in `pyproject.toml` and invoked from `.venv` rather than
`$PATH`: this project has already been bitten by exactly this drift, when local black 25.9.0
disagreed with the repo-pinned 26.3.1 and produced a formatting diff CI would have rejected.

### 2. The pyrefly baseline needs calibrating, or it is not a gate

"Whole repo strict with a baseline" is operable, but not at face value. The count depends entirely on
whether pyrefly can see the dependencies, and Pyomo is hostile to inference because
`ProcessBlock`/`Component` are built by metaprogramming:

| Configuration | Errors | Files |
|---|---:|---:|
| No interpreter configured (deps invisible) | 8,049 | 721 |
| **With the project venv (deps visible)** | **49,891** | 653 |
| With venv, Pyomo-dynamism error kinds disabled for `idaes/**` | **4,074** | 410 |
| Fork-authored `idaes/accel/` only | **11** | few |

The 49,891 is dominated by `missing-attribute` (31,705), `unsupported-operation` (8,232),
`bad-index` (2,723), `not-callable` (2,587) — i.e. `model.x[1]` and `model.c = Constraint(...)`. That
is Pyomo working as designed, not defects. A 50k-entry baseline is not a gate; it is a file that
churns whenever inference improves.

**This plan implements the calibrated form**: pyrefly runs over the whole repo at full strictness,
with a sub-config disabling exactly those dynamism-driven kinds for `idaes/**` and *only* there —
fork-authored paths get everything. That leaves ~4,074 baselined findings and 11 to fix outright.
Still "whole repo, strict, baselined"; the noise floor is just set where Pyomo actually is. Say the
word and I will baseline the raw 49,891 instead.

`pyrefly suppress` (inline `# pyrefly: ignore[...]`) was considered and rejected as the baseline
mechanism — it would touch **721 of 887 files**, far more churn than the reformat. It is kept as the
*ratchet-down* tool when converting one module at a time.

---

## Phase A — Environment bootstrap

### A.1 Pin the toolchain in `pyproject.toml`

Quality tools become project dependencies, not machine state, using PEP 735 dependency groups —
uv-native, and kept out of the wheel's extras so `pip install idaes-pse[...]` and Read the Docs are
unaffected:

```toml
[dependency-groups]
quality = [
  "ruff==0.16.7",
  "pyrefly==1.3.0",
]
```

Exact pins, not floors: a formatter that drifts produces diffs, and a type checker that drifts
produces baseline churn. Dependabot proposes bumps; bumping is a deliberate commit that re-runs
`just baseline-update`.

Every recipe and CI job resolves `.venv/bin/ruff` and `.venv/bin/pyrefly`, never `$PATH`.
`scripts/doctor.py` fails when the resolved version differs from the pin.

### A.2 `.envrc` (new, tracked) — report, never mutate

direnv is already hooked in `~/.bashrc` *after* the micromamba init, so it sees and can override
conda/mamba state. The file exports and reports; it never creates, installs, or downloads.

```bash
# .envrc — entering this directory must be fast and must never touch the network.
export IDAES_PYTHON="${IDAES_PYTHON:-3.14.7}"    # matches .python-version
export UV_PROJECT_ENVIRONMENT=.venv              # matches ~/.codex/config.toml
export IDAES_ACCEL="${IDAES_ACCEL:-auto}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/rust/target}"
PATH_add "$PWD/.venv/bin"                        # pinned ruff/pyrefly/pytest beat ~/.local/bin
PATH_add "${IDAES_DATA:-$HOME/.idaes}/bin"       # solver binaries, when they exist
watch_file .python-version rust/rust-toolchain.toml pyproject.toml
[ -f .envrc.local ] && source_env .envrc.local   # personal, gitignored
./scripts/doctor.py --format=direnv              # the status block below
```

Entering the directory prints:

```
direnv: idaes-arrow (fork of IDAES/idaes-pse @ 70a8f4fe1)
  python   .venv 3.14.7                       ok
  rust     1.98.1 (rust/rust-toolchain.toml)  ok
  quality  ruff 0.16.7 / pyrefly 1.3.0        ok
  solvers  ~/.idaes/bin                       MISSING  -> just bootstrap-solvers
  accel    not installed                      IDAES_ACCEL=auto -> python path
  upstream 4 ahead, 0 behind
```

`PATH_add "$HOME/.idaes/bin"` is deliberate: `idaes/config.py:736 setup_environment()` already
mutates `PATH`/`LD_LIBRARY_PATH` at import time, so putting it on `PATH` up front means `ipopt -v`
works in a plain shell — which is what an agent will try first.

### A.3 `scripts/doctor.py` (new) — the highest-value agent affordance

One probe, three formats: `--format=direnv` (above), `--format=text`, `--format=json`
(machine-readable, for agents and CI). Each check carries a **fix command**:

| Check | Probe | Fix |
|---|---|---|
| interpreter | `.venv` exists, version matches `.python-version` | `just bootstrap` |
| deps | `idaes`, `pyomo`, `pytest` importable | `just bootstrap` |
| quality tools | `.venv/bin/{ruff,pyrefly}` exist **and match the pins** | `just bootstrap-quality` |
| solver binaries | `~/.idaes/bin` non-empty; `functions`, `cubic_roots` present | `just bootstrap-solvers` |
| rust toolchain | `rustup` resolves 1.98.1 inside `rust/` | `rustup toolchain install 1.98.1` |
| cargo tools | nextest, deny, audit, shear, machete, llvm-cov, insta, hack, msrv, mutants, geiger, udeps, maturin, typos | `just bootstrap-rust-tools` |
| accel | `idaes_accel` importable; ABI matches `idaes/accel/compat.py` | `just accel-develop` |
| upstream | ahead/behind `upstream/main`; modified-upstream-file count | `just sync-upstream` |

Exits non-zero only for things that actually block work. `just doctor` wraps it.

### A.4 `scripts/bootstrap.sh` + `just bootstrap` — one command, idempotent

`uv venv` on `.python-version` → `uv pip install -e ".[ui,grid,coolprop]" -r requirements-dev.txt` →
`uv pip install --group quality` → `idaes get-extensions --extra petsc` → `pre-commit install` →
`direnv allow` hint → `doctor`.

Split so slow pieces are separately runnable: `bootstrap-solvers` (a ~100 MB download),
`bootstrap-rust-tools` (`cargo binstall`, pinned versions), `bootstrap-quality`.

**`idaes get-extensions` is not optional**, and that is the fact this phase exists to encode. Without
it `~/.idaes/bin` is empty, `functions_lib()` returns `None`, and `test_cbrt.py` takes the whole
pytest session down at collection — precisely what broke CI.

### A.5 New justfile recipes

`bootstrap`, `bootstrap-solvers`, `bootstrap-rust-tools`, `bootstrap-quality`, `doctor`,
`lib-outline <doc>` (the recipe six skills already assume — prints a reference document's heading
outline), `fmt-py`, `lint-py`, `typecheck`, `baseline-update`, `quality`, `plan <name>`.

---

## Phase B — `AGENTS.md` and `CLAUDE.md`

**Claude Code does not read `AGENTS.md`.** It reads `CLAUDE.md`, and supports `@path` imports (4-hop
limit, resolved relative to the importing file). So:

- **`AGENTS.md`** — canonical, tool-neutral, single source of truth. Codex reads it natively.
- **`CLAUDE.md`** — a real file, not a symlink (Windows is in the CI matrix), whose first line is
  `@AGENTS.md`, followed by a short Claude-specific section.

CLAUDE.md beyond ~200 lines measurably degrades adherence, so depth lives in `.claude/rules/*.md`
with `paths:` frontmatter, which load only when matching files are touched.

### AGENTS.md outline (target ≈180 lines)

1. **What this is** — a fork of IDAES-PSE integrating Rust DataFusion/Arrow; the Python tree keeps
   upstream's layout deliberately.
2. **Start here** — `just doctor`, then `just bootstrap` if it complains. `just --list` is the
   command surface; do not invent ad hoc commands.
3. **Prime directives** — don't restructure `idaes/`; every accelerated function keeps its Python
   implementation; parity is bit-exact by default; added files are cheap, modified upstream files
   are expensive (`just divergence`).
4. **Repo map** — `idaes/` (upstream, edit narrowly), `idaes/accel/` (fork), `rust/` (all Rust),
   `docs-code-update/library_ref/` (pinned API refs → skills),
   `docs-code-update/authoritative_design/` (**off-limits**), `docs-code-update/plans/`.
5. **Where authority lives** — `32_repository_engineering.md` is the authoritative as-is description
   of pyproject/pytest/markers/CI; reference it rather than restating. `rust/Cargo.toml`'s header
   comment is authoritative for version pins. `pyproject.toml [dependency-groups]` is authoritative
   for quality-tool versions.
6. **Invariants** — one Arrow/DataFusion type universe; `panic = "unwind"`; never
   `target-cpu=native`; exactly one of `unit`/`component`/`integration`/`performance` per test; SPDX
   header on `.rs`, the 12-line IDAES block on `.py` under `idaes/`.
7. **Gotchas that have already cost us** — the highest-value section, written from real scars:
   - Porting an untyped Python function means porting its **coercion** behaviour.
     `prime_number_generator(2.9)` returns `[2,3,5]`; an `i64` signature raised `TypeError`.
   - `yaml.safe_load` silently accepts **duplicate keys** (last wins). Adding `if:` to a job that
     already had one disabled the guard invisibly. Run `actionlint`.
   - A `#` line inside a `>-` folded YAML scalar is **content**, not a comment.
   - GitHub Actions does not support **YAML anchors**.
   - On `windows-*` runners the default shell is **PowerShell**; set `shell: bash` explicitly.
   - The full suite needs `idaes get-extensions`, or `test_cbrt.py` kills collection.
   - Under `IDAES_ACCEL=force` coverage collapses — never upload it from that job.
   - Use the tool from `.venv`, never `$PATH`; version drift produces phantom diffs.
   - Always report a failure count **with its baseline**.
8. **Verification ladder** — what each command proves, and what it does not.
9. **Off-limits** — `docs-code-update/authoritative_design/` belongs to a separate workflow with its
   own brief (`_scripts/AUTHOR_BRIEF.md`), a file-ownership ledger, mechanically **banned words**
   (including `Arrow`, `DataFusion`, `just`, `recommend*`), and anchors pinned to `70a8f4fe1`. Those
   documents describe **upstream as-is** and deliberately exclude this fork's work. Read them; do not
   edit them; never cite `idaes/accel/` in them.

`docs-code-update/` is already excluded from black and typos, and will be excluded from ruff — so
AGENTS.md naming those banned words cannot trip that workflow's verifier, which scans only its own
directory.

---

## Phase C — Ruff pivot

### C.1 Format the tree

`ruff format .` committed **alone**, nothing else in the commit, so the noise is one reviewable blob
and `git log --follow` stays usable. Run with the **pinned 0.16.7**, not the stale local 0.14.2 — the
226-file figure will move. AGENTS.md records the known cost: those files now conflict on upstream
merges that touch them.

### C.2 `[tool.ruff]` in `pyproject.toml`

```toml
[tool.ruff]
target-version = "py310"   # classifiers claim 3.10+, even though we develop on 3.14
line-length = 88           # matches the outgoing black/flake8 setting
extend-exclude = ["docs-code-update", ".codex", ".agents", "rust/target"]

[tool.ruff.lint]
select = ["E","F","W","B","C4","UP","SIM","RUF","PT","PL","I","N","D","ARG","PTH"]
```

Strict everywhere; existing findings go to a baseline, not to `per-file-ignores`. The exact `select`
set is finalised after re-measuring on 0.16.7.

### C.3 Suppression baselines — `scripts/quality_baseline.py`

Ruff has no native baseline (only `--statistics`/`--diff`; confirmed). One script serves both tools:

- Consume `ruff check --output-format=json` and `pyrefly check --output-format=json`.
- Key each finding on **`(relative_path, rule_code)` → count** — deliberately *not* line numbers, so
  the baseline survives edits and reformatting.
- Fail when a new `(file, rule)` pair appears or a count increases. A count that *decreases* also
  fails, with "run `just baseline-update`" — that is the ratchet.
- Baselines tracked at `.quality/ruff-baseline.json` and `.quality/pyrefly-baseline.json`, each
  recording the tool version that produced it, so a stale baseline is self-evident.

### C.4 Removals

Delete `[tool.flake8]` and both `[tool.pylint.*]` blocks from `pyproject.toml`; delete `.pylint/`;
drop `black` from `requirements-dev.txt` and pre-commit; replace the `code-formatting` and `pylint`
jobs in `core.yml`.

**What is lost, plainly:** `.pylint/idaes_transform.py` is an astroid plugin teaching pylint about
`declare_process_block_class()`. Ruff has no plugin mechanism, so that ProcessBlock awareness goes.
In practice pylint's value here was already narrow — `core.yml` runs it with `--disable=R`, and
`.pylint/pylintrc` disables `no-member` outright, which is the check that plugin most affects. The
file stays in git history and is referenced from AGENTS.md.

---

## Phase D — pyrefly

### `pyrefly.toml` (new, repo root)

```toml
project-includes = ["idaes", "scripts", "rust/py/idaes-accel/python"]
project-excludes = ["**/docs-code-update/**", "**/rust/target/**", "**/.venv/**"]
python-version = "3.10"                  # the floor we claim, not the one we develop on
python-interpreter = ".venv/bin/python"  # WITHOUT this the errors are wrong, not merely fewer

# Upstream IDAES is Pyomo-metaprogrammed: `model.x[1]` and `model.c = Constraint(...)`
# are correct code no type checker can follow. These kinds are 45,817 of 49,891
# errors. Disabled HERE ONLY; fork-authored paths get everything.
[[sub-config]]
matches = "idaes/**"
[sub-config.errors]
missing-attribute = false
unsupported-operation = false
bad-index = false
not-callable = false
missing-module-attribute = false
```

**The schema above is written against pyrefly 0.51.1 and must be re-derived for 1.3.0** with
`pyrefly init` and `pyrefly dump-config` before anything is committed — a major version bump is
exactly where `sub-config` spelling and error-kind names change. `idaes/accel/**` is not covered by
that block, so the fork's own errors get fixed, not suppressed.

---

## Phase E — Claude Code and Codex configuration

### `.claude/settings.json` (tracked)

`permissions.allow` for the read-only surface (`just --list`, `just doctor`, `git status|log|diff`,
`cargo check|clippy|tree|metadata`, `ruff check`, `pyrefly check`, `pytest --collect-only`, `rg`,
`fd`, `ls`); `ask` for `git push`, `git commit`, `maturin publish`, `cargo publish`; `deny` for
`rm -rf`, writes under `.git/**`, and **writes under `docs-code-update/authoritative_design/**`** —
the other workflow's territory. Plus `env` for `IDAES_ACCEL`/`UV_PROJECT_ENVIRONMENT` and a
`statusLine` showing the active accel backend.

*Context:* `~/.claude/settings.json` currently sets `skipDangerousModePermissionPrompt: true` and has
no `permissions` block, so project-level rules are the only guard rails in play.

Exact key names are validated against the installed Claude Code version before committing.

### `.claude/hooks/`

| Hook | Event | Purpose |
|---|---|---|
| `session-start.sh` | `SessionStart` | run `scripts/doctor.py --format=text` — the agent starts knowing what is broken |
| `format-after-edit.sh` | `PostToolUse` on `Edit\|Write` | `.venv/bin/ruff format` the touched `.py`, `cargo fmt` the touched `.rs`; ends formatting-only CI failures |
| `guard-protected-paths.sh` | `PreToolUse` on `Edit\|Write` | exit 2 with a reason when the target is under `authoritative_design/`, `.git/`, or `rust/target/` |

### `.claude/rules/` (path-scoped, lazy)

`rust.md` (`paths: rust/**`) — type universe, `panic = "unwind"`, GIL discipline, thin-cdylib rule.
`python-accel.md` (`paths: idaes/accel/**`) — decorator contract, never wrap a method, marker rule.
`upstream.md` (`paths: idaes/**`) — edit narrowly, merge cost, header rule.
`ci.md` (`paths: .github/**`) — the YAML gotchas, run `actionlint` before pushing.

### Skills — fix, then unify

1. **Fix the 26 broken paths**: `docs/library_ref/` → `docs-code-update/library_ref/` across all
   `SKILL.md`/`REFERENCE.md` files.
2. **Drop the 3 dangling references** naming files that exist nowhere: `datafusion_rust_UDFs.md`,
   `deltalake.md`, `deltalake_rust_1.0.0_9f922319_advanced_reference_2026-08-20.md` (superseded by
   the `43a0cf10` document that *is* present).
3. Add the `just lib-outline` recipe the skills already assume.
4. Delete the two tombstone skills (`attrs-cattrs-ref`, `typer-rich-ref`) — they route nowhere and
   cost context in every listing.
5. **Make `.claude/skills` a symlink to `../.codex/skills`** so both runtimes read one copy; fall
   back to real directories plus a `just skills-sync` drift check if the loader objects.
6. `scripts/check_skill_refs.py` + a CI job, so a reference can never silently rot again.

### New repo skills and subagents

Skills: `verify` (run the right gate for what changed), `new-kernel` (scaffold an accelerated
function end to end: rlib fn + tests, `#[pyfunction]`, registry entry, parity cases),
`sync-upstream` (merge, re-run parity, report divergence).

Subagents (`.claude/agents/`): `parity-auditor` (adversarially hunt Python/Rust divergence, above all
coercion and input mutation — the class that already bit us), `ci-doctor` (read a failing run,
isolate the step, propose a minimal fix).

### Codex side

`~/.codex/AGENTS.md` is empty and `~/.codex/config.toml` runs `approval_policy = "never"` with
`sandbox_mode = "danger-full-access"`, so this repo's `AGENTS.md` is Codex's *only* guidance. Add a
project `.codex/config.toml` recording `UV_PROJECT_ENVIRONMENT=.venv` and the trusted-tool surface,
and state in AGENTS.md that Codex runs unsandboxed here.

---

## Phase F — Mechanical gates and repo hygiene

- **Fix the two live CI bugs**: restore `shell: bash` to the parity job, and add
  `idaes get-extensions --extra petsc` before the suite (or scope the suite to markers needing no
  compiled binaries).
- **`.github/workflows/quality.yml`** (new): `ruff format --check`, `ruff check` vs baseline,
  `pyrefly check` vs baseline, **`actionlint`**, `taplo fmt --check`, `yamllint`, `shellcheck`, and
  `check_skill_refs.py`. `actionlint` alone would have caught the duplicate-`if` bug.
- **`.pre-commit-config.yaml`**: ruff + ruff-format replace black (pinned to the same versions as
  `[dependency-groups]`); add actionlint, taplo, shellcheck; keep the three local Rust hooks.
- **`.editorconfig`** — one indent/EOL/charset truth for every editor and agent.
- **`.github/dependabot.yml`** — cargo, github-actions, and the pip dependency group, so ruff and
  pyrefly bumps arrive as reviewable PRs instead of silent drift.
- **`docs-code-update/plans/`** is empty; move the Rust-integration plan there as
  `01_rust_arrow_integration.md` and this one as `02_agent_environment.md`. Plans in
  `~/.claude/plans/` are invisible to Codex and to future sessions; in-repo they are readable by both
  and reviewable in a PR. `just plan <name>` creates a stub.
- `.gitignore`: `.venv/`, `.envrc.local`, `.claude/settings.local.json`, `.ruff_cache/`,
  `.pyrefly_cache/`.

---

## Order of work

1. Phase F's two CI fixes — get the board green before changing anything else.
2. A.1 pin ruff/pyrefly, A.4 bootstrap, A.3 doctor, **re-measure on the current versions**.
3. A.2 `.envrc` (it calls doctor, so doctor comes first).
4. C.1 the reformat commit, alone.
5. C.2–C.4 ruff config, baseline script, pylint/black removal.
6. Phase D pyrefly — schema re-derived for 1.3.0 first.
7. Phase B AGENTS.md/CLAUDE.md, written last so it documents what is actually true.
8. Phase E `.claude/` + skill fixes; Phase F remaining gates.

---

## Verification

```bash
# Bootstrap from nothing, the way a new agent would
rm -rf .venv && just bootstrap && just doctor --format=json | jq '.checks[] | select(.ok==false)'
direnv allow && cd .. && cd idaes-arrow     # status block prints; nothing is downloaded

# The pins are real
.venv/bin/ruff --version                    # 0.16.7, not ~/.local/bin's 0.14.2
.venv/bin/pyrefly --version                 # 1.3.0, not 0.51.1
just doctor --format=json | jq '.checks[] | select(.name=="quality")'

# Quality gates: green, or equal to baseline
just fmt-py && git diff --exit-code         # reformat is idempotent
just lint-py                                # ruff vs .quality/ruff-baseline.json
just typecheck                              # pyrefly vs .quality/pyrefly-baseline.json
just quality                                # + actionlint, taplo, yamllint, shellcheck, skill refs
pre-commit run --all-files

# The real suite runs at all now
just py-test-noaccel && just py-test-accel  # needs get-extensions; previously died at collection
just ci-fast                                # Rust side unaffected

# Agent-config correctness
python scripts/check_skill_refs.py          # 26/26 resolve
just lib-outline datafusion_schemas_rust    # the recipe six skills assume
actionlint .github/workflows/*.yml          # zero findings in our files
claude -p "run just doctor and summarize"   # Claude reads CLAUDE.md -> @AGENTS.md
codex exec "what may I not edit in this repo?"   # must name authoritative_design

gh run list --repo paul-heyse/idaes-arrow --limit 6
```

## Open items

1. **The pyrefly calibration** — proceeding with the ~4,074 baseline unless told otherwise.
2. All counts re-measured on ruff 0.16.7 / pyrefly 1.3.0 before configs and baselines are written;
   the pyrefly config schema is re-derived for 1.3.0.
3. `.claude/skills` as a symlink to `.codex/skills` is the clean unification; fallback is duplication
   plus a drift check. Confirmed against the installed Claude Code version during implementation.
4. `idaes get-extensions` downloads ~100 MB on first bootstrap and in the parity CI job. If that is
   unwelcome in CI, the alternative is scoping the parity suite to markers needing no compiled
   binaries, at some loss of coverage.
