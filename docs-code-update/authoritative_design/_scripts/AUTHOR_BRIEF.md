# Author brief — authoritative_design document set

Read this before writing any document in
`/home/paul/idaes-pse/docs-code-update/authoritative_design/`.

## What this set is

A complete, verified, **as-is** architecture reference for IDAES-PSE at commit
`70a8f4fe1` (v2.13.0rc0). It documents the library exactly as it stands. It is
not a plan, not a critique, and not a proposal.

## Mandatory reading before you write

1. `01_glossary_and_conventions.md` — the controlled vocabulary, the
   term-collision table, the anchor/diagram/table conventions, and the language
   rules. Use these terms verbatim.
2. `04_control_volume_framework.md` — the worked exemplar. Match its depth,
   section shape, table density and tone. Copy its structure, not its content.
3. Your own document's rows in `_generated/ledger.csv` — the exact files you own.

## Non-negotiable rules

- **As-is only.** Present indicative. Describe what the code does, never what
  anyone could or ought to do about it. Evaluative statements appear only in
  section 12, only as an observation with an anchor and an observable
  consequence.
- **Banned words**, checked mechanically: `Arrow`, `DataFusion`, `migrat*`,
  `roadmap`, `will be`, `should be`, `we plan`, `TODO`, `recommend*`, `simply`,
  `just`, `obviously`. Quoted source inside fenced code blocks is exempt.
- **You own exactly the files the ledger assigns you.** Everything else is a
  cross-reference to the owning document, never a restatement.
- **Every non-obvious claim carries an anchor**: `` `idaes/path/file.py:LINE` ``,
  repo-root-relative, in backticks, next to the symbol it names. Cite the
  `class`/`def` line, not the decorator line. For a config key, cite the
  `CONFIG.declare("key"` line.

## Line numbers: the working tree is NOT the subject

The document set describes the IDAES library at **`70a8f4fe1`**. The repository
has moved on since — there is now an `idaes/accel/` package and
`idaes/core/surrogate/pysmo/sampling.py` has changed — and it may move again
while you write.

**Take every line number from the pinned revision, never from the working tree.**
The generated inputs in `_generated/` are already taken at the pin, so figures
from `symbols.json`, `classes.csv`, `config_keys.csv` and `hooks.csv` are correct
as they stand. When you need to read source directly, read the pinned version:

```bash
git show 70a8f4fe1:idaes/core/base/unit_model.py | sed -n '140,175p'
ast-grep outline <(git show 70a8f4fe1:idaes/models/unit_models/mixer.py) --lang python
```

`verify.py --only anchors` resolves every anchor against `70a8f4fe1`, so an
anchor taken from the working tree for a file that has changed will FAIL even
though it looks right in your editor. Files under `idaes/accel/` do not exist at
the pinned revision and are outside the documented scope — never cite them.
- **Never hand-count.** Every count comes from `_generated/`.
- **Length 400-1400 lines**, with 1250 as the guideline. Between 1250 and 1400
  the verify script notes it and passes. Above 1400 the scope needs splitting,
  not compressing — use the pre-approved `NNa_`/`NNb_` split for your document
  and say so in your report.
- **At most 6 mermaid diagrams**, each with a one-sentence caption saying what
  the reader takes from it. Six or more flat items is a table, not a diagram.
- **All 16 template sections**, numbered, in order. A section that does not
  apply gets the single line `Not applicable: <one clause>`. A missing heading
  is a defect.

## Document header

```
# NN — <Title>

> **Doc ID** NN · **Repo SHA** 70a8f4fe1 (IDAES-PSE v2.13.0rc0) · **Source roots** `idaes/...`
> **Owns** N modules / N LOC · **Assets** ... · **Siblings** [aa](aa_....md), [bb](bb_....md)
```

## The 16 sections

