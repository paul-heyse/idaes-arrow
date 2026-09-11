#!/usr/bin/env python3
"""Verify every document path referenced by an agent skill actually resolves.

The skills in ``.codex/skills/`` were imported from another project and pointed
at ``docs/library_ref/``; in this repository the corpus lives at
``docs-code-update/library_ref/``. Every one of the 26 references was dead, and
nothing noticed, because a skill that routes to a missing file fails silently at
the moment an agent tries to use it.

Run by ``just lint-skills`` and by CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIRS = (ROOT / ".codex" / "skills",)
REFERENCE = re.compile(r"(?:docs|docs-code-update)/library_ref/[A-Za-z0-9_.\-]+\.md")


def main() -> int:
    broken: list[tuple[Path, str]] = []
    checked = 0
    for skills in SKILL_DIRS:
        if not skills.is_dir():
            continue
        for md in sorted(skills.rglob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            for ref in sorted(set(REFERENCE.findall(text))):
                checked += 1
                if not (ROOT / ref).is_file():
                    broken.append((md.relative_to(ROOT), ref))

    if broken:
        print(f"{len(broken)} broken skill reference(s):", file=sys.stderr)
        for skill, ref in broken:
            print(f"  {skill}: {ref}", file=sys.stderr)
        print(
            "\nDocuments live under docs-code-update/library_ref/ in this repo.",
            file=sys.stderr,
        )
        return 1

    print(f"skill references ok ({checked} checked across {len(SKILL_DIRS)} root(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
