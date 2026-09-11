#!/usr/bin/env python3
"""
Measure the internal import graph and the third-party dependency surface.

Document 29 asserts how the package tiers depend on one another. This script
derives those facts from `_generated/imports.csv` so the assertions are measured
rather than assumed, and so an upward dependency cannot hide in prose.

Tiers, outermost first. A tier may import from tiers below it; an import from a
tier above is an upward dependency and is reported individually.

Usage:
    python _scripts/layering.py              # all sections
    python _scripts/layering.py --section violations
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent / "_generated"

# Package granularity for the dependency graph. Longest prefix wins, so
# `idaes/core/util` is distinguished from `idaes/core`.
#
# No tier ORDER is asserted here. An invented ranking would decide the answer in
# advance; instead the graph is built from the measured imports and its cycles
# are reported. A cycle is an objective property of the code.
PACKAGES = [
    "idaes/core/base", "idaes/core/util", "idaes/core/scaling",
    "idaes/core/initialization", "idaes/core/solvers", "idaes/core/surrogate",
    "idaes/core/plugins", "idaes/core/dmf", "idaes/core/io", "idaes/core",
    "idaes/models/properties", "idaes/models/unit_models",
    "idaes/models/costing", "idaes/models/control", "idaes/models/flowsheets",
    "idaes/models", "idaes/models_extra/power_generation",
    "idaes/models_extra/column_models", "idaes/models_extra/gas_solid_contactors",
    "idaes/models_extra/temperature_swing_adsorption",
    "idaes/models_extra/gas_distribution",
    "idaes/models_extra/co2_capture_and_utilization", "idaes/models_extra",
    "idaes/apps/grid_integration", "idaes/apps/matopt", "idaes/apps/caprese",
    "idaes/apps/nmpc", "idaes/apps/uncertainty_propagation", "idaes/apps",
    "idaes/commands", "idaes",
]

STDLIB_HINT = {
    "os", "sys", "re", "json", "math", "copy", "enum", "types", "logging",
    "collections", "itertools", "functools", "typing", "abc", "io", "time",
    "pathlib", "importlib", "textwrap", "shutil", "subprocess", "platform",
    "random", "unittest", "inspect", "csv", "tempfile", "warnings", "numbers",
    "contextlib", "datetime", "string", "traceback", "ctypes", "xml", "gzip",
    "tarfile", "urllib", "hashlib", "pickle", "threading", "argparse", "glob",
    "operator", "struct", "weakref", "decimal", "fractions", "uuid", "shlex",
}


def package_of(path: str) -> str:
    """Longest-prefix package for a module path.

    The bare-prefix case matters: an import target that IS a package directory,
    such as `idaes/core/util`, has no trailing slash and no `.py`, so matching
    only `prefix + "/"` and `prefix + ".py"` attributed it to its PARENT. That
    silently moved 412 of 1,774 intra-idaes statements up one level and hid an
    edge that closes a cycle.
    """
    for prefix in PACKAGES:
        if path == prefix or path.startswith(prefix + "/") or path == prefix + ".py":
            return prefix
    return "idaes"


def load():
    rows = list(csv.DictReader((GEN / "imports.csv").open(encoding="utf-8")))
    ledger = {r["file"]: r["doc"]
              for r in csv.DictReader((GEN / "ledger.csv").open(encoding="utf-8"))}
    return rows, ledger


def resolve(row: dict) -> str | None:
    """Absolute module path of an import target, or None if not an idaes import."""
    mod = row["module"]
    level = int(row["level"] or 0)
    if level:
        parts = Path(row["file"]).parent.parts
        base = list(parts[: len(parts) - (level - 1)]) if level > 1 else list(parts)
        mod = "/".join(base) + ("/" + mod.replace(".", "/") if mod else "")
        return mod
    if mod.split(".")[0] != "idaes":
        return None
    return mod.replace(".", "/")


def build_graph(rows):
    edges = Counter()
    sites = defaultdict(list)
    for r in rows:
        target = resolve(r)
        if target is None:
            continue
        src, dst = package_of(r["file"]), package_of(target)
        if src != dst:
            edges[(src, dst)] += 1
            sites[(src, dst)].append((r["file"], r["line"], r["module"]))
    return edges, sites


def section_edges(rows, ledger):
    edges, _ = build_graph(rows)
    out = ["| From package | To package | Imports |", "|---|---|---:|"]
    for (s, d), n in sorted(edges.items(), key=lambda kv: -kv[1]):
        out.append(f"| `{s}` | `{d}` | {n} |")
    return "\n".join(out)


def section_cycles(rows, ledger):
    """Mutually dependent package pairs, and larger cycles, from the measured graph."""
    edges, sites = build_graph(rows)
    adj = defaultdict(set)
    for (s, d) in edges:
        adj[s].add(d)

    # Tarjan's strongly connected components, iterative.
    index, low, onstack, stack, order, sccs = {}, {}, set(), [], [], []
    counter = [0]
    for root in list(adj):
        if root in index:
            continue
        work = [(root, iter(adj[root]))]
        index[root] = low[root] = counter[0]; counter[0] += 1
        stack.append(root); onstack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]; counter[0] += 1
                    stack.append(nxt); onstack.add(nxt)
                    work.append((nxt, iter(adj[nxt])))
                    advanced = True
                    break
                if nxt in onstack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop(); onstack.discard(w); comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))

    out = []
    pairs = sorted({(s, d) for (s, d) in edges if (d, s) in edges and s < d})
    if pairs:
        out.append("**Mutually dependent package pairs**\n")
        out.append("| Package A | Package B | A imports B | B imports A |")
        out.append("|---|---|---:|---:|")
        for a, b in pairs:
            out.append(f"| `{a}` | `{b}` | {edges[(a, b)]} | {edges[(b, a)]} |")
    else:
        out.append("No mutually dependent package pairs.")

    out.append("\n**Strongly connected components larger than one package**\n")
    if sccs:
        for comp in sccs:
            out.append("- " + ", ".join(f"`{c}`" for c in comp))
    else:
        out.append("None.")
    return "\n".join(out)


def section_thirdparty(rows, ledger):
    per = defaultdict(Counter)
    for r in rows:
        top = r["module"].split(".")[0]
        if not top or top == "idaes" or int(r["level"] or 0):
            continue
        if top in STDLIB_HINT:
            continue
        per[top][package_of(r["file"])] += 1
    out = ["| Package | Import sites | Packages that use it |", "|---|---:|---|"]
    for pkg, tiers in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(tiers.values())
        where = ", ".join(f"`{t}` ({n})" for t, n in tiers.most_common())
        out.append(f"| `{pkg}` | {total} | {where} |")
    return "\n".join(out)


def section_pyomo(rows, ledger):
    per = Counter()
    for r in rows:
        if r["module"].split(".")[0] != "pyomo":
            continue
        per[".".join(r["module"].split(".")[:3])] += 1
    out = ["| Pyomo subpackage | Import sites |", "|---|---:|"]
    for mod, n in per.most_common():
        out.append(f"| `{mod}` | {n} |")
    return "\n".join(out)


SECTIONS = {
    "edges": section_edges,
    "cycles": section_cycles,
    "thirdparty": section_thirdparty,
    "pyomo": section_pyomo,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--section", choices=sorted(SECTIONS))
    args = ap.parse_args()
    rows, ledger = load()
    for name in ([args.section] if args.section else ["edges", "cycles", "thirdparty", "pyomo"]):
        print(f"<!-- section: {name} -->")
        print(SECTIONS[name](rows, ledger))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
