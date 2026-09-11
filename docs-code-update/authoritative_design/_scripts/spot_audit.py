#!/usr/bin/env python3
"""
Sample anchors from the document set and print the source line each one cites.

The automated checks in verify.py prove an anchor RESOLVES. They cannot prove it
supports the claim next to it. This script supports the one check that needs a
human: pick anchors at random, show the claim and the cited source side by side,
and read them.

Usage:
    python _scripts/spot_audit.py                 # 10 anchors from across the set
    python _scripts/spot_audit.py --doc 04 -n 15  # 15 from one document
    python _scripts/spot_audit.py --seed 7        # reproducible sample
"""

from __future__ import annotations

import argparse
import random
import re
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = DOCS.parents[1]

ANCHOR_RE = re.compile(r"`(idaes/[A-Za-z0-9_./-]+\.py):(\d+)(?:-(\d+))?`")
DOC_RE = re.compile(r"^\d\d[a-z]?_[a-z0-9_]+\.md$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", help="restrict to one document number, e.g. 04")
    ap.add_argument("-n", type=int, default=10, help="how many anchors to sample")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--context", type=int, default=1, help="source lines either side")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    docs = sorted(p for p in DOCS.glob("*.md") if DOC_RE.match(p.name))
    if args.doc:
        docs = [d for d in docs if d.name.startswith(args.doc)]
    if not docs:
        print("no matching documents")
        return 1

    found: list[tuple[Path, int, str, str, int]] = []
    for d in docs:
        lines = d.read_text(encoding="utf-8").splitlines()
        in_index = False
        for i, line in enumerate(lines, 1):
            # Skip the section 15 anchor index: those rows are the anchor list
            # itself, not claims about the code.
            if line.startswith("## 15."):
                in_index = True
            elif line.startswith("## "):
                in_index = False
            if in_index:
                continue
            for m in ANCHOR_RE.finditer(line):
                found.append((d, i, line.strip(), m.group(1), int(m.group(2))))

    if not found:
        print("no anchors found outside the anchor indexes")
        return 1

    sample = rng.sample(found, min(args.n, len(found)))
    print(f"{len(found)} claim-bearing anchors across {len(docs)} documents; "
          f"showing {len(sample)}\n")

    cache: dict[str, list[str]] = {}
    for doc, doc_line, claim, path, line_no in sample:
        if path not in cache:
            cache[path] = (REPO / path).read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        src = cache[path]
        lo = max(1, line_no - args.context)
        hi = min(len(src), line_no + args.context)

        print("=" * 78)
        print(f"{doc.name}:{doc_line}")
        for chunk in textwrap.wrap(claim, 76, initial_indent="  ", subsequent_indent="  "):
            print(chunk)
        print(f"  -> {path}:{line_no}")
        for n in range(lo, hi + 1):
            marker = ">>" if n == line_no else "  "
            print(f"  {marker} {n:>5} | {src[n - 1][:90]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
