# 01 — Glossary and conventions

> **Doc ID** 01 · **Repo SHA** 70a8f4fe1 (IDAES-PSE v2.13.0rc0) · **Source roots** none (front matter)
> **Owns** no source files · **Siblings** [00](00_index_and_reading_map.md), [03](03_block_hierarchy_and_construction_protocol.md), [31](31_extension_point_catalog.md)

This document fixes the vocabulary and the presentation rules for the whole set.
Every other document uses the terms defined here verbatim and follows the
conventions in sections 4–8. Where a term in this codebase has more than one
meaning — and most of the important ones do — section 3 records every sense and
names the one spelling each document uses.

---

## 1. How to read a term definition

Each entry gives the term, the construct it names in the source, an anchor, and
the one phrasing the document set uses. Anchors are repository-root-relative and
pinned to `70a8f4fe1`; see section 4.

---

## 2. Core vocabulary

### 2.1 The block system

**Process block.** An IDAES modelling object built on Pyomo's `Block`. Every
process block exists as a **pair** of classes: a *data class* that carries the
behaviour, and a *container class* that Pyomo instantiates. The container is not
written by hand — `declare_process_block_class` synthesizes it and injects it
into the data class's own module (`idaes/core/base/process_block.py:176`). The
naming rule throughout IDAES is that the data class is `FooData` and the
synthesized container is `Foo`. There are 160 such pairs in the tree.

**Data class / container class.** `FooData` subclasses `ProcessBlockData`
(itself a Pyomo `BlockData`, `idaes/core/base/process_base.py:78`) and defines
`CONFIG` and `build()`. `Foo` subclasses `ProcessBlock`
(`idaes/core/base/process_block.py:141`), which dispatches in `__new__` to a
scalar or indexed subclass created by `_ScalarProcessBlockMeta`
(`idaes/core/base/process_block.py:123`) or `_IndexedProcessBlockMeta`
(`idaes/core/base/process_block.py:106`). Documents always name both halves of
the pair on first mention and never re-explain the rule.

**Build.** The construction step that creates Pyomo components on a block.
Pyomo calls it through the default rule `_rule_default`
(`idaes/core/base/process_block.py:35`), which calls `b.build()`. A document
that says "at build time" means inside this call.

**CONFIG block.** A Pyomo `ConfigBlock`/`ConfigDict` declared as a class
attribute on a data class and extended by subclasses through `CONFIG.declare`.
There are 1,083 declared keys in the tree. Resolution of the user's keyword
arguments into `self.config` happens in `_get_config_args`
(`idaes/core/base/process_base.py:232`).

**`useDefault`.** A module-level sentinel object
(`idaes/core/base/process_base.py:59`) used as a CONFIG default meaning "resolve
this by walking up the block hierarchy at build time" rather than "use this
value". It is not `None`, and the distinction matters: `None` is a legitimate
configured value in several places.

**Flowsheet.** A `FlowsheetBlockData`/`FlowsheetBlock` pair
(`idaes/core/base/flowsheet_model.py:99`) that owns the time domain and acts as
the container for unit models. A block identifies itself as a flowsheet by
returning `True` from `is_flowsheet()`
(`idaes/core/base/flowsheet_model.py:202`); the upward search in
`ProcessBlockData.flowsheet()` uses exactly this test.

**Unit model.** A `UnitModelBlockData`/`UnitModelBlock` pair
(`idaes/core/base/unit_model.py:54`) representing one piece of process
equipment. Unit models own ports and usually one or more control volumes.

**Control volume.** The reusable balance-equation engine. A control volume owns
the state blocks, the reaction blocks, and the material, energy and momentum
balance constraints. Two geometries exist: zero-dimensional (`ControlVolume0D`)
and one-dimensional (`ControlVolume1D`). See
[04](04_control_volume_framework.md).

**Port.** A Pyomo `Port` carrying the state variables that connect two unit
models. Ports are built from a state block by `StateBlock.build_port`
(`idaes/core/base/property_base.py:488`) and attached by `add_port`
(`idaes/core/base/unit_model.py:141`) and its inlet/outlet wrappers.

