#!/usr/bin/env python3
"""
Generate the tables for 00_index_and_reading_map.md from the ledger.

The index document's coverage ledger is the set's correctness contract: every
source file and every shipped asset assigned to exactly one document. It is
generated, never hand-maintained, so it cannot drift from the ledger the verify
script checks.

Usage:
    python _scripts/make_index_tables.py            # all tables to stdout
    python _scripts/make_index_tables.py --table summary
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
GEN = DOCS / "_generated"

# Canonical filenames come from ledger.py, the single place they are defined,
# so the index can never name a file the ledger does not assign work to.
import sys
sys.path.insert(0, str(HERE))
from ledger import DOC_TITLES as _LEDGER_NAMES  # noqa: E402

FILENAMES = dict(_LEDGER_NAMES)
# Document 08 is split; the ledger names the first half, so the second is added
# here for the index listing.
FILENAMES["08"] = "08a_model_introspection_and_persistence"
FILENAMES["08b"] = "08b_core_support_utilities"
FILENAMES.setdefault("00", "00_index_and_reading_map")
FILENAMES.setdefault("28", "28_data_and_file_format_inventory")
FILENAMES.setdefault("29", "29_dependency_and_layering_map")
FILENAMES.setdefault("31", "31_extension_point_catalog")

TITLES = {
    "00": "Index and reading map", "01": "Glossary and conventions",
    "02": "Runtime platform and command line interface",
    "03": "Block hierarchy and construction protocol",
    "04": "Control volume framework", "05": "Property and reaction framework",
    "06": "Model preparation: Initializers and Scalers",
    "07": "Diagnostics and run orchestration", "08": "Core utility library",
    "09": "Surrogate subsystem", "10": "Unit models: control-volume based",
    "11": "Unit models: network, contactors and control",
    "12": "Modular properties: the generic framework",
    "13": "Modular properties: equations of state and phase equilibrium",
    "14": "Modular properties: state definitions and correlation libraries",
    "15": "Property package catalog", "16": "General Helmholtz property system",
    "17": "Costing framework and libraries",
    "18": "Power generation: boiler island",
    "19": "Power generation: heat exchangers and properties",
    "20": "Power generation: Helmholtz units and solid oxide cells",
    "21": "Column models and solvent systems", "22": "Gas-solid contactors",
    "23": "Temperature swing adsorption, gas distribution and CCU",
    "24": "Reference flowsheets and demonstrations", "25": "Grid integration",
    "26": "MatOpt", "27": "Dynamic optimization and uncertainty",
    "28": "Data and file format inventory", "29": "Dependency and layering map",
    "30": "Numerics and solver interface map", "31": "Extension point catalog",
    "32": "Repository engineering",
}


def load():
    rows = list(csv.DictReader((GEN / "ledger.csv").open(encoding="utf-8")))
    manifest = json.loads((GEN / "manifest.json").read_text())
    return rows, manifest


def table_summary(rows, manifest) -> str:
    per = defaultdict(lambda: {"modules": 0, "loc": 0, "assets": 0, "bytes": 0})
    for r in rows:
        if r["role"] != "source":
            continue
        d = per[r["doc"]]
        if r["kind"] == "module":
            d["modules"] += 1
            d["loc"] += int(r["loc"] or 0)
        else:
            d["assets"] += 1
            d["bytes"] += int(r["bytes"] or 0)

    out = ["| Doc | Title | Modules | LOC | Assets |", "|---|---|---:|---:|---:|"]
    tm = tl = ta = 0
    for doc in sorted(TITLES):
        d = per.get(doc, {"modules": 0, "loc": 0, "assets": 0})
        tm += d["modules"]; tl += d["loc"]; ta += d["assets"]
        name = FILENAMES[doc]
        mods = str(d["modules"]) if d["modules"] else "—"
        loc = f"{d['loc']:,}" if d["loc"] else "—"
        assets = str(d["assets"]) if d["assets"] else "—"
        out.append(f"| [{doc}]({name}.md) | {TITLES[doc]} | {mods} | {loc} | {assets} |")
    out.append(f"| | **Total** | **{tm}** | **{tl:,}** | **{ta}** |")
    return "\n".join(out)


def table_census(rows, manifest) -> str:
    c = manifest["counts"]
    pairs = [
        ("Source modules", f"{c['source_modules']:,}"),
        ("Source lines of code", f"{c['source_loc']:,}"),
        ("Test modules", f"{c['test_modules']:,}"),
        ("Test lines of code", f"{c['test_loc']:,}"),
        ("Source directories", f"{c['source_dirs']}"),
        ("Classes", f"{c['classes']:,}"),
        ("Module-level functions", f"{c['module_level_functions']:,}"),
        ("Process block classes", f"{c['process_block_classes']}"),
        ("Configuration keys", f"{c['config_keys']:,}"),
        ("Abstract hooks (NotImplementedError)", f"{c['not_implemented_hooks']}"),
        ("Enumerations", f"{c['enums']}"),
        ("External library bindings", f"{c['external_binding_sites']}"),
        ("Deprecation sites", f"{c['deprecation_sites']}"),
        ("Shipped non-Python assets", f"{c['assets']}"),
    ]
    out = ["| Quantity | Value |", "|---|---:|"]
    out += [f"| {k} | {v} |" for k, v in pairs]
    return "\n".join(out)


def table_assets(rows, manifest) -> str:
    hist = manifest["asset_ext_histogram"]
    out = ["| Extension | Count | Owning documents |", "|---|---:|---|"]
    by_ext = defaultdict(set)
    for r in rows:
        if r["kind"] == "asset":
            by_ext[Path(r["file"]).suffix.lstrip(".") or "(none)"].add(r["doc"])
    for ext, n in hist.items():
        docs = ", ".join(sorted(by_ext.get(ext, [])))
        out.append(f"| `.{ext}` | {n} | {docs} |")
    return "\n".join(out)


def table_ledger(rows, manifest) -> str:
    out = ["| File | Kind | LOC | Doc |", "|---|---|---:|---|"]
    for r in sorted(rows, key=lambda x: x["file"]):
        if r["role"] != "source":
            continue
        out.append(f"| `{r['file']}` | {r['kind']} | {r['loc'] or '—'} | {r['doc']} |")
    return "\n".join(out)


TABLES = {
    "summary": table_summary,
    "census": table_census,
    "assets": table_assets,
    "ledger": table_ledger,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", choices=sorted(TABLES))
    args = ap.parse_args()
    rows, manifest = load()
    names = [args.table] if args.table else ["census", "summary", "assets"]
    for n in names:
        print(f"<!-- table: {n} -->")
        print(TABLES[n](rows, manifest))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