| § | Heading | Content |
|---|---|---|
| 0 | Scope and source map | Table `File \| LOC \| Purpose \| Covered in §` over every file you own |
| 1 | Architectural role | ≤400 words + one context diagram |
| 2 | Public surface inventory | `Symbol \| Kind \| Declared at \| Exported via \| Stability signal` |
| 3 | Class hierarchy and type taxonomy | classDiagram + roster table incl. the generated container class; enum tables |
| 4 | Configuration reference | One table per CONFIG block: `Key \| Domain/validator \| Default \| Req. \| Effect on build \| Anchor` |
| 5 | Construction and call sequences | Numbered anchored steps; what each step creates |
| 6 | Data structures, variables, constraints, invariants | `Component \| Type \| Index sets \| Units \| Created at \| Condition` plus an invariants table |
| 7 | Method contracts | `Method \| Signature \| Preconditions \| Effects \| Returns \| Raises \| Anchor` |
| 8 | Cross-subsystem interactions | Two tables: *Calls out to*, *Called by* |
| 9 | Extension and subclassing contracts | `Hook \| Kind \| Signature \| Resolution order \| Base behaviour \| Anchor`. Every `NotImplementedError` you own must appear. |
| 10 | External assets, data files and external libraries | `Path \| Format \| Bytes \| Authored/Generated \| Producer \| Consumer \| Load site` |
| 11 | Errors, logging and diagnostics behaviour | Exceptions raised, logger names, levels |
| 12 | Duplications, deprecations and sharp edges | Observations with anchors and consequences |
| 13 | Behaviour pinned by tests | `Behaviour \| Test file:line \| Marker` |
| 14 | Cross-references | `Topic \| Doc \| Section` |
| 15 | Source anchor index | Every anchor used, with the symbol it names, sorted |

## Tools — use these, not `cat`

`ast-grep` 0.45.2 and `ripgrep` 15.2.0 are installed.

```bash
# Module structure with line numbers, without reading bodies. Use this first,
# always. A 2,873-line file becomes 44 lines. For a file that has changed since
# the pin, outline the pinned content instead (see the line-numbers section).
ast-grep outline idaes/core/base/control_volume1d.py --view expanded

# Then read only the regions you actually need
sed -n '440,480p' idaes/core/base/control_volume1d.py

# Structural search (no false hits in comments or strings)
ast-grep run --lang python -p 'class $C(ControlVolumeBlockData): $$$' idaes/ --json=compact

# The five project rules, as a second extractor
ast-grep scan --config docs-code-update/authoritative_design/sgconfig.yml \
  --filter '^idaes-config-declare$' --globs '!**/tests/**' --json=compact idaes
```

## Your generated inputs

All in `docs-code-update/authoritative_design/_generated/`:

| File | Use it for |
|---|---|
| `ledger.csv` | Exactly which files you own (`doc` column == your number) |
| `modules.csv` | LOC per file, for your section 0 table |
| `symbols.json` | Classes, bases, decorators, class attributes, methods with line ranges and signatures |
| `classes.csv` | Flat class roster incl. `default_initializer` / `default_scaler` |
| `process_blocks.csv` | `@declare_process_block_class` sites and the synthesized container name |
| `config_keys.csv` | Every config key with domain, default and description — section 4 |
| `hooks.csv` | Every `NotImplementedError` site — section 9 |
| `enums.csv` | Enum members and values — section 3 |
| `imports.csv` | Section 8 |
| `externals.csv` | External library bindings — section 10 |
| `deprecations.csv` | Section 12 |
| `assets.csv` | Non-Python files — section 10 |
| `markers.csv` | pytest markers per test file — section 13 |

Example: your config table rows, ready to transcribe:

```bash
python3 - <<'EOF'
import csv
MINE = "06"                      # your document number
led = {r["file"] for r in csv.DictReader(open("docs-code-update/authoritative_design/_generated/ledger.csv"))
       if r["doc"] == MINE}
for r in csv.DictReader(open("docs-code-update/authoritative_design/_generated/config_keys.csv")):
    if r["file"] in led:
        print(r["file"], r["line"], r["enclosing_class"], r["key"], r["domain"], r["default"], sep=" | ")
EOF
```

## Before you finish

```bash
cd /home/paul/idaes-pse
python3 docs-code-update/authoritative_design/_scripts/verify.py
```

All checks must pass. `config` and `hooks` failing means you left something out
of section 4 or section 9 — that is the check doing its job, not a false alarm.
`assets` skipping is expected until document 28 exists. `xrefs` reporting
"planned documents linked but not yet written" is expected and fine.

Write the file with a heredoc (`cat > path <<'MDEOF' ... MDEOF`) so no shell
expansion touches the content.