**Arc.** A Pyomo `Arc` (from `pyomo.network`) connecting two ports. IDAES does
not define its own connector type; arcs are expanded by Pyomo's
`expand_arcs` transformation.

### 2.2 The property system

**Property package.** The pairing of a parameter block and a state block class
that together supply thermophysical properties to a control volume. The term
covers both hand-written packages and configurations of the modular framework.

**Parameter block.** A `PhysicalParameterBlock`
(`idaes/core/base/property_base.py:77`) holding component and phase definitions,
metadata, and numeric parameters shared by every state block built from it.
The reaction-side equivalent is `ReactionParameterBlock`.

**State block.** A `StateBlockData`/`StateBlock` pair
(`idaes/core/base/property_base.py:535` and `:267`) representing the
thermodynamic state at one point in the model, indexed by time (0-D) or by time
and length (1-D). A state block is what a port exposes and what a balance
equation queries.

**On-demand property construction.** The mechanism by which a state block
creates a property only when something asks for it.
`StateBlockData.__getattr__` (`idaes/core/base/property_base.py:816`) falls
through to `build_on_demand` (`idaes/core/base/util.py:28`), which looks the
name up in the package metadata and calls the registered build method. Documents
say "built on demand", never "lazy" or "deferred".

**Property metadata.** The declaration, per package, of which properties are
supported, which method builds each one, and what units the package works in.
Held by `PropertyClassMetadata` and the `PropertySet` taxonomy; see
[05](05_property_and_reaction_framework.md).

**True vs apparent species.** In electrolyte systems, *true* species are the
dissociated ions actually present; *apparent* species are the undissociated
salts a user supplies. The choice of which set indexes the state variables is a
configuration key, not an inference.

### 2.3 Preparation and solution

**Initializer object.** An instance of an `InitializerBase` subclass from
`idaes/core/initialization/`, implementing a fixed multi-step routine. 23 of the
160 declared process block classes name one in a `default_initializer` class
attribute (for example `idaes/core/base/unit_model.py:61`).

**Legacy initialization routine.** The older `initialize()` method defined
directly on a unit model or control volume. It coexists with Initializer
objects; neither has displaced the other. See
[06](06_model_preparation_initializers_and_scalers.md).

**Scaler object.** An instance of a `CustomScalerBase` subclass from
`idaes/core/scaling/`. 24 declared process block classes name one in a
`default_scaler` class attribute. Distinct from a **scaling factor**, which is a
numeric value stored in a Pyomo `Suffix`.

**Suffix-based scaling** and **Scaler-based scaling.** The two scaling
generations present in the tree. The suffix-based API is
`idaes/core/util/scaling.py`; the Scaler-based API is `idaes/core/scaling/`.
Documents use these two names and never call either one "the" scaling API.

**Solver.** A Pyomo solver object obtained through `get_solver`
(`idaes/core/solvers/get_solver.py`). IDAES injects its own configured defaults
by re-registering solvers in the Pyomo `SolverFactory`; see
[30](30_numerics_and_solver_interface_map.md).

**Model tag.** A `ModelTag` or `ModelTagGroup` from
`idaes/core/util/tags.py` — a named, unit-aware handle on a model quantity used
for reporting and for annotating SVG process flow diagrams. Unrelated to a
logger tag or a git tag.

---

## 3. Term-collision table

This codebase overloads most of its important words. Every document resolves
these collisions explicitly on every use; an unqualified use of a term in the
first column is a review defect.

