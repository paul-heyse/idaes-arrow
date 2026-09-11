#!/usr/bin/env python3
"""
Expand abbreviated `.../file.py:LINE` anchors to full repo-root-relative paths.

Document 01 §4 requires anchors to start `idaes/`. An abbreviated anchor is not
merely a style deviation: `verify.py`'s anchor pattern does not match it, so an
abbreviated anchor is never checked. Expanding them brings those claims under
the gate.

A suffix is resolved against the tracked file list at the pinned revision and
must match exactly one path; ambiguous or unresolvable suffixes are reported and
left alone.

Usage:
    python _scripts/expand_anchors.py            # report what would change
    python _scripts/expand_anchors.py --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = DOCS.parents[1]
PIN = "70a8f4fe1"

ABBREV = re.compile(r"`\.\.\./([A-Za-z0-9_./-]+\.(?:py|json|csv|nl|svg|md|txt))(:\d+(?:-\d+)?)?`")
DOC_RE = re.compile(r"^\d\d[a-z]?_[a-z0-9_]+\.md$")


def tracked_paths() -> list[str]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", PIN, "--", "idaes"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    paths = tracked_paths()
    by_suffix: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        parts = p.split("/")
        for i in range(len(parts)):
            by_suffix["/".join(parts[i:])].append(p)

    expanded = unresolved = ambiguous = 0
    for doc in sorted(p for p in DOCS.glob("*.md") if DOC_RE.match(p.name)):
        text = doc.read_text(encoding="utf-8")
        changed = False

        def repl(m: re.Match) -> str:
            nonlocal expanded, unresolved, ambiguous, changed
            suffix, line = m.group(1), m.group(2) or ""
            hits = by_suffix.get(suffix, [])
            if len(hits) == 1:
                expanded += 1
                changed = True
                return f"`{hits[0]}{line}`"
            if not hits:
                unresolved += 1
                print(f"  UNRESOLVED {doc.name}: .../{suffix}{line}")
            else:
                ambiguous += 1
                print(f"  AMBIGUOUS  {doc.name}: .../{suffix} -> {len(hits)} paths")
            return m.group(0)

        new = ABBREV.sub(repl, text)
        if changed and args.apply:
            doc.write_text(new, encoding="utf-8")

    verb = "expanded" if args.apply else "would expand"
    print(f"\n{verb} {expanded} anchors; {unresolved} unresolved, {ambiguous} ambiguous")
    return 1 if (unresolved or ambiguous) else 0


if __name__ == "__main__":
    raise SystemExit(main())
