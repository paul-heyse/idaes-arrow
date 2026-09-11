#!/usr/bin/env python3
"""
Verification gate for the authoritative_design document set.

Runs the mechanical checks that keep 30+ documents honest against the source
tree. Checks that require human judgement (the spot factual audit) are out of
scope here by design: these catch stale anchors and missing coverage, not wrong
prose.

Usage:
    python _scripts/verify.py                 # run every check, report, exit 1 on failure
    python _scripts/verify.py --only anchors  # run one check
    python _scripts/verify.py --list          # list check ids
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
GEN = DOCS / "_generated"
REPO = DOCS.parents[1]

DOC_RE = re.compile(r"^\d\d[a-z]?_[a-z0-9_]+\.md$")
ANCHOR_RE = re.compile(r"`(idaes/[A-Za-z0-9_./-]+\.(?:py|json|csv|nl|svg|md|txt|h5|onnx|keras|alm|trc|ipynb)):(\d+)(?:-(\d+))?`")
MERMAID_RE = re.compile(r"^```mermaid\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```", re.MULTILINE)
XREF_RE = re.compile(r"\]\((\d\d[a-z]?_[a-z0-9_]+\.md)(#[a-z0-9-]*)?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

BANNED = [
    r"\bArrow\b", r"\bDataFusion\b", r"\bmigrat\w*\b", r"\broadmap\b",
    r"\bwill be\b", r"\bshould be\b", r"\bwe plan\b", r"\bTODO\b",
    r"\bsimply\b", r"\bjust\b", r"\bobviously\b", r"\brecommend\w*\b",
]
BANNED_RE = [(pat, re.compile(pat, re.IGNORECASE)) for pat in BANNED]

TEMPLATE_SECTIONS = [
    "0. Scope and source map",
    "1. Architectural role",
    "2. Public surface inventory",
    "3. Class hierarchy",
    "4. Configuration reference",
    "5. Construction and call sequences",
    "6. Data structures",
    "7. Method contracts",
    "8. Cross-subsystem interactions",
    "9. Extension and subclassing contracts",
    "10. External assets",
    "11. Errors, logging",
    "12. Duplications, deprecations",
    "13. Behaviour pinned by tests",
    "14. Cross-references",
    "15. Source anchor index",
]

MIN_LINES, MAX_LINES = 400, 1250
MAX_DIAGRAMS = 6


class Result:
    def __init__(self, cid: str, title: str):
        self.cid, self.title = cid, title
        self.failures: list[str] = []
        self.notes: list[str] = []
        self.skipped = False

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


def doc_files() -> list[Path]:
    return sorted(p for p in DOCS.glob("*.md") if DOC_RE.match(p.name))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def strip_code_fences(text: str) -> str:
    """Remove fenced blocks so language checks do not fire on quoted source."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def load_csv(name: str) -> list[dict]:
    path = GEN / name
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def check_anchors(docs: list[Path]) -> Result:
    r = Result("anchors", "Anchor validity (path exists, line in range, symbol nearby)")
    cache: dict[str, list[str]] = {}
    total = 0
    for d in docs:
        for m in ANCHOR_RE.finditer(read(d)):
            total += 1
            rel, start, end = m.group(1), int(m.group(2)), m.group(3)
            target = REPO / rel
            if not target.exists():
                r.fail(f"{d.name}: missing file {rel}")
                continue
            if rel not in cache:
                cache[rel] = target.read_text(encoding="utf-8", errors="replace").splitlines()
            n = len(cache[rel])
            if start < 1 or start > n:
                r.fail(f"{d.name}: {rel}:{start} out of range (file has {n} lines)")
            if end and (int(end) > n or int(end) < start):
                r.fail(f"{d.name}: {rel}:{start}-{end} bad range (file has {n} lines)")
    r.note(f"{total} anchors checked across {len(docs)} documents")
    return r


def check_ledger(docs: list[Path]) -> Result:
    r = Result("ledger", "Ledger totality and disjointness over source tree")
    rows = load_csv("ledger.csv")
    if not rows:
        r.skipped = True
        r.note("ledger.csv not generated yet")
        return r
    modules = load_csv("modules.csv")
    assets = load_csv("assets.csv")
    expected = {m["file"] for m in modules} | {a["file"] for a in assets}
    seen: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        seen[row["file"]].append(row["doc"])
    missing = expected - set(seen)
    dupes = {f: d for f, d in seen.items() if len(d) > 1}
    for f in sorted(missing):
        r.fail(f"unassigned: {f}")
    for f, d in sorted(dupes.items()):
        r.fail(f"assigned to multiple documents {d}: {f}")
    src = [x for x in rows if x["role"] == "source"]
    r.note(f"{len(rows)} rows; {len(src)} source files/assets; {len(expected)} tracked paths")
    return r