| Term | Sense 1 | Sense 2 | Sense 3 | Required phrasing |
|---|---|---|---|---|
| component | chemical species (`Component`, `idaes/core/base/components.py`) | Pyomo component (`Var`, `Constraint`, `Block`) | the `component` pytest marker | "chemical component" / "Pyomo component" / "the `component` marker" |
| block | Pyomo `Block` | IDAES process block | `ConfigBlock` | "Pyomo Block" / "process block" / "CONFIG block" |
| config | the global `idaes.cfg` tree (`idaes/config.py`) | a Pyomo `ConfigBlock`/`ConfigDict` | a property package configuration dictionary | "global configuration" / "CONFIG block" / "configuration dictionary" |
| scaler | a `CustomScalerBase` subclass | a scaling factor held in a `Suffix` | — | "Scaler object" / "scaling factor" |
| initializer | an `InitializerBase` subclass | Pyomo's `initialize=` keyword argument | the legacy `initialize()` method | "Initializer object" / "the `initialize=` argument" / "legacy initialization routine" |
| tag | `ModelTag` / `ModelTagGroup` | a logger tag (`idaes/logger.py`) | a git or release tag | "model tag" / "logger tag" / "release tag" |
| state | `StateBlock` | a state definition module (`FTPx`, `FcPh`, …) | `InitializationStatus` | "StateBlock" / "state definition" / "initialization status" |
| parameter | `PhysicalParameterBlock` | a Pyomo `Param` | a correlation coefficient | "parameter block" / "Pyomo Param" / "correlation coefficient" |
| property | a thermophysical quantity | a Python `@property` | a property package | "thermophysical property" / "Python property" / "property package" |
| domain | a CONFIG validator callable | `ContinuousSet` spatial domain (`length_domain`) | a variable's Pyomo domain | "CONFIG domain" / "length domain" / "variable domain" |
| build | `ProcessBlockData.build()` | `build_parameters` on a correlation class | the documentation or package build | "build method" / "`build_parameters`" / "documentation build" |
| flow | a material flow term | a `FlowDirection` enum member | flowsheet execution order | "flow term" / "flow direction" / "execution order" |
| extension | a downloaded binary from `idaes get-extensions` | a plug-in seam in the Python API | — | "binary extension" / "extension point" |
| unit | a unit model | a unit of measurement | the `unit` pytest marker | "unit model" / "unit of measurement" / "the `unit` marker" |
| `PhaseType` | the phase-classification enum (`idaes/core/base/phases.py:33`): `undefined`, `liquidPhase`, `vaporPhase`, `solidPhase`, `aqueousPhase` | the phase-presentation enum (`idaes/models/properties/general_helmholtz/helmholtz_functions.py:107`): `MIX`, `LG`, `L`, `G` | — | always qualified by import path; the member sets are disjoint |

Two further naming hazards, both real classes in the tree:

