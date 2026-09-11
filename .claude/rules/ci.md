---
description: GitHub Actions gotchas that have broken this repo
paths:
  - ".github/**"
---

# Editing workflows

Run `just lint-workflows` before pushing. Every item below is a real incident
here, and actionlint catches all of them.

- **`yaml.safe_load` accepts duplicate keys silently** (last wins). Adding an
  `if:` to a job that already had one produced a guard that did nothing, and a
  plain YAML parse check passed.
- **A `#` line inside a `>-` folded scalar is content, not a comment.** It gets
  evaluated as part of the expression. Put notes above the key.
- **GitHub Actions does not support YAML anchors.** Duplicate the block and say
  why in a comment.
- **`windows-*` runners default to PowerShell.** Any bash script needs
  `defaults.run.shell: bash` at the job level or it dies with a `ParserError`.
- **`macos-13` is retired**; the Intel image is `macos-15-intel`.
- **An empty env var is not an unset one.** `FOO: ${{ cond && 'x' || '' }}` sets
  `FOO=""`, which broke `CARGO_TARGET_DIR`. Use a conditional step instead.

## This repository specifically

- Jobs that would publish or need upstream secrets are guarded with
  `github.repository == 'IDAES/idaes-pse'`, so they no-op in the fork.
- Any job running the IDAES test suite needs `idaes get-extensions` first, or
  pytest aborts at collection.
- Never upload coverage from an `IDAES_ACCEL=force` job — the Python paths stop
  executing and coverage collapses past Codecov's threshold.
- Tool versions are pinned from `pyproject.toml [dependency-groups]`. Do not
  `pip install ruff` in a workflow.
