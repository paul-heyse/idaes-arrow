# Operational API for the idaes-arrow fork.
#
# `just --list` is the first thing to run. Prefer these recipes over ad hoc
# commands: they own the feature selection, profiles, report paths and env vars,
# so they can change without anything downstream needing to re-learn them.
#
# Recipes are grouped by execution-cost tier:
#   discovery   seconds, every task
#   local       seconds to a minute, every edit
#   pr          minutes, before review
#   scheduled   minutes to hours, nightly/weekly/risk-triggered
#   mutating    CHANGES SOURCE OR ENVIRONMENT -- never a dependency of a gate
#
# Note `cargo check` is not a cacheable sccache workload (check units omit the
# link step); `cargo build` is. Recipes that want cache reuse set RUSTC_WRAPPER
# explicitly rather than committing it to rust/.cargo/config.toml, which would
# break contributors who do not have sccache installed.

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list --unsorted

# ---------------------------------------------------------------- discovery --

[group('discovery')]
[doc('Record the exact toolchain + tool inventory that produced a result')]
[working-directory('rust')]
versions:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p target
    {
      date -u
      uname -a || true
      rustc -vV
      cargo -V
      rustup show active-toolchain
      rustup component list --installed
      cargo install --list
      sccache --show-stats 2>/dev/null || true
    } > target/tooling-inventory.txt
    echo "wrote rust/target/tooling-inventory.txt"

[group('discovery')]
[working-directory('rust')]
metadata:
    cargo metadata --format-version 1 --no-deps

# -------------------------------------------------------------- local loop --

[group('local')]
[working-directory('rust')]
check:
    cargo check --workspace --all-targets

[group('local')]
[working-directory('rust')]
clippy:
    cargo clippy --workspace --all-targets -- -D warnings

[group('local')]
[working-directory('rust')]
fmt-check:
    cargo fmt --all -- --check

[group('local')]
[working-directory('rust')]
test:
    cargo nextest run --workspace

[group('local')]
[working-directory('rust')]
test-package package:
    cargo nextest run -p {{ package }}

# nextest does NOT run doctests. Every gate must pair the two.
[group('local')]
[working-directory('rust')]
doctest:
    cargo test --workspace --doc

[group('local')]
[working-directory('rust')]
deps-fast:
    cargo machete
    cargo shear

[group('local')]
[doc('Check the SPDX header on Rust sources (addheader covers only .py under idaes/)')]
headers-rust:
    python3 scripts/check_rust_headers.py

[group('local')]
[doc('Fast gate: run before switching tasks')]
ci-fast: fmt-check check clippy test doctest deps-fast typos headers-rust

# --------------------------------------------------------------------- PR --

[group('pr')]
[working-directory('rust')]
coverage:
    mkdir -p target/coverage
    cargo llvm-cov nextest --workspace --all-features \
      --lcov --output-path target/coverage/lcov.info
    @echo "wrote rust/target/coverage/lcov.info"

[group('pr')]
[working-directory('rust')]
policy:
    cargo deny check
    cargo audit

[group('pr')]
[doc('Fail if any Arrow/DataFusion/Parquet/object_store major is duplicated')]
[working-directory('rust')]
one-type-universe:
    #!/usr/bin/env bash
    set -euo pipefail
    dupes="$(cargo tree -d 2>/dev/null || true)"
    if grep -qE '^(arrow|parquet|object_store|datafusion)' <<<"$dupes"; then
      echo "FAIL: duplicate major of a type-universe crate:" >&2
      echo "$dupes" >&2
      exit 1
    fi
    echo "one type universe: ok"

[group('pr')]
typos:
    typos --config .github/workflows/typos.toml

[group('pr')]
[working-directory('rust')]
snapshots-pending:
    cargo insta pending-snapshots

[group('pr')]
ci-pr: ci-fast one-type-universe policy coverage

# -------------------------------------------------------------- scheduled --

[group('scheduled')]
[working-directory('rust')]
features-each:
    cargo hack check --workspace --each-feature

[group('scheduled')]
[working-directory('rust')]
features-powerset:
    cargo hack check --workspace --feature-powerset