- **`QGESSCosting`** names two different classes in two different modules. Every
  reference disambiguates by import path, never by class name alone. See
  [17 §12](17_costing_framework_and_libraries.md#12-duplications-deprecations-and-sharp-edges).
- **`PhaseType`** names two enumerations with **disjoint** member sets: the
  phase classification in `idaes/core/base/phases.py:33` and the phase
  presentation in
  `idaes/models/properties/general_helmholtz/helmholtz_functions.py:107`. The
  second reaches every module of the Helmholtz steam-cycle unit models through
  the star-import shim at
  `idaes/models/properties/helmholtz/helmholtz.py:16`, so in those modules the
  bare name resolves to the Helmholtz enum. Every reference qualifies by import
  path. See [16 §12](16_general_helmholtz_property_system.md#12-duplications-deprecations-and-sharp-edges).

- **`matopt`** is importable both as `idaes.apps.matopt` and as the top-level
  name `matopt`, because `idaes/apps/matopt/__init__.py:16` inserts its parent
  directory onto `sys.path` before importing its own subpackages under the bare
  name (`idaes/apps/matopt/__init__.py:18`). Documents state the sentence once,
  in [26](26_matopt.md), and cite it elsewhere.

---

## 4. Anchor convention

An anchor is a repository-root-relative path and a line number in backticks,
placed adjacent to the symbol it identifies:

    the kwarg splitter `_process_kwargs` (`idaes/core/base/process_block.py:91`)

Rules:

1. Paths are relative to the repository root and always start `idaes/`.
2. Anchors are plain backticked text, never markdown links. Plain text stays
   greppable in any renderer and survives the file moving between repositories.
3. For a class or function, cite the `class` or `def` line, **not** the
   decorator line. Decorated classes are ambiguous to tooling — the pylint
   astroid plugin in `.pylint/idaes_transform.py` exists precisely because
   decorator-generated classes confuse static analysis — so the convention is to
   cite the definition line and name the decorator in prose.
4. For a CONFIG key, cite the `CONFIG.declare("key"` line.
5. Ranges (`:137-172`) are used only for a contiguous block actually described.
   Whole-file ranges are not used.
6. Every anchor in a document is repeated in that document's section 15, so a
   rebase can be reconciled mechanically.

All anchors are pinned to `70a8f4fe1`. `_scripts/verify.py --only anchors`
checks that every cited path exists and every cited line is in range.

---

## 5. Diagrams

Mermaid is used only where a diagram shows a mechanism that prose and tables
cannot. Five permitted forms:

| Form | Used for |
|---|---|
| `classDiagram` | an inheritance structure with at least three classes or two levels |
| `sequenceDiagram` | a build, initialization or solve path crossing at least two objects |
| `flowchart` | branching dispatch — submodel initializer resolution, `get_method` lookup, `useDefault` resolution |
| `stateDiagram-v2` | a status enum with transitions, such as `InitializationStatus` |
| `erDiagram` | relationships between data files, such as the Helmholtz parameter pipeline |

Limits, enforced by `_scripts/verify.py --only diagrams`: at most 6 diagrams per
document, at most 25 nodes per diagram, at most 8 participants in a sequence
diagram. Every diagram carries a one-sentence caption stating what the reader
takes from it. Anything that is a flat list of six or more items is a table, not
a diagram.

---

## 6. Table conventions

**Configuration tables.** One table per CONFIG block, with these columns in this
order:

| Key | Domain / validator | Default | Req. | Effect on build | Anchor |
|---|---|---|---|---|---|

Nested configuration dictionaries get their own table under a heading titled
with the dotted path. Reused templates — `CONFIG_Template` in
`idaes/core/base/control_volume_base.py`, the module-level `STREAM_CONFIG` in
`idaes/models/unit_models/mscontactor.py`, and the `_make_heater_config_block`
helper in `idaes/models/unit_models/heater.py` — are documented once in their
owning document. Consumers show only a delta table:

| Key | Inherited from | Override |
|---|---|---|

**Class rosters.** Every class hierarchy section carries a roster table
alongside its diagram:

| Class | Base(s) | Declared at | Decorator | Container class | Key overrides |
|---|---|---|---|---|---|

The container-class column holds the name synthesized by
`declare_process_block_class`, so the pair is visible in one row.

**Abstract contracts.** IDAES has no `abc.ABC` hierarchy. The de facto mechanism
is a method that raises `NotImplementedError`; there are 159 such sites. They
are presented as a table of the method set, never as prose.

**Correlation libraries.** Namespace-class libraries — `modular_properties/pure/`
and the MEA correlations in `models_extra/column_models/properties/` — use:

| Outer class | Inner property class | `build_parameters` | `return_expression` | Coefficient source | Anchor |
|---|---|---|---|---|---|

**Enums.** All 74 enum classes are presented as:

| Member | Value | Meaning | Consumed at |
|---|---|---|---|

---

## 7. Cross-referencing

References use a relative link carrying the document number and section:

    see [12 §4](12_modular_properties_generic_framework.md#4-configuration-reference)

Numbered headings produce stable slugs. Every cross-reference is reciprocal: if
document 10 cites document 04, then document 04 lists document 10 in its
section 8 or 14. `_scripts/verify.py --only xrefs` resolves every link and
reports one-way references.

Each fact has exactly one home. The ownership ledger in
[00](00_index_and_reading_map.md) assigns every source file and every shipped
asset to exactly one document; that document carries the normative description
and the others link to it. Documents 28 through 31 are index documents: their
rows point at an owning document and state a single fact, and they do not
restate semantics.

---

## 8. Language rules

The set describes the code as it stands at `70a8f4fe1`. Present indicative,
descriptive, no advocacy.

Words and phrases that do not appear in any document, checked by
`_scripts/verify.py --only language`:

<!-- verify:language-exempt-start -->
`Arrow`, `DataFusion`, `migrat*`, `roadmap`, `will be`, `should be`, `we plan`,
`TODO`, `recommend*`, and the filler adverbs `simply`, `just` and `obviously`.
<!-- verify:language-exempt-end -->

This list is the authoritative one; `_scripts/verify.py` holds the same set in
its `BANNED` constant. The region above is wrapped in exemption markers so that
the document defining the ban can name the banned words.

Evaluative statements are permitted only in section 12 of a document, only as an
observation with an anchor and an observable consequence. This is correct:

> Two classes named `QGESSCosting` exist. `from idaes.models.costing.QGESS import
> QGESSCosting` and `from idaes.models_extra.power_generation.costing.power_plant_capcost
> import QGESSCosting` resolve to different classes with different costing
> methods.

This is not, and does not appear anywhere in the set:

> The duplicate `QGESSCosting` classes ought to be consolidated.

Quoted source code inside fenced blocks is exempt from the language check, so a
comment marker in the codebase can be reproduced verbatim when it is the subject
of the description. A document that has to name a banned word outside a fence
wraps the passage in `<!-- verify:language-exempt-start -->` and
`<!-- verify:language-exempt-end -->`; this document is the only current user of
that escape hatch.

---

## 9. Document template

Every content document (02 onward) carries these sections, numbered, in this
order. Sections 0, 1, 2, 3, 8, 13, 14 and 15 are mandatory. The remainder are
mandatory where applicable and otherwise appear with the single line
`Not applicable: <one clause>` — a missing heading is a defect, never an
ambiguity.

| § | Heading | Content |
|---|---|---|
| 0 | Scope and source map | Table `File \| LOC \| Purpose \| Covered in §`. This is the coverage contract. |
| 1 | Architectural role | Up to 400 words plus one context diagram |
| 2 | Public surface inventory | `Symbol \| Kind \| Declared at \| Exported via \| Stability signal` |
| 3 | Class hierarchy and type taxonomy | Diagram plus roster table |
| 4 | Configuration reference | One table per CONFIG block |
| 5 | Construction and call sequences | Numbered anchored steps; what each step creates |
| 6 | Data structures, variables, constraints, invariants | `Component \| Type \| Index sets \| Units \| Created in \| Condition` |
| 7 | Method contracts | `Method \| Signature \| Preconditions \| Effects \| Returns \| Raises \| Anchor` |
| 8 | Cross-subsystem interactions | Two tables: calls out to, called by |
| 9 | Extension and subclassing contracts | `Hook \| Kind \| Signature \| Resolution order \| Base behaviour \| Anchor` |
| 10 | External assets, data files and external libraries | `Path \| Format \| Bytes \| Authored/Generated \| Producer \| Consumer \| Load site` |
| 11 | Errors, logging and diagnostics behaviour | Exceptions raised, logger names and levels |
| 12 | Duplications, deprecations and sharp edges | Observations with anchors and consequences |
| 13 | Behaviour pinned by tests | `Behaviour \| Test file:line \| Marker` |
| 14 | Cross-references | `Topic \| Doc \| Section` |
| 15 | Source anchor index | Every anchor used, with the symbol it names |

The *stability signal* column in section 2 records only observed facts:
membership of `__all__`, presence of a deprecation decorator, a leading
underscore, or coverage by an autodoc directive in `docs/`. IDAES publishes no
separate stability policy, so no document asserts one.

---

## 10. Units and quantities

IDAES carries Pyomo units on essentially every expression, and unit consistency
is asserted in tests through `pyomo.util.check_units` (124 import sites).
Documents therefore state units in every data-structure table. The vocabulary
for units comes from `UnitSet`
(`idaes/core/base/property_meta.py`), which defines seven base quantities and
roughly forty-three derived ones; a document naming a derived quantity uses the
`UnitSet` spelling, in upper case, as in `FLOW_MOL` or `HEAT_TRANSFER_COEFFICIENT`.

Currency is a unit too. `register_idaes_currency_units`
(`idaes/core/base/costing_base.py`) registers Chemical Engineering Plant Cost
Index-based currency units such as `USD_2018`, so cost expressions carry units
in the same way physical quantities do.

---

## 11. Counting conventions

Every count in the set comes from `_generated/`, produced by
`_scripts/inventory.py` at `70a8f4fe1`. Documents do not hand-count. Three
numbers are easy to get wrong and are fixed here:

Each structural count is produced by two independent extractors — the Python
`ast` module in `_scripts/inventory.py` and tree-sitter rules in `sgrules/` run
through `ast-grep scan` — and `_scripts/crosscheck.py` asserts they agree.

| Quantity | Value | Note |
|---|---:|---|
| Source modules | 465 | Tests and `idaes/conftest.py` excluded |
| Source LOC | 215,226 | Same exclusion |
| Classes declared by `declare_process_block_class` | 160 | Counted from the decorator, not the class name |
| `CONFIG.declare` keys | 1,083 | Only calls whose first argument is a string literal |
| `NotImplementedError` hook sites | 159 | A plain grep returns 161; two are commented out, at `idaes/models/properties/modular_properties/state_definitions/FpTPxpc.py:143` and `:380` |
| Classes named `*Scaler` | 46 | Not the same as the next row; 39 are in `idaes/models`, 7 in `idaes/core` |
| Process blocks declaring `default_scaler` | 24 | |
| Process blocks declaring `default_initializer` | 23 | |
| Deprecation sites | 49 | Counting a multi-line `@deprecated(...)` both as a call and as a decorator returns 53 |
| Shipped non-Python assets | 179 | Tracked files under `idaes/`, tests included |

---

## 12. Not applicable sections

Sections 4 through 13 of this template do not apply to this document: it owns no
source files and describes no subsystem. The set's own conventions are its
subject.

---

## 13. Cross-references

| Topic | Doc | Section |
|---|---|---|
| Ownership ledger, reading order | [00](00_index_and_reading_map.md) | §2 |
| The `FooData`/`Foo` pair in full | [03](03_block_hierarchy_and_construction_protocol.md) | §3, §5 |
| Property metadata and `UnitSet` | [05](05_property_and_reaction_framework.md) | §3 |
| Suffix-based and Scaler-based scaling | [06](06_model_preparation_initializers_and_scalers.md) | §1 |
| Every extension point named here | [31](31_extension_point_catalog.md) | §3 |
| `QGESSCosting` disambiguation | [17](17_costing_framework_and_libraries.md) | §12 |
| The `matopt` import name | [26](26_matopt.md) | §1 |

---

## 14. Source anchor index

| Anchor | Symbol |
|---|---|
| `idaes/core/base/process_block.py:35` | `_rule_default` |
| `idaes/core/base/process_block.py:106` | `_IndexedProcessBlockMeta` |
| `idaes/core/base/process_block.py:123` | `_ScalarProcessBlockMeta` |
| `idaes/core/base/process_block.py:141` | `ProcessBlock` |
| `idaes/core/base/process_block.py:176` | `declare_process_block_class` |
| `idaes/core/base/process_block.py:91` | `_process_kwargs` |
| `idaes/core/base/process_base.py:59` | `useDefault` |
| `idaes/core/base/process_base.py:78` | `ProcessBlockData` |
| `idaes/core/base/process_base.py:232` | `ProcessBlockData._get_config_args` |
| `idaes/core/base/flowsheet_model.py:99` | `FlowsheetBlockData` |
| `idaes/core/base/flowsheet_model.py:202` | `FlowsheetBlockData.is_flowsheet` |
| `idaes/core/base/unit_model.py:54` | `UnitModelBlockData` |
| `idaes/core/base/unit_model.py:61` | `UnitModelBlockData.default_initializer` |
| `idaes/core/base/unit_model.py:141` | `UnitModelBlockData.add_port` |
| `idaes/core/base/property_base.py:77` | `PhysicalParameterBlock` |
| `idaes/core/base/property_base.py:267` | `StateBlock` |
| `idaes/core/base/property_base.py:488` | `StateBlock.build_port` |
| `idaes/core/base/property_base.py:535` | `StateBlockData` |
| `idaes/core/base/property_base.py:816` | `StateBlockData.__getattr__` |
| `idaes/core/base/util.py:28` | `build_on_demand` |
| `idaes/apps/matopt/__init__.py:16` | `sys.path` insertion |
| `idaes/apps/matopt/__init__.py:18` | top-level `matopt` import |
| `idaes/models/properties/modular_properties/state_definitions/FpTPxpc.py:143` | commented-out `NotImplementedError` |
| `idaes/models/properties/modular_properties/state_definitions/FpTPxpc.py:380` | commented-out `NotImplementedError` |
