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
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
GEN = DOCS / "_generated"
REPO = DOCS.parents[1]

DOC_RE = re.compile(r"^\d\d[a-z]?_[a-z0-9_]+\.md$")

# The revision the documents describe. Anchors resolve against this, never the
# working tree, so the checks stay meaningful while the repository moves on.
PIN = "70a8f4fe1"
ANCHOR_RE = re.compile(r"`(idaes/[A-Za-z0-9_./-]+\.(?:py|json|csv|nl|svg|md|txt|h5|onnx|keras|alm|trc|ipynb)):(\d+)(?:-(\d+))?`")
MERMAID_RE = re.compile(r"^```mermaid\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```", re.MULTILINE)
XREF_RE = re.compile(r"\]\((\d\d[a-z]?_[a-z0-9_]+\.md)(#[a-z0-9-]*)?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

# Case-insensitive bans: forward-looking and filler language.
BANNED = [
    r"\bmigrat\w*\b", r"\broadmap\b", r"\bwill be\b", r"\bshould be\b",
    r"\bwe plan\b", r"\bTODO\b", r"\bsimply\b", r"\bjust\b",
    r"\bobviously\b", r"\brecommend\w*\b",
]
# Case-SENSITIVE bans: these are proper nouns. Matching them case-insensitively
# also catches the ordinary English word "arrow", which legitimately appears in
# descriptions of Pyomo Arcs and of dependency direction.
BANNED_CASED = [r"\bArrow\b", r"\bDataFusion\b"]

BANNED_RE = [(pat, re.compile(pat, re.IGNORECASE)) for pat in BANNED]
BANNED_RE += [(pat, re.compile(pat)) for pat in BANNED_CASED]

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

# Below MIN_LINES a document is too thin for its scope. Between SOFT_MAX and
# MAX_LINES it is noted but allowed: the largest scopes in the set (26 modules /
# ~10k LOC) do not compress below that without losing content. Above MAX_LINES
# the scope needs splitting, not compressing.
MIN_LINES, SOFT_MAX, MAX_LINES = 400, 1250, 1400
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


def github_slug(heading: str) -> str:
    """Reproduce GitHub's heading-anchor algorithm.

    Downcase, drop every character that is not a letter, digit, space or
    hyphen, then replace runs of spaces with single hyphens. Note that
    punctuation is *removed*, not replaced: "5.7 Port construction" becomes
    "57-port-construction", not "5-7-port-construction".
    """
    text = heading.strip().lower()
    text = re.sub(r"[^a-z0-9 \-]+", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def load_csv(name: str) -> list[dict]:
    path = GEN / name
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def source_at_pin(rel: str) -> list[str] | None:
    """File content at the documented revision, not the working tree.

    Anchors describe a fixed revision of the library. Resolving them against the
    working tree would report a stale anchor as valid whenever a line merely
    shifted, and a valid anchor as broken whenever a file was added or removed
    after the pin.
    """
    proc = subprocess.run(
        ["git", "show", f"{PIN}:{rel}"],
        cwd=REPO, capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").splitlines()


def check_anchors(docs: list[Path]) -> Result:
    r = Result("anchors", f"Anchor validity at the documented revision {PIN}")
    cache: dict[str, list[str] | None] = {}
    total = 0
    for d in docs:
        for m in ANCHOR_RE.finditer(read(d)):
            total += 1
            rel, start, end = m.group(1), int(m.group(2)), m.group(3)
            if rel not in cache:
                cache[rel] = source_at_pin(rel)
            if cache[rel] is None:
                r.fail(f"{d.name}: {rel} does not exist at {PIN}")
                continue
            n = len(cache[rel])
            if start < 1 or start > n:
                r.fail(f"{d.name}: {rel}:{start} out of range (file has {n} lines)")
            if end and (int(end) > n or int(end) < start):
                r.fail(f"{d.name}: {rel}:{start}-{end} bad range (file has {n} lines)")
    # An abbreviated anchor such as `.../file.py:120` does not match ANCHOR_RE,
    # so it silently escapes this check entirely. 278 such anchors existed
    # before this guard. Reject them rather than let a claim go unverified.
    abbrev = re.compile(r"`\.\.\./[A-Za-z0-9_./-]+\.(?:py|json|csv|nl|svg|md|txt):\d+")
    for d in docs:
        for m in abbrev.finditer(read(d)):
            r.fail(
                f"{d.name}: abbreviated anchor escapes checking: {m.group(0)}` "
                "- run _scripts/expand_anchors.py --apply"
            )
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


def _docs_by_id(docs: list[Path]) -> dict[str, list[Path]]:
    """Map a document number to every file carrying it.

    A document split into `NNa_`/`NNb_` keeps its ledger number, so one id can
    own two files. Returning a list keeps the per-document coverage checks
    looking at the whole document rather than whichever half sorted last.
    """
    by_id: dict[str, list[Path]] = defaultdict(list)
    for d in docs:
        by_id[d.name[:2]].append(d)
    return dict(by_id)


def _combined(paths: list[Path]) -> str:
    return "\n".join(read(p) for p in paths)


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
        paths = by_id.get(doc_id)
        if not paths:
            continue
        text = _combined(paths)
        label = "+".join(p.name for p in paths)
        for _f, key in sorted(keys):
            checked += 1
            if key not in text:
                missing += 1
                r.fail(f"{label}: config key not documented: {key} (from {_f})")
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
    cat_text = _combined(cat) if cat else ""
    for h in hooks:
        doc_id = owner.get(h["file"])
        paths = by_id.get(doc_id) if doc_id else None
        if not paths:
            continue
        if h["method"] not in _combined(paths):
            label = "+".join(p.name for p in paths)
            r.fail(f"{label}: hook method not documented: {h['class']}.{h['method']} ({h['file']}:{h['line']})")
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
    if not inv:
        r.skipped = True
        r.note("28 not written yet")
        return r
    inv_text = _combined(inv)
    rows = [x for x in ledger if x["kind"] == "asset" and x["role"] == "source"]
    for a in rows:
        if a["file"] not in inv_text and Path(a["file"]).name not in inv_text:
            r.fail(f"28: asset not inventoried: {a['file']}")
    r.note(f"{len(rows)} shipped assets")
    return r


# The 33 documents named in the plan. A link to one of these that does not yet
# exist is pending, not broken; a link to anything else is broken.
PLANNED = {
    "00_index_and_reading_map", "01_glossary_and_conventions",
    "02_runtime_platform_and_cli", "03_block_hierarchy_and_construction_protocol",
    "04_control_volume_framework", "05_property_and_reaction_framework",
    "06_model_preparation_initializers_and_scalers",
    "07_diagnostics_and_run_orchestration",
    "09_surrogate_subsystem", "10_unit_models_control_volume_based",
    "11_unit_models_network_contactors_and_control",
    "12_modular_properties_generic_framework",
    "13_modular_properties_eos_and_phase_equilibrium",
    "14_modular_properties_state_definitions_and_libraries",
    "15_property_package_catalog", "16_general_helmholtz_property_system",
    "17_costing_framework_and_libraries", "18_power_generation_boiler_island",
    "19_power_generation_heat_exchangers_and_properties",
    "20_power_generation_helmholtz_units_and_soc",
    "21_column_models_and_solvent_systems", "22_gas_solid_contactors",
    "23_tsa_gas_distribution_and_ccu",
    "24_reference_flowsheets_and_demonstrations", "25_grid_integration",
    "26_matopt", "27_dynamic_optimization_and_uncertainty",
    "28_data_and_file_format_inventory", "29_dependency_and_layering_map",
    "30_numerics_and_solver_interface_map", "31_extension_point_catalog",
    "32_repository_engineering",
}
# Pre-approved splits, used when a document's scope genuinely exceeds one file.
# The parent number is retained so existing cross-references keep resolving.
PLANNED |= {
    "07a_diagnostics", "07b_run_orchestration",
    "08a_model_introspection_and_persistence", "08b_core_support_utilities",
    "09a_surrogate_framework", "09b_pysmo",
    "12a_generic_property", "12b_generic_reaction",
}


def check_xrefs(docs: list[Path]) -> Result:
    r = Result("xrefs", "Cross-references resolve and are reciprocated")
    names = {d.name for d in docs}
    slugs: dict[str, set[str]] = {}
    for d in docs:
        slugs[d.name] = {github_slug(h[1]) for h in HEADING_RE.findall(read(d))}
    edges: dict[str, set[str]] = defaultdict(set)
    pending: set[str] = set()
    for d in docs:
        for m in XREF_RE.finditer(read(d)):
            target, frag = m.group(1), m.group(2)
            if target not in names:
                if target[:-3] in PLANNED:
                    pending.add(target)
                else:
                    r.fail(f"{d.name}: link to document outside the planned set: {target}")
                continue
            if target != d.name:
                edges[d.name].add(target)
            if frag and frag[1:] and frag[1:] not in slugs[target]:
                r.fail(f"{d.name}: link to missing heading {target}{frag}")
    for src, targets in sorted(edges.items()):
        for t in sorted(targets):
            if src not in edges.get(t, set()):
                r.note(f"one-way reference: {src} -> {t} (not reciprocated)")
    if pending:
        r.note(f"{len(pending)} planned documents linked but not yet written: "
               + ", ".join(sorted(x[:2] for x in pending)))
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
        # The minimum guards against a content document too thin for its scope.
        # Document 00 owns no source and is a manifest; its right length is
        # however long the tables are, and padding it to a line count would make
        # it worse, not better.
        if d.name.startswith("00") :
            r.note(f"{d.name}: {n} lines (index; minimum not applied)")
        elif n < MIN_LINES:
            r.fail(f"{d.name}: {n} lines (under {MIN_LINES})")
        elif n > MAX_LINES:
            r.fail(f"{d.name}: {n} lines (over {MAX_LINES}) - split, do not compress")
        elif n > SOFT_MAX:
            r.note(f"{d.name}: {n} lines (over the {SOFT_MAX} guideline, within the cap)")
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
    r = Result("header", "Every document pins the documented revision in its header")
    # The documents pin the revision of the IDAES library they describe, which is
    # not necessarily the working tree's HEAD. Check against `documented_revision`,
    # not `short_sha`, so commits that do not touch `idaes/` do not fail the gate.
    manifest = GEN / "manifest.json"
    sha = "70a8f4fe1"
    if manifest.exists():
        m = json.loads(manifest.read_text())
        sha = m.get("documented_revision", sha)
        drift = m.get("documented_subtree_changed_since_pin")
        inventoried = m.get("inventoried_revision", sha)
        if drift and not str(inventoried).startswith(sha):
            r.fail(
                f"the inventory was taken at {inventoried}, not the documented "
                f"revision {sha}, while idaes/ differs in {len(drift)} files - "
                "regenerate with the default --rev"
            )
        elif drift:
            r.note(
                f"idaes/ differs from {sha} in {len(drift)} files at HEAD; "
                "the inventory and every anchor resolve at the pinned revision, "
                "so the document set is unaffected"
            )
        elif not m.get("head_matches_documented_revision", True):
            r.note(
                f"HEAD is {m.get('short_sha')}, ahead of the documented revision "
                f"{sha}, but idaes/ is unchanged between them"
            )
    for d in docs:
        head = "\n".join(read(d).splitlines()[:12])
        if sha not in head:
            r.fail(f"{d.name}: header does not pin SHA {sha}")
    return r


# Headline counts asserted in the front matter, and where each comes from.
# `(label, manifest-key-or-callable)`. These are the numbers a reader is most
# likely to quote, so they are checked against the generated data rather than
# trusted. Two of them were wrong before this check existed: the enum count
# (55 vs 74) and the `*Scaler` class count (45 vs 46).
def _count_scaler_classes() -> int:
    return sum(1 for c in load_csv("classes.csv") if c["name"].endswith("Scaler"))


def _count_declares(field: str) -> int:
    return sum(1 for r in load_csv("retrofit.csv") if r[field] == "True")


HEADLINE_COUNTS = [
    ("Source modules", lambda m: m["counts"]["source_modules"]),
    ("Source lines of code", lambda m: m["counts"]["source_loc"]),
    ("Test modules", lambda m: m["counts"]["test_modules"]),
    ("Classes", lambda m: m["counts"]["classes"]),
    ("Process block classes", lambda m: m["counts"]["process_block_classes"]),
    ("Configuration keys", lambda m: m["counts"]["config_keys"]),
    ("Enumerations", lambda m: m["counts"]["enums"]),
    ("Shipped non-Python assets", lambda m: m["counts"]["assets"]),
]


def check_counts(docs: list[Path]) -> Result:
    r = Result("counts", "Headline counts in the front matter match the generated data")
    manifest = GEN / "manifest.json"
    if not manifest.exists():
        r.skipped = True
        return r
    m = json.loads(manifest.read_text())
    index = [d for d in docs if d.name.startswith("00")]
    if not index:
        r.skipped = True
        r.note("00 not written yet")
        return r
    text = read(index[0])
    checked = 0
    for label, getter in HEADLINE_COUNTS:
        expected = getter(m)
        # The census table renders each row as `| <label> | <value> |`, with the
        # value comma-grouped above 999.
        pat = re.compile(
            rf"^\|\s*{re.escape(label)}\s*\|\s*([\d,]+)\s*\|", re.MULTILINE
        )
        found = pat.search(text)
        if not found:
            r.fail(f"00: no census row for {label!r}")
            continue
        checked += 1
        claimed = int(found.group(1).replace(",", ""))
        if claimed != expected:
            r.fail(f"00: {label} claims {claimed:,}, generated data says {expected:,}")
    # Cross-document consistency for the two counts that were previously wrong.
    for label, actual in (("`*Scaler`", _count_scaler_classes()),):
        for d in docs:
            body = read(d)
            pat = re.compile(rf"\*\*(\d+)\*\* classes in the tree are named {re.escape(label)}")
            for mm in pat.finditer(body):
                checked += 1
                if int(mm.group(1)) != actual:
                    r.fail(f"{d.name}: claims {mm.group(1)} classes named {label}, actual {actual}")
    r.note(f"{checked} headline counts checked")
    return r


CHECKS = {
    "counts": check_counts,
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
