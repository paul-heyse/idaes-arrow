#!/usr/bin/env python3
"""Compare ruff and pyrefly findings against a recorded baseline.

Neither tool has a native baseline, so this supplies one for both.

Why counts keyed on ``(file, rule)`` rather than line numbers: a line-keyed
baseline invalidates itself the moment anything is reformatted or a line is
inserted. Keying on the pair, with a count, survives edits while still catching
a genuinely new violation.

The ratchet cuts both ways. A count going *up* fails, because that is a new
defect. A count going *down* also fails, telling you to re-record -- otherwise
fixed findings stay budgeted forever and the baseline never shrinks.

    just lint-py          # ruff vs baseline
    just typecheck        # pyrefly vs baseline
    just baseline-update  # re-record both (confirms first)
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = ROOT / ".quality"
VENV_BIN = ROOT / ".venv" / "bin"


def pinned_version(tool: str) -> str:
    """The version recorded in pyproject's quality dependency group."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for spec in data.get("dependency-groups", {}).get("quality", []):
        if isinstance(spec, str) and spec.startswith(f"{tool}=="):
            return spec.split("==", 1)[1].strip()
    return "unknown"


def collect_ruff() -> collections.Counter:
    exe = VENV_BIN / "ruff"
    proc = subprocess.run(
        [str(exe), "check", "--output-format", "json", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        sys.exit(f"ruff failed ({proc.returncode}):\n{proc.stderr}")
    counts: collections.Counter = collections.Counter()
    for item in json.loads(proc.stdout or "[]"):
        path = Path(item["filename"])
        rel = path.relative_to(ROOT) if path.is_absolute() else path
        counts[f"{rel}::{item['code']}"] += 1
    return counts


def collect_pyrefly() -> collections.Counter:
    exe = VENV_BIN / "pyrefly"
    proc = subprocess.run(
        [str(exe), "check", "--output-format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = proc.stdout.strip()
    if not payload:
        sys.exit(f"pyrefly produced no JSON ({proc.returncode}):\n{proc.stderr}")
    data = json.loads(payload)
    errors = data["errors"] if isinstance(data, dict) and "errors" in data else data
    counts: collections.Counter = collections.Counter()
    for item in errors:
        path = Path(item.get("path") or item.get("file", "?"))
        rel = path.relative_to(ROOT) if path.is_absolute() else path
        kind = item.get("name") or item.get("kind") or "unknown"
        counts[f"{rel}::{kind}"] += 1
    return counts


COLLECTORS = {"ruff": collect_ruff, "pyrefly": collect_pyrefly}


def baseline_path(tool: str) -> Path:
    return BASELINE_DIR / f"{tool}-baseline.json"


def load(tool: str) -> tuple[collections.Counter, str]:
    path = baseline_path(tool)
    if not path.exists():
        return collections.Counter(), ""
    blob = json.loads(path.read_text(encoding="utf-8"))
    return collections.Counter(blob["counts"]), blob.get("tool_version", "")


def save(tool: str, counts: collections.Counter) -> None:
    BASELINE_DIR.mkdir(exist_ok=True)
    baseline_path(tool).write_text(
        json.dumps(
            {
                "tool": tool,
                # Recorded so a baseline taken with a different version is
                # self-evident rather than mysteriously wrong.
                "tool_version": pinned_version(tool),
                "total": sum(counts.values()),
                "counts": dict(sorted(counts.items())),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def cmd_update(tool: str) -> int:
    counts = COLLECTORS[tool]()
    save(tool, counts)
    print(
        f"{tool}: recorded {sum(counts.values())} findings "
        f"across {len(counts)} (file, rule) pairs at version {pinned_version(tool)}"
    )
    return 0


def cmd_check(tool: str) -> int:
    current = COLLECTORS[tool]()
    baseline, recorded_version = load(tool)
    pinned = pinned_version(tool)

    if not baseline_path(tool).exists():
        print(f"{tool}: no baseline yet -- run `just baseline-update`", file=sys.stderr)
        return 1
    if recorded_version and recorded_version != pinned:
        print(
            f"{tool}: baseline was recorded with {recorded_version} but "
            f"{pinned} is pinned -- run `just baseline-update`",
            file=sys.stderr,
        )
        return 1

    worse = {
        k: (baseline.get(k, 0), v) for k, v in current.items() if v > baseline.get(k, 0)
    }
    better = {
        k: (baseline[k], current.get(k, 0))
        for k in baseline
        if current.get(k, 0) < baseline[k]
    }

    if worse:
        print(f"{tool}: {len(worse)} new or increased finding(s):", file=sys.stderr)
        for key, (was, now) in sorted(worse.items())[:40]:
            path, _, rule = key.rpartition("::")
            print(f"  {path}  {rule}  {was} -> {now}", file=sys.stderr)
        if len(worse) > 40:
            print(f"  ... and {len(worse) - 40} more", file=sys.stderr)
        return 1

    if better:
        total = sum(was - now for was, now in better.values())
        print(
            f"{tool}: {total} finding(s) fixed in {len(better)} place(s). "
            "Run `just baseline-update` so the ratchet holds.",
            file=sys.stderr,
        )
        return 1

    print(f"{tool}: {sum(current.values())} findings, equal to baseline")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "update"))
    parser.add_argument("tool", choices=tuple(COLLECTORS))
    args = parser.parse_args(argv)
    return (cmd_check if args.command == "check" else cmd_update)(args.tool)


if __name__ == "__main__":
    sys.exit(main())
