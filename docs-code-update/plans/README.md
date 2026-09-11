# Plans

Design and implementation plans for this fork, in the repository rather than in
any one agent's private state.

Plans under `~/.claude/plans/` are invisible to Codex and to the next session.
Here they are readable by both runtimes, reviewable in a pull request, and they
carry the reasoning that commit messages compress.

| Plan | Covers | Status |
|---|---|---|
| `01_rust_arrow_integration.md` | Forking, the `rust/` workspace, the Arrow/PyO3 boundary, the dispatch layer, CI, the first vertical slice | Phases 0-4 done; Phase 5 (the `parameter_sweep` -> `pysmo/sampling` slice) open |
| `02_agent_environment.md` | Environment bootstrap, direnv, AGENTS.md/CLAUDE.md, the ruff and pyrefly pivot, agent configuration | Implemented |

A plan records what was decided and **why**, including options rejected and the
measurements behind a choice. When the code and a plan disagree, the code is what
runs — update the plan or note the divergence.

`just plan <name>` creates a stub.
