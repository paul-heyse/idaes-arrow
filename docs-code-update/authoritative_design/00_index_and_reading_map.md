# 00 — Index and reading map

> **Doc ID** 00 · **Repo SHA** 70a8f4fe1 (IDAES-PSE v2.13.0rc0) · **Source roots** none (front matter)
> **Owns** no source files · **Siblings** [01](01_glossary_and_conventions.md), [29](29_dependency_and_layering_map.md), [31](31_extension_point_catalog.md)

This is the manifest for a complete, verified architecture reference for
IDAES-PSE as it stands at commit `70a8f4fe1`. It records what each document
covers, assigns every source file and every shipped asset to exactly one owner,
and describes how the set is checked.

---

## 1. What this set is, and what it is not

It documents the library **as it is**. It is not a plan, a critique or a
proposal. Statements about the code are descriptive; the only evaluative
material appears in each document's section 12, as an observation with an anchor
and an observable consequence.

Two properties make the set usable as a reference rather than as prose:

**Every claim is anchored.** Non-obvious statements carry a
`` `idaes/path/file.py:LINE` `` citation next to the symbol they describe.
Anchors resolve against `70a8f4fe1`, not the working tree, so they stay correct
while the repository moves on.

**Every fact is counted, not estimated.** Each number comes from
`_generated/`, produced by static analysis of the pinned revision and
cross-checked by a second, independent extractor.

### 1.1 The pinned revision

The subject is the IDAES library at `70a8f4fe1`. The working tree may carry
commits on top of that which do not belong to the documented subject. The
tooling handles this rather than ignoring it: `inventory.py` enumerates and
reads files through `git ls-tree` and `git show` at the pin, `crosscheck.py`
exports that revision before scanning it, and `verify.py` resolves every anchor
against it. `manifest.json` records whether `idaes/` has drifted, and by how
much.

The practical consequence for a reader: a line number in this set is a line
number **at `70a8f4fe1`**. If the file has changed since, use
`git show 70a8f4fe1:<path>` to see what the anchor refers to.

---

## 2. The census

Measured at `70a8f4fe1`, tests excluded except where stated.

| Quantity | Value |
|---|---:|
| Source modules | 465 |
| Source lines of code | 215,226 |
| Test modules | 409 |
| Test lines of code | 212,886 |
| Source directories | 92 |
| Classes | 698 |
| Module-level functions | 964 |
| Process block classes | 160 |
| Configuration keys | 1,083 |
| Abstract hooks (`NotImplementedError`) | 159 |
| Enumerations | 74 |
| External library bindings | 26 |
| Deprecation sites | 49 |
| Shipped non-Python assets | 179 |

Three of these are easy to get wrong and are fixed here, with the reason:

| Quantity | Correct | A naive count gives | Why |
|---|---:|---:|---|
| `NotImplementedError` hooks | 159 | 161 | Two are commented out, at `idaes/models/properties/modular_properties/state_definitions/FpTPxpc.py:143` and `:380` |
| Deprecation sites | 49 | 53 | A multi-line `@deprecated(...)` counted both as a call and as a decorator |
| Process blocks declaring a Scaler | 24 | 46 | 46 is the number of classes *named* `*Scaler`, which is a different question |
| Enumerations | 74 | 55 | Nineteen are declared with a dotted base such as `enum.Enum` and are missed by matching the bare name |

---

## 3. The documents

Grouped by tier. Module and LOC counts are the files each document owns.
Thirty-three numbered documents produce thirty-four files: document 08 exceeded
the length cap and took the pre-approved split into `08a` and `08b`, keeping its
ledger number so existing cross-references still resolve.

