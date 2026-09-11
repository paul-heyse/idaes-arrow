#!/usr/bin/env python3
"""
Machine inventory of the IDAES-PSE source tree.

Derives every fact the authoritative_design document set needs to count, so that
no document hand-counts anything.  Uses only the standard library plus
``git ls-files``; IDAES itself is never imported.  ``idaes/__init__.py`` has
import-time side effects (creates directories, mutates PATH / LD_LIBRARY_PATH,
pre-registers AMPLFUNC external function libraries) and pyomo is not guaranteed
to be installed, so static analysis is the only reproducible option.

Usage:
    python _scripts/inventory.py [--repo REPO_ROOT] [--out OUT_DIR]

Writes to OUT_DIR (default ``_generated``):
    manifest.json        run metadata, SHA, headline counts
    modules.csv          every tracked .py file with LOC and role
    symbols.json         classes / functions / methods with line numbers
    classes.csv          flat class roster with bases and decorators
    process_blocks.csv   @declare_process_block_class sites
    config_keys.csv      every CONFIG.declare(...) call
    hooks.csv            every `raise NotImplementedError` site
    retrofit.csv         default_initializer / default_scaler adoption
    enums.csv            Enum / IntEnum / StrEnum subclasses and members
    imports.csv          module -> imported module edges
    externals.csv        find_library / ExternalFunction / AMPLFUNC sites
    deprecations.csv     deprecation_warning / @deprecated / relocated_module_attribute
    assets.csv           every tracked non-.py file under idaes/
    markers.csv          pytest markers per test file
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def tracked_files(repo: Path, pattern: str) -> list[str]:
    out = git(repo, "ls-files", pattern)
    return [line for line in out.splitlines() if line]


def is_test_path(path: str) -> bool:
    return "/tests/" in path or path.endswith("/conftest.py") or path == "idaes/conftest.py"


def unparse(node) -> str:
    """ast.unparse with a short, table-safe rendering."""
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:  # pragma: no cover - defensive
        return "<unparseable>"
    text = " ".join(text.split())
    return text if len(text) <= 160 else text[:157] + "..."


def const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def qualname(stack: list[str], name: str) -> str:
    return ".".join([*stack, name]) if stack else name


# --------------------------------------------------------------------------
# AST walker
# --------------------------------------------------------------------------


class ModuleScan:
    """Collects every fact of interest from one parsed module."""

    def __init__(self, relpath: str, source: str, tree: ast.Module):
        self.relpath = relpath
        self.lines = source.splitlines()
        self.tree = tree
        self.docstring = ast.get_docstring(tree) or ""
        self.classes: list[dict] = []
        self.functions: list[dict] = []
        self.process_blocks: list[dict] = []
        self.config_keys: list[dict] = []
        self.hooks: list[dict] = []
        self.enums: list[dict] = []
        self.imports: list[dict] = []
        self.externals: list[dict] = []
        self.deprecations: list[dict] = []
        self.dunder_all: list[str] = []
        self._scope: list[str] = []

    # -- entry point ------------------------------------------------------

    def run(self) -> "ModuleScan":
        self._visit_body(self.tree.body, parent_class=None)
        self._scan_calls()
        self._scan_imports()
        return self

    # -- structural walk --------------------------------------------------

    def _visit_body(self, body, parent_class: dict | None) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                self._visit_class(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(node, parent_class)
            elif isinstance(node, ast.Assign):
                self._visit_assign(node, parent_class)
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                # module-level conditionals still contain real definitions
                for sub in ast.iter_child_nodes(node):
                    if isinstance(sub, list):  # pragma: no cover
                        continue
                nested = []
                for field in ("body", "orelse", "finalbody"):
                    nested.extend(getattr(node, field, []) or [])
                for handler in getattr(node, "handlers", []) or []:
                    nested.extend(handler.body)
                self._visit_body(nested, parent_class)

    def _visit_class(self, node: ast.ClassDef) -> None:
        bases = [unparse(b) for b in node.bases]
        decorators = [unparse(d) for d in node.decorator_list]
        record = {
            "file": self.relpath,
            "line": node.lineno,
            "qualname": qualname(self._scope, node.name),
            "name": node.name,
            "bases": bases,
            "decorators": decorators,
            "docstring": bool(ast.get_docstring(node)),
            "methods": [],
            "class_attrs": {},
            "generated_block": "",
        }
        self.classes.append(record)

        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and unparse(dec.func).endswith(
                "declare_process_block_class"
            ):
                generated = const_str(dec.args[0]) if dec.args else ""
                block_class = ""
                for kw in dec.keywords:
                    if kw.arg == "block_class":
                        block_class = unparse(kw.value)
                record["generated_block"] = generated or ""
                self.process_blocks.append(
                    {
                        "file": self.relpath,
                        "line": node.lineno,
                        "data_class": node.name,
                        "generated_class": generated or "",
                        "block_class": block_class,
                        "bases": ";".join(bases),
                    }
                )

        for base in bases:
            if base in ("Enum", "IntEnum", "StrEnum", "str, Enum", "Flag", "IntFlag"):
                members = [
                    (t.id, unparse(stmt.value))
                    for stmt in node.body
                    if isinstance(stmt, ast.Assign)
                    for t in stmt.targets
                    if isinstance(t, ast.Name)
                ]
                self.enums.append(
                    {
                        "file": self.relpath,
                        "line": node.lineno,
                        "name": node.name,
                        "base": base,
                        "members": ";".join(f"{k}={v}" for k, v in members),
                        "n_members": len(members),
                    }
                )

        self._scope.append(node.name)
        self._visit_body(node.body, parent_class=record)
        self._scope.pop()

    def _visit_function(self, node, parent_class: dict | None) -> None:
        args = unparse(node.args)
        record = {
            "file": self.relpath,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "qualname": qualname(self._scope, node.name),
            "name": node.name,
            "signature": f"({args})",
            "decorators": [unparse(d) for d in node.decorator_list],
            "docstring": bool(ast.get_docstring(node)),
            "is_method": parent_class is not None,
        }
        if parent_class is not None:
            parent_class["methods"].append(record)
        else:
            self.functions.append(record)

        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise) and sub.exc is not None:
                exc = unparse(sub.exc)
                if exc.startswith("NotImplementedError"):
                    self.hooks.append(
                        {
                            "file": self.relpath,
                            "line": sub.lineno,
                            "owner": qualname(self._scope, node.name),
                            "method": node.name,
                            "class": parent_class["name"] if parent_class else "",
                            "message": exc,
                        }
                    )

    def _visit_assign(self, node: ast.Assign, parent_class: dict | None) -> None:
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "__all__" and parent_class is None:
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    self.dunder_all = [
                        v for v in (const_str(e) for e in node.value.elts) if v
                    ]
            if parent_class is not None:
                parent_class["class_attrs"][target.id] = unparse(node.value)

    # -- call-level scans -------------------------------------------------

    def _scan_calls(self) -> None:
        class_by_line = sorted(
            ((c["line"], c["name"]) for c in self.classes), key=lambda t: t[0]
        )

        def enclosing_class(line: int) -> str:
            name = ""
            for cline, cname in class_by_line:
                if cline <= line:
                    name = cname
                else:
                    break
            return name

        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = unparse(node.func)

            # CONFIG.declare("key", ConfigValue(...))
            if func.endswith(".declare") and node.args:
                key = const_str(node.args[0])
                if key is not None:
                    domain = default = description = ""
                    kind = ""
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Call):
                        inner = node.args[1]
                        kind = unparse(inner.func)
                        for kw in inner.keywords:
                            if kw.arg == "domain":
                                domain = unparse(kw.value)
                            elif kw.arg == "default":
                                default = unparse(kw.value)
                            elif kw.arg == "description":
                                description = const_str(kw.value) or unparse(kw.value)
                    self.config_keys.append(
                        {
                            "file": self.relpath,
                            "line": node.lineno,
                            "config_object": func[: -len(".declare")],
                            "enclosing_class": enclosing_class(node.lineno),
                            "key": key,
                            "value_kind": kind,
                            "domain": domain,
                            "default": default,
                            "description": " ".join(description.split())[:200],
                        }
                    )

            # external library / external function bindings
            short = func.rsplit(".", 1)[-1]
            if short in (
                "find_library",
                "ExternalFunction",
                "LoadLibrary",
                "cdll",
                "Executable",
            ):
                self.externals.append(
                    {
                        "file": self.relpath,
                        "line": node.lineno,
                        "kind": short,
                        "call": unparse(node),
                    }
                )

            # deprecation surface
            if short in (
                "deprecation_warning",
                "relocated_module_attribute",
                "deprecated",
                "in_testing_environment",
            ) and short != "in_testing_environment":
                version = remove_in = msg = ""
                for kw in node.keywords:
                    if kw.arg == "version":
                        version = const_str(kw.value) or unparse(kw.value)
                    elif kw.arg == "remove_in":
                        remove_in = const_str(kw.value) or unparse(kw.value)
                    elif kw.arg in ("msg", "message"):
                        msg = const_str(kw.value) or unparse(kw.value)
                if not msg and node.args:
                    msg = const_str(node.args[0]) or unparse(node.args[0])
                self.deprecations.append(
                    {
                        "file": self.relpath,
                        "line": node.lineno,
                        "kind": short,
                        "version": version,
                        "remove_in": remove_in,
                        "message": " ".join(msg.split())[:200],
                    }
                )

        # Bare `@deprecated` decorators only. The call form `@deprecated(...)` is
        # already captured by the call scan above, at the decorator's own line;
        # recording it a second time against the class line double-counts it.
        for cls in self.classes:
            for dec in cls["decorators"]:
                bare = dec.split(".")[-1]
                if bare == "deprecated":
                    self.deprecations.append(
                        {
                            "file": self.relpath,
                            "line": cls["line"],
                            "kind": "decorator",
                            "version": "",
                            "remove_in": "",
                            "message": f"{cls['name']}: {dec}",
                        }
                    )

    def _scan_imports(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(
                        {
                            "file": self.relpath,
                            "line": node.lineno,
                            "form": "import",
                            "module": alias.name,
                            "names": "",
                            "level": 0,
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                self.imports.append(
                    {
                        "file": self.relpath,
                        "line": node.lineno,
                        "form": "from",
                        "module": node.module or "",
                        "names": ";".join(a.name for a in node.names),
                        "level": node.level or 0,
                    }
                )


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


MARKER_RE = re.compile(r"@pytest\.mark\.([A-Za-z_][A-Za-z0-9_]*)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument(
        "--out", default=str(Path(__file__).resolve().parents[1] / "_generated")
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    sha = git(repo, "rev-parse", "HEAD")
    short_sha = git(repo, "rev-parse", "--short", "HEAD")

    py_files = [p for p in tracked_files(repo, "idaes/*") if p.endswith(".py")]
    non_py = [p for p in tracked_files(repo, "idaes/*") if not p.endswith(".py")]

    modules: list[dict] = []
    all_classes: list[dict] = []
    all_functions: list[dict] = []
    process_blocks: list[dict] = []
    config_keys: list[dict] = []
    hooks: list[dict] = []
    enums: list[dict] = []
    imports: list[dict] = []
    externals: list[dict] = []
    deprecations: list[dict] = []
    markers: list[dict] = []
    symbols: dict[str, dict] = {}
    parse_failures: list[str] = []

    for rel in sorted(py_files):
        abs_path = repo / rel
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        loc = source.count("\n") + (0 if source.endswith("\n") or not source else 1)
        test = is_test_path(rel)

        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            parse_failures.append(f"{rel}: {exc}")
            modules.append(
                {
                    "file": rel,
                    "package": str(Path(rel).parent),
                    "loc": loc,
                    "role": "test" if test else "source",
                    "n_classes": 0,
                    "n_functions": 0,
                    "has_docstring": False,
                    "parse_error": True,
                }
            )
            continue

        scan = ModuleScan(rel, source, tree).run()

        modules.append(
            {
                "file": rel,
                "package": str(Path(rel).parent),
                "loc": loc,
                "role": "test" if test else "source",
                "n_classes": len(scan.classes),
                "n_functions": len(scan.functions),
                "has_docstring": bool(scan.docstring),
                "parse_error": False,
            }
        )

        if test:
            found = Counter(MARKER_RE.findall(source))
            for marker, count in sorted(found.items()):
                markers.append({"file": rel, "marker": marker, "count": count})
            continue

        symbols[rel] = {
            "loc": loc,
            "docstring": scan.docstring.strip().splitlines()[0] if scan.docstring else "",
            "dunder_all": scan.dunder_all,
            "classes": [
                {
                    "name": c["name"],
                    "qualname": c["qualname"],
                    "line": c["line"],
                    "bases": c["bases"],
                    "decorators": c["decorators"],
                    "generated_block": c["generated_block"],
                    "class_attrs": c["class_attrs"],
                    "methods": [
                        {
                            "name": m["name"],
                            "line": m["line"],
                            "end_line": m["end_line"],
                            "signature": m["signature"],
                            "decorators": m["decorators"],
                            "docstring": m["docstring"],
                        }
                        for m in c["methods"]
                    ],
                }
                for c in scan.classes
            ],
            "functions": [
                {
                    "name": f["name"],
                    "line": f["line"],
                    "end_line": f["end_line"],
                    "signature": f["signature"],
                    "decorators": f["decorators"],
                    "docstring": f["docstring"],
                }
                for f in scan.functions
            ],
        }

        for c in scan.classes:
            all_classes.append(
                {
                    "file": rel,
                    "line": c["line"],
                    "name": c["name"],
                    "qualname": c["qualname"],
                    "bases": ";".join(c["bases"]),
                    "decorators": ";".join(c["decorators"]),
                    "generated_block": c["generated_block"],
                    "n_methods": len(c["methods"]),
                    "default_initializer": c["class_attrs"].get("default_initializer", ""),
                    "default_scaler": c["class_attrs"].get("default_scaler", ""),
                }
            )
        all_functions.extend(scan.functions)
        process_blocks.extend(scan.process_blocks)
        config_keys.extend(scan.config_keys)
        hooks.extend(scan.hooks)
        enums.extend(scan.enums)
        imports.extend(scan.imports)
        externals.extend(scan.externals)
        deprecations.extend(scan.deprecations)

    # ---- retrofit adoption (declared process blocks only) ----------------
    class_index = {(c["file"], c["name"]): c for c in all_classes}
    retrofit: list[dict] = []
    for pb in process_blocks:
        cls = class_index.get((pb["file"], pb["data_class"]), {})
        retrofit.append(
            {
                "file": pb["file"],
                "line": pb["line"],
                "data_class": pb["data_class"],
                "generated_class": pb["generated_class"],
                "bases": pb["bases"],
                "default_initializer": cls.get("default_initializer", ""),
                "default_scaler": cls.get("default_scaler", ""),
                "declares_initializer": bool(cls.get("default_initializer")),
                "declares_scaler": bool(cls.get("default_scaler")),
            }
        )

    # ---- assets ----------------------------------------------------------
    assets: list[dict] = []
    for rel in sorted(non_py):
        p = repo / rel
        assets.append(
            {
                "file": rel,
                "package": str(Path(rel).parent),
                "ext": Path(rel).suffix.lstrip(".") or "(none)",
                "bytes": p.stat().st_size if p.exists() else 0,
                "in_tests": "/tests/" in rel,
            }
        )

    # ---- write -----------------------------------------------------------
    write_csv(
        out / "modules.csv",
        modules,
        ["file", "package", "loc", "role", "n_classes", "n_functions", "has_docstring", "parse_error"],
    )
    write_csv(
        out / "classes.csv",
        all_classes,
        ["file", "line", "name", "qualname", "bases", "decorators", "generated_block",
         "n_methods", "default_initializer", "default_scaler"],
    )
    write_csv(
        out / "process_blocks.csv",
        process_blocks,
        ["file", "line", "data_class", "generated_class", "block_class", "bases"],
    )
    write_csv(
        out / "config_keys.csv",
        config_keys,
        ["file", "line", "config_object", "enclosing_class", "key", "value_kind",
         "domain", "default", "description"],
    )
    write_csv(out / "hooks.csv", hooks, ["file", "line", "class", "method", "owner", "message"])
    write_csv(
        out / "retrofit.csv",
        retrofit,
        ["file", "line", "data_class", "generated_class", "bases", "default_initializer",
         "default_scaler", "declares_initializer", "declares_scaler"],
    )
    write_csv(out / "enums.csv", enums, ["file", "line", "name", "base", "n_members", "members"])
    write_csv(out / "imports.csv", imports, ["file", "line", "form", "module", "names", "level"])
    write_csv(out / "externals.csv", externals, ["file", "line", "kind", "call"])
    write_csv(
        out / "deprecations.csv",
        deprecations,
        ["file", "line", "kind", "version", "remove_in", "message"],
    )
    write_csv(out / "assets.csv", assets, ["file", "package", "ext", "bytes", "in_tests"])
    write_csv(out / "markers.csv", markers, ["file", "marker", "count"])

    (out / "symbols.json").write_text(
        json.dumps(symbols, indent=1, sort_keys=True), encoding="utf-8"
    )

    source_modules = [m for m in modules if m["role"] == "source"]
    test_modules = [m for m in modules if m["role"] == "test"]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": str(repo),
        "sha": sha,
        "short_sha": short_sha,
        "tool": "docs-code-update/authoritative_design/_scripts/inventory.py",
        "method": "static ast parse; idaes is never imported",
        "counts": {
            "py_files_tracked": len(py_files),
            "source_modules": len(source_modules),
            "test_modules": len(test_modules),
            "source_loc": sum(m["loc"] for m in source_modules),
            "test_loc": sum(m["loc"] for m in test_modules),
            "source_dirs": len({m["package"] for m in source_modules}),
            "classes": len(all_classes),
            "module_level_functions": len(all_functions),
            "process_block_classes": len(process_blocks),
            "config_keys": len(config_keys),
            "not_implemented_hooks": len(hooks),
            "enums": len(enums),
            "import_statements": len(imports),
            "external_binding_sites": len(externals),
            "deprecation_sites": len(deprecations),
            "assets": len(assets),
            "parse_failures": len(parse_failures),
        },
        "asset_ext_histogram": dict(
            sorted(Counter(a["ext"] for a in assets).items(), key=lambda kv: -kv[1])
        ),
        "marker_histogram": dict(
            sorted(
                Counter(
                    {m["marker"]: 0 for m in markers}
                ).items()
            )
        ),
        "parse_failures": parse_failures,
    }
    marker_totals = Counter()
    for m in markers:
        marker_totals[m["marker"]] += m["count"]
    manifest["marker_histogram"] = dict(
        sorted(marker_totals.items(), key=lambda kv: -kv[1])
    )

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(json.dumps(manifest["counts"], indent=2))
    if parse_failures:
        print("PARSE FAILURES:", file=sys.stderr)
        for f in parse_failures:
            print("  " + f, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
