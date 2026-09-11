#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES).
#
# Copyright (c) 2018-2026 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National Laboratory,
# National Technology & Engineering Solutions of Sandia, LLC, Carnegie Mellon
# University, West Virginia University Research Corporation, et al.
# All rights reserved.  Please see the files COPYRIGHT.md and LICENSE.md
# for full copyright and license information.
#################################################################################
"""Check (or apply) the SPDX license header on Rust sources under ``rust/``.

``addheader`` is not used for Rust: it is configured in ``addheader.yml`` for
``*.py`` under ``idaes/`` with the twelve-line IDAES block, and that block asserts
copyright held by institutions that did not author this fork's Rust code. New
``.rs`` files carry a short SPDX header instead. See ``FORK.md``.

Usage::

    python scripts/check_rust_headers.py          # check, non-zero on failure
    python scripts/check_rust_headers.py --fix    # prepend where missing
"""

import argparse
import sys
from pathlib import Path

HEADER = """\
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.
"""

ROOT = Path(__file__).resolve().parent.parent
RUST_DIR = ROOT / "rust"
# Build output and vendored corpora are not ours to annotate.
SKIP_DIRS = {"target", "corpus", "artifacts"}


def rust_sources():
    for path in sorted(RUST_DIR.rglob("*.rs")):
        if SKIP_DIRS & set(path.relative_to(RUST_DIR).parts):
            continue
        yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix", action="store_true", help="prepend the header where it is missing"
    )
    args = parser.parse_args(argv)

    missing = []
    for path in rust_sources():
        text = path.read_text(encoding="utf-8")
        if text.startswith(HEADER):
            continue
        if args.fix:
            path.write_text(HEADER + "\n" + text.lstrip("\n"), encoding="utf-8")
        else:
            missing.append(path.relative_to(ROOT))

    if missing:
        print("Missing SPDX header (run with --fix):", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    checked = sum(1 for _ in rust_sources())
    print(f"license headers ok ({checked} Rust files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