| Doc | Title | Modules | LOC | Assets |
|---|---|---:|---:|---:|
| [00](00_index_and_reading_map.md) | Index and reading map | — | — | — |
| [01](01_glossary_and_conventions.md) | Glossary and conventions | — | — | — |
| [02](02_runtime_platform_and_cli.md) | Runtime platform and command line interface | 19 | 2,658 | — |
| [03](03_block_hierarchy_and_construction_protocol.md) | Block hierarchy and construction protocol | 7 | 2,371 | — |
| [04](04_control_volume_framework.md) | Control volume framework | 5 | 6,982 | — |
| [05](05_property_and_reaction_framework.md) | Property and reaction framework | 6 | 3,772 | — |
| [06](06_model_preparation_initializers_and_scalers.md) | Model preparation: Initializers and Scalers | 15 | 7,171 | — |
| [07](07_diagnostics_and_run_orchestration.md) | Diagnostics and run orchestration | 26 | 9,866 | — |
| [08a](08a_model_introspection_and_persistence.md) | Core utility library: model introspection and persistence | 5 | 4,128 | — |
| [08b](08b_core_support_utilities.md) | Core utility library: support utilities, plug-ins and the deprecated-surface register | 20 | 4,858 | — |
| [09](09_surrogate_subsystem.md) | Surrogate subsystem | 21 | 10,275 | — |
| [10](10_unit_models_control_volume_based.md) | Unit models: control-volume based | 18 | 9,141 | — |
| [11](11_unit_models_network_contactors_and_control.md) | Unit models: network, contactors and control | 14 | 8,264 | 32 |
| [12](12_modular_properties_generic_framework.md) | Modular properties: the generic framework | 4 | 7,436 | — |
| [13](13_modular_properties_eos_and_phase_equilibrium.md) | Modular properties: equations of state and phase equilibrium | 20 | 6,793 | — |
| [14](14_modular_properties_state_definitions_and_libraries.md) | Modular properties: state definitions and correlation libraries | 23 | 5,898 | — |
| [15](15_property_package_catalog.md) | Property package catalog | 26 | 8,312 | — |
| [16](16_general_helmholtz_property_system.md) | General Helmholtz property system | 36 | 9,228 | 54 |
| [17](17_costing_framework_and_libraries.md) | Costing framework and libraries | 11 | 11,618 | 6 |
| [18](18_power_generation_boiler_island.md) | Power generation: boiler island | 13 | 11,626 | 5 |
| [19](19_power_generation_heat_exchangers_and_properties.md) | Power generation: heat exchangers and properties | 10 | 6,435 | — |
| [20](20_power_generation_helmholtz_units_and_soc.md) | Power generation: Helmholtz units and solid oxide cells | 24 | 10,646 | — |
| [21](21_column_models_and_solvent_systems.md) | Column models and solvent systems | 15 | 10,081 | — |
| [22](22_gas_solid_contactors.md) | Gas-solid contactors | 15 | 13,939 | — |
| [23](23_tsa_gas_distribution_and_ccu.md) | Temperature swing adsorption, gas distribution and CCU | 15 | 6,320 | 1 |
| [24](24_reference_flowsheets_and_demonstrations.md) | Reference flowsheets and demonstrations | 22 | 11,031 | 3 |
| [25](25_grid_integration.md) | Grid integration | 18 | 8,673 | — |
| [26](26_matopt.md) | MatOpt | 28 | 10,167 | 1 |
| [27](27_dynamic_optimization_and_uncertainty.md) | Dynamic optimization and uncertainty | 22 | 5,732 | 4 |
| [28](28_data_and_file_format_inventory.md) | Data and file format inventory | — | — | — |
| [29](29_dependency_and_layering_map.md) | Dependency and layering map | — | — | — |
| [30](30_numerics_and_solver_interface_map.md) | Numerics and solver interface map | 7 | 1,805 | — |
| [31](31_extension_point_catalog.md) | Extension point catalog | — | — | — |
| [32](32_repository_engineering.md) | Repository engineering | — | — | — |
| | **Total** | **465** | **215,226** | **106** |

---

## 4. Reading paths

The set is not meant to be read front to back. Five paths through it:

**Understanding how a model is built.** [01](01_glossary_and_conventions.md)
for the vocabulary, then [03](03_block_hierarchy_and_construction_protocol.md)
for the block protocol, [04](04_control_volume_framework.md) for the balance
equations and [05](05_property_and_reaction_framework.md) for the property
contract. Those four are the spine; every other document assumes them.

**Adding a new model.** [31](31_extension_point_catalog.md) first — it ends with
worked checklists for adding a unit model, a property package, a costing package
or a solver. Then the owning document for whichever seam you are filling.

**Understanding a specific subsystem.** Find it in section 3 and read that
document alone. Each one is self-contained: its section 0 lists exactly the
files it covers, and anything outside that scope is a cross-reference rather
than a restatement.

**Auditing the numerics.** [30](30_numerics_and_solver_interface_map.md) for the
solver interface, the external libraries and the availability gates;
[06](06_model_preparation_initializers_and_scalers.md) for initialization and
both scaling generations; [07](07_diagnostics_and_run_orchestration.md) for the
diagnostic tooling.

**Auditing the data.** [28](28_data_and_file_format_inventory.md) for every
shipped and runtime file format, [29](29_dependency_and_layering_map.md) for the
dependency graph and the duplication register.

---

## 5. The ownership ledger

Every source file and every shipped asset is assigned to **exactly one**
document. That document carries the normative description; every other document
links to it rather than restating it. The assignment lives in
`_generated/ledger.csv`, generated from ordered path rules in
`_scripts/ledger.py` so it cannot drift from a hand-maintained list.

Totality and disjointness are checked, not asserted:
`verify.py --only ledger` fails if any tracked path is unassigned or assigned
twice. At `70a8f4fe1` the ledger covers **465 source modules and 179 assets with
zero unassigned and zero duplicated**.

Four documents own no source files. They are **index documents** and obey a
stricter rule: each row points at an owning document and states a single fact,
and they do not restate semantics that another document carries.

