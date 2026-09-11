#!/usr/bin/env python3
"""Report whether this working copy is ready to do work, and how to fix it.

Deliberately dependency-free and standard-library only: it has to run *before*
the virtual environment exists, which is exactly when it is most needed.

Three output formats:

``--format=direnv``
    A compact status block. ``.envrc`` calls this on every directory entry, so
    it must be fast and must never touch the network.
``--format=text``
    The same information with fix commands spelled out. Used by the Claude Code
    SessionStart hook.
``--format=json``
    Machine-readable, for agents and CI::

        just doctor --format=json | jq '.checks[] | select(.ok==false)'

Exit status is 1 only when something *blocks work*. A missing optional
accelerator is reported, not fatal.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
UPSTREAM = "IDAES/idaes-pse"
PINNED_COMMIT = "70a8f4fe1"

# Binaries that must exist in the IDAES data directory. `functions` is the one
# that matters most: idaes/core/util/functions.py does
# os.path.isfile(find_library("functions")), which raises TypeError on None and
# kills the whole pytest session at collection.
REQUIRED_LIBS = ("functions", "cubic_roots", "general_helmholtz_external")

CARGO_TOOLS = (
    "cargo-nextest",
    "cargo-deny",
    "cargo-audit",
    "cargo-shear",
    "cargo-machete",
    "cargo-llvm-cov",
    "cargo-insta",
    "cargo-hack",
    "cargo-msrv",
    "cargo-mutants",
    "cargo-geiger",
    "cargo-udeps",
    "maturin",
    "typos-cli",
)


@dataclass
class Check:
    """One probe, its verdict, and the command that fixes it."""

    name: str
    ok: bool
    detail: str
    fix: str = ""
    blocking: bool = True
    extra: dict = field(default_factory=dict)


def run(*args: str, cwd: Path | None = None, timeout: int = 30) -> tuple[int, str]:
    """Run a command, returning (returncode, stripped stdout+stderr)."""
    try:
        proc = subprocess.run(
            args,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def venv_python() -> Path:
    """Path to the project interpreter, whether or not it exists yet."""
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def venv_bin(name: str) -> Path:
    directory = "Scripts" if platform.system() == "Windows" else "bin"
    suffix = ".exe" if platform.system() == "Windows" else ""
    return VENV / directory / f"{name}{suffix}"


def pinned_quality_versions() -> dict[str, str]:
    """Read the exact ruff/pyrefly pins out of pyproject.toml.

    pyproject is the single source of truth; this script never carries its own
    copy of the version numbers.
    """
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    for spec in data.get("dependency-groups", {}).get("quality", []):
        if isinstance(spec, str) and "==" in spec:
            name, _, version = spec.partition("==")
            pins[name.strip()] = version.strip()
    return pins


def idaes_bin_dir() -> Path:
    """Mirror idaes/config.py::get_data_directory without importing idaes."""
    if env := os.environ.get("IDAES_DATA"):
        return Path(env) / "bin"
    if platform.system() == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "idaes" / "bin"
    return Path.home() / ".idaes" / "bin"


# --------------------------------------------------------------------- checks


def check_interpreter() -> Check:
    wanted = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    python = venv_python()
    if not python.exists():
        return Check(
            "python", False, f".venv missing (want {wanted})", "just bootstrap"
        )
    code, out = run(str(python), "--version")
    if code != 0:
        return Check("python", False, f".venv broken: {out}", "just bootstrap")
    actual = out.split()[-1]
    ok = actual == wanted
    return Check(
        "python",
        ok,
        f".venv {actual}" + ("" if ok else f" (.python-version wants {wanted})"),
        "" if ok else "rm -rf .venv && just bootstrap",
        extra={"wanted": wanted, "actual": actual},
    )


def check_deps() -> Check:
    python = venv_python()
    if not python.exists():
        return Check("deps", False, "no .venv", "just bootstrap")
    code, out = run(
        str(python),
        "-c",
        "import idaes, pyomo, pytest; print(idaes.__version__)",
        timeout=120,
    )
    if code != 0:
        missing = out.strip().splitlines()[-1] if out else "import failed"
        return Check("deps", False, missing, "just bootstrap")
    return Check("deps", True, f"idaes {out.strip()}")


def check_quality_tools() -> Check:
    pins = pinned_quality_versions()
    if not pins:
        return Check("quality", False, "no [dependency-groups] quality pins", "")
    problems, found = [], []
    for tool, wanted in pins.items():
        exe = venv_bin(tool)
        if not exe.exists():
            problems.append(f"{tool} not in .venv")
            continue
        code, out = run(str(exe), "--version")
        actual = out.split()[1] if code == 0 and len(out.split()) > 1 else "?"
        found.append(f"{tool} {actual}")
        if actual != wanted:
            problems.append(f"{tool} {actual} != pinned {wanted}")
    if problems:
        return Check(
            "quality",
            False,
            "; ".join(problems),
            "just bootstrap-quality",
            extra={"pins": pins},
        )
    return Check("quality", True, " / ".join(found), extra={"pins": pins})


def check_solvers() -> Check:
    """The check this whole script was written for.

    An empty bin directory is not a degraded state -- it makes the test suite
    abort during collection.
    """
    bindir = idaes_bin_dir()
    if not bindir.is_dir() or not any(bindir.iterdir()):
        return Check(
            "solvers",
            False,
            f"{bindir} empty -- pytest will abort at collection",
            "just bootstrap-solvers",
        )
    names = {p.stem for p in bindir.iterdir()}
    missing = [lib for lib in REQUIRED_LIBS if lib not in names]
    if missing:
        return Check(
            "solvers",
            False,
            f"{bindir} missing {', '.join(missing)}",
            "just bootstrap-solvers",
        )
    return Check("solvers", True, f"{bindir} ({len(list(bindir.iterdir()))} files)")


def check_rust() -> Check:
    rust_dir = ROOT / "rust"
    wanted = ""
    toolchain = rust_dir / "rust-toolchain.toml"
    if toolchain.exists():
        data = tomllib.loads(toolchain.read_text(encoding="utf-8"))
        wanted = data.get("toolchain", {}).get("channel", "")
    if shutil.which("rustup") is None:
        return Check("rust", False, "rustup not installed", "see rustup.rs")
    # Resolved from inside rust/, so rust-toolchain.toml applies.
    code, out = run("rustc", "--version", cwd=rust_dir)
    if code != 0:
        return Check(
            "rust",
            False,
            out.splitlines()[0] if out else "rustc failed",
            f"rustup toolchain install {wanted}",
        )
    actual = out.split()[1] if len(out.split()) > 1 else "?"
    ok = actual == wanted or not wanted
    return Check(
        "rust",
        ok,
        f"{actual}" + ("" if ok else f" (rust-toolchain.toml wants {wanted})"),
        "" if ok else f"rustup toolchain install {wanted}",
    )


def check_cargo_tools() -> Check:
    code, out = run("cargo", "install", "--list", timeout=60)
    if code != 0:
        return Check(
            "cargo-tools", False, "cargo unavailable", "see rustup.rs", blocking=False
        )
    installed = {
        line.split()[0] for line in out.splitlines() if line and not line[0].isspace()
    }
    missing = [t for t in CARGO_TOOLS if t not in installed]
    if missing:
        return Check(
            "cargo-tools",
            False,
            f"missing: {', '.join(missing)}",
            "just bootstrap-rust-tools",
            blocking=False,
        )
    return Check("cargo-tools", True, f"{len(CARGO_TOOLS)} present")


def check_accel() -> Check:
    """Never blocking: running without the extension is a supported state."""
    python = venv_python()
    mode = os.environ.get("IDAES_ACCEL", "auto")
    if not python.exists():
        return Check("accel", False, "no .venv", "just bootstrap", blocking=False)
    code, out = run(
        str(python),
        "-c",
        "import idaes_accel as m; print(m.__version__, m.__abi_version__)",
        timeout=120,
    )
    if code != 0:
        return Check(
            "accel",
            False,
            f"not installed (IDAES_ACCEL={mode} -> python path)",
            "just accel-develop",
            blocking=False,
        )
    version, _, abi = out.strip().partition(" ")
    return Check("accel", True, f"{version} abi {abi} (IDAES_ACCEL={mode})")


def check_upstream() -> Check:
    code, _ = run("git", "remote", "get-url", "upstream")
    if code != 0:
        return Check(
            "upstream",
            False,
            "no 'upstream' remote",
            f"git remote add upstream https://github.com/{UPSTREAM}.git",
            blocking=False,
        )
    code, out = run(
        "git", "rev-list", "--left-right", "--count", "upstream/main...HEAD"
    )
    if code != 0:
        return Check(
            "upstream", True, "not fetched yet", "just sync-upstream", blocking=False
        )
    behind, _, ahead = out.strip().partition("\t")
    code, modified = run(
        "git", "diff", "--name-only", "--diff-filter=M", "upstream-main...HEAD"
    )
    n_mod = len([x for x in modified.splitlines() if x]) if code == 0 else -1
    return Check(
        "upstream",
        True,
        f"{ahead} ahead, {behind} behind"
        + (f"; {n_mod} upstream files modified" if n_mod >= 0 else ""),
        blocking=False,
        extra={"ahead": ahead, "behind": behind, "modified_upstream": n_mod},
    )


CHECKS = (
    check_interpreter,
    check_deps,
    check_quality_tools,
    check_solvers,
    check_rust,
    check_cargo_tools,
    check_accel,
    check_upstream,
)


# --------------------------------------------------------------------- output


def emit_direnv(checks: list[Check]) -> None:
    print(f"direnv: idaes-arrow (fork of {UPSTREAM} @ {PINNED_COMMIT})")
    for c in checks:
        status = "ok" if c.ok else ("MISSING" if c.blocking else "--")
        print(f"  {c.name:<11} {c.detail[:44]:<46} {status}")
        if not c.ok and c.fix:
            print(f"  {'':<11} -> {c.fix}")


def emit_text(checks: list[Check]) -> None:
    for c in checks:
        mark = "PASS" if c.ok else ("FAIL" if c.blocking else "WARN")
        print(f"[{mark}] {c.name}: {c.detail}")
        if not c.ok and c.fix:
            print(f"       fix: {c.fix}")
    blocking = [c for c in checks if not c.ok and c.blocking]
    if blocking:
        print(f"\n{len(blocking)} blocking issue(s). Start with: just bootstrap")
    else:
        print("\nEnvironment ready.")


def emit_json(checks: list[Check]) -> None:
    print(
        json.dumps(
            {
                "repo": str(ROOT),
                "upstream": UPSTREAM,
                "documented_revision": PINNED_COMMIT,
                "ready": all(c.ok for c in checks if c.blocking),
                "checks": [
                    {
                        "name": c.name,
                        "ok": c.ok,
                        "detail": c.detail,
                        "fix": c.fix,
                        "blocking": c.blocking,
                        **({"extra": c.extra} if c.extra else {}),
                    }
                    for c in checks
                ],
            },
            indent=2,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json", "direnv"), default="text")
    args = parser.parse_args(argv)

    checks = [fn() for fn in CHECKS]
    {"direnv": emit_direnv, "text": emit_text, "json": emit_json}[args.format](checks)
    return 1 if any(not c.ok and c.blocking for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
