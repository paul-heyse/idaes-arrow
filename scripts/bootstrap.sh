#!/usr/bin/env bash
# Create a working development environment for this repository, idempotently.
#
# Run it again any time; every step is safe to repeat. Prefer `just bootstrap`,
# which is the documented entry point.
#
# Stages are separable because one of them is slow and network-bound:
#   --venv-only      interpreter + python dependencies
#   --quality-only   the pinned ruff/pyrefly from [dependency-groups]
#   --solvers-only   the ~100 MB IDAES binary download
#   --rust-only      pinned cargo development tools
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv"
PY="${VENV}/bin/python"
BIN="${VENV}/bin"
[[ "${OS:-}" == Windows_NT ]] && { PY="${VENV}/Scripts/python.exe"; BIN="${VENV}/Scripts"; }

# Versions pinned here, not on the machine. Keep in sync with the reference
# doc's tool inventory; `just doctor` reports drift.
CARGO_TOOLS=(
  "cargo-nextest@0.9.143" "cargo-deny@0.20.2"   "cargo-audit@0.22.2"
  "cargo-shear@1.13.4"    "cargo-machete@0.9.2" "cargo-llvm-cov@0.9.0"
  "cargo-insta@1.48.0"    "cargo-hack@0.6.45"   "cargo-msrv@0.19.3"
  "cargo-mutants@27.1.0"  "cargo-geiger@0.13.0" "cargo-udeps@0.1.61"
  "maturin@1.15.0"        "typos-cli@1.50.0"
)

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: $1 is required but not installed" >&2
    exit 1
  }
}

stage_venv() {
  need uv
  local want
  want="$(cat .python-version)"

  # Reuse an existing venv when the interpreter already matches, so
  # `just bootstrap` is cheap to re-run. Recreate when it does not: a venv on
  # the wrong Python is worse than none, because everything appears to work
  # until an abi3 wheel or a version-gated dependency fails obscurely.
  if [[ -x "$PY" ]] && [[ "$("$PY" -c 'import platform;print(platform.python_version())' 2>/dev/null)" == "$want" ]]; then
    say "Reusing .venv (already on $want)"
  else
    if [[ -e "$VENV" ]]; then
      say "Recreating .venv (wanted $want)"
      uv venv "$VENV" --python "$want" --clear
    else
      say "Creating .venv on $want"
      uv venv "$VENV" --python "$want"
    fi
  fi

  say "Installing idaes-pse (editable) and development dependencies"
  # --no-build-isolation is deliberately NOT used: setuptools_scm needs the
  # build environment to resolve the version from git tags.
  uv pip install --python "$PY" -e ".[ui,grid,coolprop]"
  uv pip install --python "$PY" -r requirements-dev.txt
}

stage_quality() {
  need uv
  say "Installing pinned tooling from [dependency-groups] (quality + accel)"
  uv pip install --python "$PY" --group dev
}

stage_solvers() {
  # NOT optional. Without these, idaes/core/util/functions.py evaluates
  # os.path.isfile(None) and pytest aborts during collection -- every test, not
  # just the ones needing a solver.
  local bindir
  bindir="$("$BIN/idaes" bin-directory 2>/dev/null || echo "${HOME}/.idaes/bin")"

  # Skip the ~100 MB download when the libraries are already there, so
  # `just bootstrap` stays cheap to re-run. Use --force to refresh.
  if [[ "${FORCE_SOLVERS:-0}" != "1" ]] \
     && [[ -f "${bindir}/functions.so" || -f "${bindir}/functions.dll" ]] \
     && [[ -f "${bindir}/cubic_roots.so" || -f "${bindir}/cubic_roots.dll" ]]; then
    say "IDAES solvers already present in ${bindir} (FORCE_SOLVERS=1 to refresh)"
    return 0
  fi

  say "Downloading IDAES solvers and compiled libraries (~100 MB)"
  if [[ "$(uname -s)" == "Linux" ]] && command -v apt-get >/dev/null 2>&1; then
    echo "note: these binaries link against libgfortran5 libgomp1 liblapack3 libblas3"
  fi
  "$BIN/idaes" get-extensions --extra petsc
}

stage_rust() {
  need cargo
  if ! command -v cargo-binstall >/dev/null 2>&1; then
    say "Installing cargo-binstall (prebuilt binaries beat compiling 14 tools)"
    cargo install cargo-binstall --locked
  fi
  say "Installing pinned cargo development tools"
  cargo binstall --no-confirm "${CARGO_TOOLS[@]}"
}

stage_repo_linters() {
  # Linters for the repository's own configuration, not for its source. These
  # are plain binaries with no Python or Cargo home, so they are fetched
  # directly and pinned by tag.
  local bindir="${HOME}/.local/bin"
  mkdir -p "$bindir"

  if ! command -v actionlint >/dev/null 2>&1; then
    say "Installing actionlint"
    # Catches duplicate YAML keys, bad shell expressions and unknown runner
    # labels in workflows. Each has already broken CI in this repo.
    curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash \
      | bash -s -- latest "$bindir"
  fi

  if ! command -v taplo >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
    say "Installing taplo"
    cargo binstall --no-confirm taplo-cli
  fi
}

stage_hooks() {
  if command -v pre-commit >/dev/null 2>&1; then
    say "Installing git hooks"
    pre-commit install
  fi
}

main() {
  case "${1:-all}" in
    --venv-only)    stage_venv ;;
    --quality-only) stage_quality ;;
    --solvers-only) stage_solvers ;;
    --rust-only)    stage_rust ;;
    --linters-only) stage_repo_linters ;;
    all)
      stage_venv
      stage_quality
      stage_solvers
      stage_rust
      stage_repo_linters
      stage_hooks
      ;;
    *) echo "usage: $0 [--venv-only|--quality-only|--solvers-only|--rust-only|--linters-only]" >&2
       exit 2 ;;
  esac

  if command -v direnv >/dev/null 2>&1 && [[ -f .envrc ]]; then
    direnv status 2>/dev/null | grep -q "Found RC allowed true" \
      || echo -e "\nnote: run 'direnv allow' to activate the environment on cd"
  fi

  say "Status"
  "${PY}" scripts/doctor.py --format=text || true
}

main "$@"