| Document | Indexes |
|---|---|
| [28](28_data_and_file_format_inventory.md) | Every shipped asset and every runtime file format |
| [29](29_dependency_and_layering_map.md) | The package import graph, its cycles, and the duplication register |
| [30](30_numerics_and_solver_interface_map.md) | Numerics across the tree — though it also *owns* `idaes/core/solvers` |
| [31](31_extension_point_catalog.md) | Every extension seam in the library |

### 5.1 Assets by format

| Extension | Count | Owning documents |
|---|---:|---|
| `.json` | 45 | 16, 17, 32 |
| `.csv` | 40 | 27, 32 |
| `.svg` | 39 | 11, 18, 24 |
| `.nl` | 32 | 16 |
| `.keras` | 5 | 32 |
| `.md` | 4 | 18, 23, 26, 27 |
| `.h5` | 4 | 32 |
| `.txt` | 3 | 32 |
| `.trc` | 3 | 32 |
| `.ipynb` | 2 | 27 |
| `.alm` | 1 | 32 |
| `.onnx` | 1 | 32 |

---

## 6. How the set is checked

`_scripts/verify.py` runs twelve mechanical checks. They catch missing coverage
and stale anchors; they cannot catch prose that is wrong about code it cites
correctly, which is what the spot audit in section 6.2 is for.

| Check | What it proves |
|---|---|
| `counts` | The headline counts in section 2 match the generated data |
| `anchors` | Every `file.py:LINE` citation exists and is in range **at the pinned revision** |
| `ledger` | Every tracked source file and asset is owned by exactly one document |
| `config` | Every one of the 1,083 configuration keys appears verbatim in the document owning its module |
| `hooks` | Every one of the 159 abstract hooks appears in its owning document and in [31](31_extension_point_catalog.md) |
| `assets` | Every shipped asset appears in [28](28_data_and_file_format_inventory.md) |
| `xrefs` | Every cross-reference resolves to an existing document and heading, and is reciprocated |
| `language` | No forward-looking or filler language outside explicit exempt regions |
| `size` | Each document is within its length bounds |
| `diagrams` | At most six diagrams per document, fences balanced |
| `template` | Every content document carries all sixteen template sections |
| `header` | Every document pins the documented revision |

Run them all with:

```bash
python docs-code-update/authoritative_design/_scripts/verify.py
```

### 6.1 Two independent extractors

Structural facts are derived twice and asserted to agree, by
`_scripts/crosscheck.py`:

| Extractor | Mechanism |
|---|---|
| `_scripts/inventory.py` | CPython's own `ast` module |
| `sgrules/*.yml` via `ast-grep scan` | tree-sitter structural rules |

Both report 160 process block classes, 1,083 configuration keys, 159 hooks, 26
external library bindings, 49 deprecation sites and 74 enumerations.

The check earns its place twice. It caught the deprecation double-count recorded
in section 2. And enumerations were added to the pairing only after the fact —
the enum count was the one structural fact not covered by it, and it was the one
that was wrong, reading 55 because base classes were matched by bare name and 19
classes are declared `class X(enum.Enum)`. The `counts` check in section 6 now
guards the numbers in this document against the same failure.

### 6.2 The check no script can do

`_scripts/spot_audit.py` samples claim-bearing anchors and prints each claim
beside the source line it cites, for a human to read. Automated checks prove an
anchor resolves; only reading proves it supports the sentence next to it.

```bash
python docs-code-update/authoritative_design/_scripts/spot_audit.py --doc 04 -n 10
```

---

## 7. Regenerating everything

```bash
# Re-derive the census from the pinned revision
python docs-code-update/authoritative_design/_scripts/inventory.py

# Re-derive the ownership ledger
python docs-code-update/authoritative_design/_scripts/ledger.py

# Assert the two extractors still agree
python docs-code-update/authoritative_design/_scripts/crosscheck.py

# Re-derive this document's tables
python docs-code-update/authoritative_design/_scripts/make_index_tables.py

# Check the whole set
python docs-code-update/authoritative_design/_scripts/verify.py
```

`_generated/README.md` documents every generated file and explains why the
tooling never imports IDAES: `idaes/__init__.py` creates directories, mutates
`PATH` and `LD_LIBRARY_PATH`, and pre-registers external function libraries at
import time, and optional dependencies would make the result differ per machine.

---

## 8. Conventions

Defined in full in [01](01_glossary_and_conventions.md): the controlled
vocabulary and its term-collision table, the anchor format, when a diagram is
permitted, the shape of configuration and class-roster tables, the
cross-referencing rule, and the language rules. Section 9 of that document
specifies the sixteen-section template every content document follows.

The one convention worth stating here, because it confuses every reader once:
**every IDAES modelling type exists as a pair of classes.** The developer writes
`FooData`; the `declare_process_block_class` decorator synthesizes `Foo` and
injects it into the same module. 160 such pairs exist. See
[03 §3](03_block_hierarchy_and_construction_protocol.md#3-class-hierarchy-and-type-taxonomy).