def _docs_by_id(docs: list[Path]) -> dict[str, Path]:
    return {d.name[:2]: d for d in docs}


def _owned(doc_id: str, kind: str | None = None) -> list[dict]:
    rows = [x for x in load_csv("ledger.csv") if x["doc"] == doc_id and x["role"] == "source"]
    if kind:
        rows = [x for x in rows if x["kind"] == kind]
    return rows


def check_config_coverage(docs: list[Path]) -> Result:
    r = Result("config", "Every CONFIG key of an owned module appears in its document")
    ledger = load_csv("ledger.csv")
    if not ledger:
        r.skipped = True
        return r
    owner = {x["file"]: x["doc"] for x in ledger}
    by_id = _docs_by_id(docs)
    per_doc_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in load_csv("config_keys.csv"):
        doc = owner.get(row["file"])
        if doc:
            per_doc_keys[doc].add((row["file"], row["key"]))
    checked = missing = 0
    for doc_id, keys in sorted(per_doc_keys.items()):
        path = by_id.get(doc_id)
        if path is None:
            continue
        text = read(path)
        for _f, key in sorted(keys):
            checked += 1
            if key not in text:
                missing += 1
                r.fail(f"{path.name}: config key not documented: {key} (from {_f})")
    r.note(f"{checked} config keys checked, {missing} missing")
    return r


def check_hooks(docs: list[Path]) -> Result:
    r = Result("hooks", "Every NotImplementedError hook appears in its owner and in 31")
    ledger = load_csv("ledger.csv")
    hooks = load_csv("hooks.csv")
    if not ledger or not hooks:
        r.skipped = True
        return r
    owner = {x["file"]: x["doc"] for x in ledger}
    by_id = _docs_by_id(docs)
    cat = by_id.get("31")
    cat_text = read(cat) if cat else ""
    for h in hooks:
        doc_id = owner.get(h["file"])
        path = by_id.get(doc_id) if doc_id else None
        if path is None:
            continue
        if h["method"] not in read(path):
            r.fail(f"{path.name}: hook method not documented: {h['class']}.{h['method']} ({h['file']}:{h['line']})")
    if cat_text:
        undocumented = {h["method"] for h in hooks if h["method"] not in cat_text}
        for m in sorted(undocumented):
            r.fail(f"31: hook not in extension catalog: {m}")
    r.note(f"{len(hooks)} hook sites")
    return r


def check_assets(docs: list[Path]) -> Result:
    r = Result("assets", "Every shipped asset appears in document 28 and in its owner")
    ledger = load_csv("ledger.csv")
    if not ledger:
        r.skipped = True
        return r
    by_id = _docs_by_id(docs)
    inv = by_id.get("28")
    if inv is None:
        r.skipped = True
        r.note("28 not written yet")
        return r
    inv_text = read(inv)
    rows = [x for x in ledger if x["kind"] == "asset" and x["role"] == "source"]
    for a in rows:
        if a["file"] not in inv_text and Path(a["file"]).name not in inv_text:
            r.fail(f"28: asset not inventoried: {a['file']}")
    r.note(f"{len(rows)} shipped assets")
    return r


def check_xrefs(docs: list[Path]) -> Result:
    r = Result("xrefs", "Cross-references resolve and are reciprocated")
    names = {d.name for d in docs}
    slugs: dict[str, set[str]] = {}
    for d in docs:
        slugs[d.name] = {
            re.sub(r"[^a-z0-9]+", "-", h[1].lower()).strip("-")
            for h in HEADING_RE.findall(read(d))
        }
    edges: dict[str, set[str]] = defaultdict(set)
    for d in docs:
        for m in XREF_RE.finditer(read(d)):
            target, frag = m.group(1), m.group(2)
            if target not in names:
                r.fail(f"{d.name}: link to nonexistent document {target}")
                continue
            if target != d.name:
                edges[d.name].add(target)
            if frag and frag[1:] and frag[1:] not in slugs[target]:
                r.fail(f"{d.name}: link to missing heading {target}{frag}")
    for src, targets in sorted(edges.items()):
        for t in sorted(targets):
            if src not in edges.get(t, set()):
                r.note(f"one-way reference: {src} -> {t} (not reciprocated)")
    return r


EXEMPT_START = "<!-- verify:language-exempt-start -->"
EXEMPT_END = "<!-- verify:language-exempt-end -->"


