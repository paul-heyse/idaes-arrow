# `_generated/` — machine-derived inventories

Everything in this directory is **output**. Do not hand-edit it; regenerate with:

```bash
python docs-code-update/authoritative_design/_scripts/inventory.py
```

Pinned to `70a8f4fe1` (IDAES-PSE v2.13.0rc0). `manifest.json` records the SHA and
the generation timestamp for every run.

## Pinned revision versus the working tree

The document set describes the IDAES library at `70a8f4fe1`. The working tree
may carry commits on top of that revision which do not touch `idaes/` — fork
scaffolding, build tooling, or code outside the documented subtree. Every
inventory run compares the two and records the result in `manifest.json`:

| Field | Meaning |
|---|---|
| `sha` | The working tree's current HEAD |
| `documented_revision` | `70a8f4fe1`, the revision the documents describe |
| `head_matches_documented_revision` | Whether HEAD is that revision |
| `documented_subtree_changed_since_pin` | Files under `idaes/` that differ between the two; `[]` means none |

When `documented_subtree_changed_since_pin` is a non-empty list, anchors in the
document set may be stale and the run prints a warning to stderr. An empty list
means HEAD has moved but every anchor and count still holds.

## Two independent extractors

Every structural fact below is derived twice and the two results are asserted to
agree by `_scripts/crosscheck.py`:

| Extractor | Mechanism |
|---|---|
| `_scripts/inventory.py` | CPython's own `ast` module |
| `sgrules/*.yml` via `ast-grep scan` | tree-sitter structural rules |

| Fact | Value | Agreement |
|---|---:|---|
| `declare_process_block_class` classes | 160 | both |
| `CONFIG.declare` keys | 1,083 | both |
| `NotImplementedError` hooks | 159 | both |
| External library bindings | 26 | both |
| Deprecation sites | 49 | both |
| Enumeration classes | 74 | both |

The check earns its keep, twice over. It caught a defect in the Python
extractor, which counted a multi-line `@deprecated(...)` decorator twice — once
as a call at the decorator line and once as a decorator at the class line —
inflating the deprecation count from 49 to 53.

Enumerations were added to the pairing later, and the reason is instructive:
the enum count was the one structural fact *not* cross-checked, and it was the
one that was wrong. The Python extractor matched base classes by bare name, so
19 classes declared `class X(enum.Enum)` were missed and the count read 55
instead of 74. Both extractors now match the class definition rather than a base
name spelling.

## Why static analysis and not introspection

The inventory is produced by parsing the source with the standard-library `ast`
module. IDAES is never imported. Two reasons:

1. `idaes/__init__.py` has import-time side effects — it resolves and **creates**
   the data, binary and testing directories, mutates `PATH` and
   `LD_LIBRARY_PATH`, pre-registers three external function libraries in
   `AMPLFUNC`, and installs a logging filter. Importing to inspect would change
   the machine it runs on.
2. Much of the tree is guarded by `attempt_import` for optional dependencies
   (OMLT, TensorFlow, ONNX, CoolProp, Prescient, Egret, scikit-learn, mpi4py).
   Runtime introspection would silently report a different surface on every
   machine, which is exactly the non-reproducibility the document set exists to
   remove.

The cost is that dynamically generated names are not observed directly. The one
place this matters is `declare_process_block_class`, which synthesizes a
container class at import time and injects it into the decorated class's module.
`process_blocks.csv` records the synthesized name from the decorator argument, so
the generated surface is still captured.

## Files

| File | Rows | Content |
|---|---|---|
| `manifest.json` | — | Run metadata, SHA, headline counts, asset and pytest-marker histograms |
| `modules.csv` | 874 | Every tracked `.py` file: package, LOC, `source`/`test` role, class and function counts |
| `symbols.json` | 465 | Per source module: classes (bases, decorators, class attributes, methods with line ranges and signatures), module-level functions, `__all__` |
| `classes.csv` | 698 | Flat class roster with bases, decorators, generated block name, `default_initializer` / `default_scaler` |
| `process_blocks.csv` | 160 | Every `@declare_process_block_class` site: data class, synthesized container class, `block_class` override |
| `config_keys.csv` | 1083 | Every `CONFIG.declare(...)`: config object, enclosing class, key, value kind, domain, default, description |
| `hooks.csv` | 159 | Every `raise NotImplementedError` site — IDAES's de facto abstract-method mechanism |
| `retrofit.csv` | 160 | Per declared process block: whether it declares `default_initializer` / `default_scaler` |
| `enums.csv` | 74 | Enum / IntEnum / StrEnum subclasses with members and values |
| `imports.csv` | 3106 | Every import statement: form, module, imported names, relative level |
| `externals.csv` | 26 | `find_library`, `ExternalFunction`, `LoadLibrary`, `Executable` call sites |
| `deprecations.csv` | 49 | `deprecation_warning`, `relocated_module_attribute`, `@deprecated` sites with version and `remove_in` |
| `assets.csv` | 179 | Every tracked non-`.py` file under `idaes/` with extension and byte size |
| `markers.csv` | — | `@pytest.mark.*` occurrences per test file |

## Counts at `70a8f4fe1`

| Quantity | Value |
|---|---:|
| Tracked `.py` files | 874 |
| Source modules (tests and `conftest.py` excluded) | 465 |
| Source LOC | 215,226 |
| Test modules / test LOC | 409 / 212,886 |
| Source directories | 92 |
| Classes | 698 |
| Module-level functions | 964 |
| `@declare_process_block_class` classes | 160 |
| `CONFIG.declare(...)` keys | 1,083 |
| `raise NotImplementedError` hooks | 159 |
| Enum classes | 74 |
| External binding sites | 26 |
| Deprecation sites | 49 |
| Non-`.py` assets | 179 |

## Counting notes

Numbers here supersede any hand count. Two discrepancies worth recording,
because both are easy to reproduce incorrectly:

- A naive `grep -c 'raise NotImplementedError'` returns **161**. Two of those are
  commented out, at `idaes/models/properties/modular_properties/state_definitions/FpTPxpc.py:143`
  and `:380`. The true count is **159**.
- **46** classes in the tree are named `*Scaler`, but only **24** process block
  classes declare a `default_scaler` class attribute, and **23** declare a
  `default_initializer`. The three numbers answer different questions and must
  not be substituted for one another.
- A naive count of deprecation sites returns **53** if a multi-line
  `@deprecated(...)` decorator is counted both as a call and as a decorator. The
  true count is **49**.
- Matching enum base classes only by their bare name (`Enum`, `IntEnum`, …)
  returns **55**. Nineteen classes are declared with a dotted base such as
  `class EosType(enum.Enum)` and were missed. The true count is **74**.
