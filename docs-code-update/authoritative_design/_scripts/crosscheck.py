#!/usr/bin/env python3
"""
Cross-check the Python `ast` inventory against the ast-grep rule set.

Two independent extractors derive the same structural facts from the same tree:

  * ``_scripts/inventory.py``  — CPython's own ``ast`` module
  * ``sgrules/*.yml``          — ast-grep tree-sitter rules, run via ``ast-grep scan``

Agreement is evidence the facts are counted correctly; disagreement has already
caught one real defect (multi-line ``@deprecated(...)`` decorators counted twice
by the Python extractor). This script is the standing version of that check.

Usage:
    python _scripts/crosscheck.py            # report, exit 1 on mismatch
    python _scripts/crosscheck.py --verbose  # list the differing sites
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
GEN = DOCS / "_generated"
REPO = DOCS.parents[1]
SGCONFIG = DOCS / "sgconfig.yml"

# rule id -> (generated csv, human label)
PAIRS = {
    "idaes-process-block-class": ("process_blocks.csv", "declare_process_block_class classes"),
    "idaes-config-declare": ("config_keys.csv", "CONFIG.declare keys"),
    "idaes-not-implemented-hook": ("hooks.csv", "NotImplementedError hooks"),
    "idaes-external-library-binding": ("externals.csv", "external library bindings"),
    "idaes-deprecation-site": ("deprecations.csv", "deprecation sites"),
    "idaes-enum-class": ("enums.csv", "enumeration classes"),
}

# Sites where the two extractors legitimately anchor to different lines.
# Nothing is listed here today; entries require a written justification.
LINE_ANCHOR_EXEMPTIONS: set[tuple[str, str]] = set()


PINNED_SHA = "70a8f4fe1"


@contextlib.contextmanager
def pinned_tree():
    """Export `idaes/` at the documented revision into a temporary directory.

    ast-grep scans a filesystem, so comparing it against an inventory taken at a
    fixed revision requires materialising that revision. Scanning the working
    tree instead would silently compare two different subjects whenever the
    repository moves ahead of the pin.
    """
    with tempfile.TemporaryDirectory(prefix="idaes-pinned-") as tmp:
        archive = subprocess.run(
            ["git", "archive", PINNED_SHA, "idaes"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True)
        yield Path(tmp)


def sg_matches(rule_id: str, root: Path) -> list[dict]:
    proc = subprocess.run(
        [
            "ast-grep", "scan",
            "--config", str(SGCONFIG),
            "--filter", f"^{rule_id}$",
            "--globs", "!**/tests/**",
            "--globs", "!**/conftest.py",
            "--json=compact",
            "idaes",
        ],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):
        raise SystemExit(f"ast-grep failed for {rule_id}: {proc.stderr.strip()}")
    out = proc.stdout.strip()
    if not out:
        return []
    return json.loads(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--compare-lines", action="store_true",
                    help="also require both extractors to anchor to the same line")
    args = ap.parse_args()

    failures = 0
    print(f"comparing both extractors at the documented revision {PINNED_SHA}\n")
    print(f"{'fact':<38} {'ast':>6} {'ast-grep':>9}  status")
    print("-" * 72)

    stack = contextlib.ExitStack()
    root = stack.enter_context(pinned_tree())

    for rule_id, (csv_name, label) in PAIRS.items():
        rows = list(csv.DictReader((GEN / csv_name).open(encoding="utf-8")))
        matches = sg_matches(rule_id, root)

        n_py, n_sg = len(rows), len(matches)
        ok = n_py == n_sg
        status = "agree" if ok else "MISMATCH"
        print(f"{label:<38} {n_py:>6} {n_sg:>9}  {status}")
        if not ok:
            failures += 1

        if args.verbose or not ok:
            py_files = {r["file"] for r in rows}
            sg_files = {m["file"] for m in matches}
            for f in sorted(py_files - sg_files):
                print(f"      ast only, file: {f}")
            for f in sorted(sg_files - py_files):
                print(f"      ast-grep only, file: {f}")

        if args.compare_lines and ok:
            py_sites = {(r["file"], int(r["line"])) for r in rows}
            sg_sites = {
                (m["file"], m["range"]["start"]["line"] + 1) for m in matches
            }
            drift = (py_sites ^ sg_sites) - LINE_ANCHOR_EXEMPTIONS
            if drift:
                print(f"      line-anchor drift at {len(drift)} sites")
                if args.verbose:
                    for f, l in sorted(drift):
                        print(f"        {f}:{l}")

    stack.close()
    print()
    if failures:
        print(f"{len(PAIRS) - failures}/{len(PAIRS)} facts agree - investigate the mismatches")
        return 1
    print(f"all {len(PAIRS)} structural facts agree across both extractors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