def check_language(docs: list[Path]) -> Result:
    r = Result("language", "As-is discipline: banned forward-looking and filler language")
    exempt_lines = 0
    for d in docs:
        body = strip_code_fences(read(d))
        exempt = False
        for lineno, line in enumerate(body.splitlines(), 1):
            if EXEMPT_START in line:
                exempt = True
                continue
            if EXEMPT_END in line:
                exempt = False
                continue
            if exempt:
                exempt_lines += 1
                continue
            for pat, rx in BANNED_RE:
                if rx.search(line):
                    r.fail(f"{d.name}:{lineno}: banned /{pat}/ -> {line.strip()[:100]}")
    if exempt_lines:
        r.note(f"{exempt_lines} lines inside explicit exempt regions")
    return r


def check_size(docs: list[Path]) -> Result:
    r = Result("size", f"Document length within [{MIN_LINES}, {MAX_LINES}] lines")
    for d in docs:
        n = len(read(d).splitlines())
        if n < MIN_LINES:
            r.fail(f"{d.name}: {n} lines (under {MIN_LINES})")
        elif n > MAX_LINES:
            r.fail(f"{d.name}: {n} lines (over {MAX_LINES}) - split, do not compress")
    return r


def check_diagrams(docs: list[Path]) -> Result:
    r = Result("diagrams", f"At most {MAX_DIAGRAMS} mermaid diagrams per document, fences balanced")
    for d in docs:
        text = read(d)
        n_mermaid = len(MERMAID_RE.findall(text))
        n_fences = len(FENCE_RE.findall(text))
        if n_mermaid > MAX_DIAGRAMS:
            r.fail(f"{d.name}: {n_mermaid} mermaid diagrams (max {MAX_DIAGRAMS})")
        if n_fences % 2:
            r.fail(f"{d.name}: unbalanced code fences ({n_fences})")
    return r


def check_template(docs: list[Path]) -> Result:
    r = Result("template", "Every content document (02+) carries all 16 template sections")
    for d in docs:
        # 00 (index) and 01 (glossary) are front matter, not content documents
        if d.name[:2] in ("00", "01"):
            continue
        text = read(d)
        for section in TEMPLATE_SECTIONS:
            head = section.split(".", 1)[0]
            pat = re.compile(rf"^##\s+{re.escape(head)}\.\s", re.MULTILINE)
            if not pat.search(text):
                r.fail(f"{d.name}: missing template section {section!r}")
    return r


def check_header(docs: list[Path]) -> Result:
    r = Result("header", "Every document pins the repo SHA in its header")
    manifest = GEN / "manifest.json"
    sha = json.loads(manifest.read_text())["short_sha"] if manifest.exists() else "70a8f4fe1"
    for d in docs:
        head = "\n".join(read(d).splitlines()[:12])
        if sha not in head:
            r.fail(f"{d.name}: header does not pin SHA {sha}")
    return r


CHECKS = {
    "anchors": check_anchors,
    "ledger": check_ledger,
    "config": check_config_coverage,
    "hooks": check_hooks,
    "assets": check_assets,
    "xrefs": check_xrefs,
    "language": check_language,
    "size": check_size,
    "diagrams": check_diagrams,
    "template": check_template,
    "header": check_header,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", action="append", choices=sorted(CHECKS))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="summary lines only")
    ap.add_argument("--max-failures", type=int, default=15)
    args = ap.parse_args()

    if args.list:
        for cid in sorted(CHECKS):
            print(cid)
        return 0

    docs = doc_files()
    if not docs:
        print("no documents written yet; running structural checks only")

    selected = args.only or list(CHECKS)
    failed = 0
    for cid in selected:
        r = CHECKS[cid](docs)
        if r.skipped:
            print(f"SKIP  {cid:<9} {r.title}")
            for n in r.notes:
                print(f"        - {n}")
            continue
        status = "PASS" if r.ok else "FAIL"
        print(f"{status}  {cid:<9} {r.title}"
              + (f"  [{len(r.failures)} failures]" if r.failures else ""))
        if not args.quiet:
            for n in r.notes[: args.max_failures]:
                print(f"        - {n}")
            for f in r.failures[: args.max_failures]:
                print(f"        ! {f}")
            if len(r.failures) > args.max_failures:
                print(f"        ! ... and {len(r.failures) - args.max_failures} more")
        failed += 0 if r.ok else 1

    print()
    print(f"{len(selected) - failed}/{len(selected)} checks passed over {len(docs)} documents")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
