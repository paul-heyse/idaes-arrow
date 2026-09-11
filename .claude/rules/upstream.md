---
description: Editing upstream-maintained Python
paths:
  - "idaes/**"
---

# Editing upstream code

This tree is maintained by IDAES/idaes-pse. Every file this fork modifies is a
conflict waiting at the next `just sync-upstream`.

- **Added files are cheap. Modified files are not.** Prefer a new module in
  `idaes/accel/` over an edit here.
- When an edit is unavoidable, keep it minimal and local. Do not reflow, rename
  or reorganise while you are in there.
- `just divergence` prints the current cost. It is expected to be dominated by
  additions; a growing list of modified files is the thing to watch.
- Every `.py` under `idaes/` needs the 12-line IDAES header
  (`just py-headers`); `idaes/tests/test_headers.py` enforces it.

Note the tree was reformatted once with `ruff format` (170 files), so some
conflict surface already exists. That was a deliberate, recorded trade.

`docs-code-update/authoritative_design/` documents this tree as it stood at
`70a8f4fe1` and is authoritative for *upstream's* design — but it predates the
fork's changes and never mentions `idaes/accel/`.