[group('scheduled')]
[working-directory('rust')]
msrv:
    cargo msrv verify

[group('scheduled')]
[doc('UB / aliasing / data-race interpretation. Records nothing about inputs not explored.')]
[working-directory('rust')]
miri package:
    cargo +nightly miri test -p {{ package }}

[group('scheduled')]
[working-directory('rust')]
miri-seeds package seeds="32":
    MIRIFLAGS="-Zmiri-many-seeds=0..{{ seeds }}" cargo +nightly miri test -p {{ package }}

[group('scheduled')]
[working-directory('rust')]
udeps:
    cargo +nightly udeps --workspace --all-targets

[group('scheduled')]
[working-directory('rust')]
mutants-file path:
    cargo mutants -f {{ path }}

[group('scheduled')]
[working-directory('rust')]
unsafe-surface:
    cargo geiger

[group('scheduled')]
[working-directory('rust')]
cache-stats:
    sccache --show-stats

# ------------------------------------------------------------------ accel --

[group('accel')]
[doc('Build + install into the ACTIVE python env. Not wheel validation.')]
accel-develop:
    maturin develop --release -m rust/py/idaes-accel/Cargo.toml

[group('accel')]
accel-wheel:
    maturin build --release -m rust/py/idaes-accel/Cargo.toml
    @ls -la rust/target/wheels/

[group('accel')]
[doc('Build a wheel, install it into a THROWAWAY venv, import it. The real gate.')]
accel-wheel-verify python="3.12":
    #!/usr/bin/env bash
    set -euo pipefail
    maturin build --release -m rust/py/idaes-accel/Cargo.toml
    whl="$(ls -t rust/target/wheels/idaes_accel-*.whl | head -1)"
    echo "verifying $whl"
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    uv venv "$tmp/venv" --python "{{ python }}" -q
    uv pip install --python "$tmp/venv/bin/python" -q "$whl"
    "$tmp/venv/bin/python" -c "
    import idaes_accel
    print('ok:', idaes_accel.__version__, 'abi', idaes_accel.__abi_version__)
    "

# ------------------------------------------------------------------ python --

[group('python')]
py-format-check:
    black --check --diff .

[group('python')]
py-lint:
    pylint --rcfile=./.pylint/pylintrc idaes/

[group('python')]
py-test marks="not integration":
    pytest --pyargs idaes -m "{{ marks }}"

[group('python')]
[doc('Whole suite on the pure-Python path')]
py-test-noaccel:
    IDAES_ACCEL=off pytest --pyargs idaes -m "not integration"

[group('python')]
[doc('Whole suite on the Rust path; fails loudly if acceleration is unavailable')]
py-test-accel:
    IDAES_ACCEL=force pytest --pyargs idaes -m "not integration"

# ---------------------------------------------------------------- upstream --

[group('upstream')]
[doc('Merge upstream IDAES/idaes-pse into this fork')]
sync-upstream:
    git fetch upstream --tags
    git merge upstream/main

[group('upstream')]
[doc('How far this fork has drifted. Added files are cheap; modified files are not.')]
divergence:
    @git diff --stat upstream-main..main | tail -1
    @echo "--- upstream files MODIFIED (recurring merge cost) ---"
    @git diff --name-status upstream-main..main | grep '^M' || echo "(none)"

# ---------------------------------------------------------------- mutating --
# These change source or environment. Never make them a dependency of a gate.

[group('mutating')]
[confirm('Rewrite source formatting in place?')]
[working-directory('rust')]
fmt:
    cargo fmt --all

[group('mutating')]
[confirm('Remove dependencies flagged by cargo-shear?')]
[working-directory('rust')]
deps-fix:
    cargo shear --fix

[group('mutating')]
[confirm('Accept ALL pending snapshots without review?')]
[working-directory('rust')]
snapshots-accept:
    cargo insta accept

[group('mutating')]
[confirm('Write spelling corrections into source?')]
typos-write:
    typos --config .github/workflows/typos.toml -w

[group('mutating')]
[doc('Apply the IDAES license header to python files under idaes/')]
py-headers:
    addheader -c addheader.yml
