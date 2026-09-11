# Rust / DataFusion / Arrow integration

Status: **Phases 0-4 implemented.** Phase 5 (the first real vertical slice) open.

This is a decision record. Where a decision is now expressed by a real file, the
file is authoritative and is named here rather than duplicated — `rust/Cargo.toml`
for pins, `rust/README.md` for layout, `pyrefly.toml` and `pyproject.toml` for the
Python gates.

## Context

`idaes-pse` at `70a8f4fe1` (v2.13.0rc0) is 100% pure Python: 874 files, ~428k LOC,
`setuptools.build_meta` + `setuptools_scm`, one `py3-none-any` wheel. Verified: no
`Cargo.toml`, `.rs`, `.pyx`, `.c`, `setuptools.Extension` or `build_ext` anywhere.
The only native coupling is runtime `ctypes.cdll.LoadLibrary` of libraries built
out-of-tree in `IDAES/idaes-ext` and downloaded by `idaes get-extensions`.

Goal: progressively integrate Rust Arrow/DataFusion capability, **dispersed**
across the codebase, with the Rust itself **consolidated**, and the Python layout
left intact so upstream merges stay cheap.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Fork mechanism | Detached repo + `upstream` remote | Actions work, visibility is free, no accidental PRs upstream |
| Packaging | Two distributions: `idaes-pse` (unchanged, pure Python) + `idaes-accel` (maturin, abi3) | Upstream's `pyproject.toml` and `publish.yml` stay untouched; `pip install idaes-pse` still needs no Rust toolchain |
| Migration style | Dual-path: Rust impl + retained Python impl + parity tests | Incremental, revertible, and parity tests are strong oracles |
| Rust channel | Pinned stable 1.98.1; `+nightly` only for Miri/udeps | Nightly for one scheduled job must not become everyone's compiler |
| MSRV | `rust-version = "1.98.1"`, equal to the toolchain pin | A declared floor below what CI exercises is an unverified promise |
| Arrow version | `=59.3.0`, not the reference docs' 59.2.0 | DF55 declares `^59.2.0`; 59.3.0 is a patch release inside the same minor |
| `object_store` | `=0.13.2`, **not** crates.io's newer 0.14.x | DF55 requires `^0.13.2`; 0.14 would put two majors in the graph |
| Boundary types | NumPy for dense numeric kernels; Arrow where the Python side is genuinely tabular | DataFusion buys nothing for elementwise kernels and roughly doubles the wheel |

## What is built

- **Phase 0** — fork created; upstream automation neutralised (publish/cleanup
  guarded on `github.repository`, crons limited to upstream); reference corpus and
  skills vendored. Actions were disabled while pushing 106 historical tags, because
  a tag-triggered run executes the workflow from *that tag's* commit.
- **Phase 1** — `rust/` workspace, toolchain pin, lints, profiles, `deny.toml`,
  nextest profiles, the `justfile` command contract, SPDX header checker.
- **Phase 2** — the PyO3 boundary crate, abi3-py310 wheels. `pyo3-arrow`'s default
  `buffer_protocol` feature is incompatible with abi3 below 3.11, hence
  `default-features = false`.
- **Phase 3** — `idaes/accel/`: loader, ABI contract, registry, parity harness.
- **Phase 4** — four workflows: `rust-ci`, `accel-wheels`, `accel-parity`,
  `rust-scheduled`.

## Phase 5 — the open work

**`idaes/core/util/parameter_sweep.py` as entry point; the Rust lands in
`idaes/core/surrogate/pysmo/sampling.py`.**

Chosen because it is the only candidate whose full test surface runs on all ten CI
cells with no optional dependencies. Rejected, with reasons:

- `pricetaker/clustering.py` — `sklearn` is declared nowhere; its tests
  `importorskip` and never run in CI. The hot function is `KMeans` with a public
  `seed=42` feeding a downstream optimisation; not bit-reproducible.
- `petsc.py::PetscTrajectory` — every test is `skipif(not petsc_available())` with
  no checked-in fixture. Zero CI signal. Keep as target #2: `_read` is an
  `n_vars x n_timesteps` Python scalar-store double loop, the largest single win.
- `tables.py` — the DataFrame is `object`-dtype by construction (pint `Unit`
  objects, the literal string `"-"`, `(float, str)` tuples). Not Arrow-shaped.
- `model_serializer.py` — 100% Pyomo-object traversal; the only Rust-able tail is
  gzip+json of a nested dict, which would be slower across the boundary.

Steps, each independently shippable:

0. `prime_number_generator` — **done**, and it proved the whole chain. It also
   produced the project's defining bug: the function is untyped and its own suite
   calls it with `2.9`, which an `i64` signature rejected.
1. `data_sequencing` — deterministic, bit-exact achievable. Mirror the accumulation
   order and exponent form exactly.
2. `FeatureScaling.data_scaling_minmax` — the NumPy-vs-Arrow decision point. Mirror
   the `inf`/`nan` pattern for constant columns; do not "fix" it.
3. `points_selection` / `nearest_neighbour` — the real algorithmic win. Today it
   copies the whole N x D dataset per query then `argsort`s. Note `np.argsort`
   defaults to unstable quicksort, so tie-breaking is currently unspecified;
   "first minimum wins" is a documented tightening.
4. `parameter_sweep.py` itself — no Rust. `to_dict`/`from_dict` must stay Python:
   `DataFrame.to_dict(orient="tight")` is an on-disk format contract users' JSON
   files depend on.

## Roadmap after Phase 5

`petsc.py::PetscTrajectory` -> `tables.py` -> `pricetaker/` LMP series ->
`model_serializer.py` (high payoff, high compat risk) -> pysmo samplers ->
the 6.8 MB prescient CSVs -> costing lookup tables. `idaes/core/io/` is an empty
package: a free namespace with no upstream collision.

Diagnostics (`svd_toolbox`, `degeneracy_hunter`, `ill_conditioning`) are sparse
linear algebra, not columnar — a Rust numeric kernel target, not DataFusion.
`idaes/core/dmf/` is a deprecation stub; do not plan around it.

## Risks that shaped the design

- **Pyomo objects cannot cross the boundary.** They are graph objects with solver
  state. Target only data that is already tabular or already being serialized.
- **Determinism.** Reduction order must not depend on thread count; never
  `target-cpu=native` (FMA contraction changes results between dev and CI);
  unseeded global RNG paths cannot be parity-tested and stay in Python.
- **GIL.** Zero Python callbacks inside `py.detach`. This forbids parallelising
  `SequentialSweepRunner` in Rust.
- **Dual-path burden.** The realistic accelerable surface is ~20-40 functions, not
  874 files; most CPU time is in Pyomo's expression walkers and the solver
  subprocess. Budget against that number.

## Verification

See `just --list`. The gates that matter: `just ci-fast`, `just one-type-universe`,
`just accel-wheel-verify`, and `just py-test-noaccel` / `just py-test-accel` — the
last pair is the only thing that catches divergence at real call sites, which is
how the `2.9` bug was found.
