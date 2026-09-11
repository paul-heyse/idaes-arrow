#!/usr/bin/env bash
# PostToolUse on Edit|Write: format the file that was just edited.
#
# Uses the pinned tools from .venv and rust/rust-toolchain.toml, so what happens
# here is exactly what CI checks. Formatting-only CI failures stop existing.
#
# Never fails the tool call: a formatter problem is not a reason to lose an edit.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" || exit 0

file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)"
[ -n "$file" ] && [ -f "$file" ] || exit 0

case "$file" in
  # Vendored references and another workflow's corpus are excluded everywhere
  # else (ruff, black, typos); be consistent here.
  */docs-code-update/*|*/.codex/*|*/.agents/*|*/rust/target/*) exit 0 ;;
  *.py)
    [ -x .venv/bin/ruff ] && .venv/bin/ruff format -q "$file" >/dev/null 2>&1
    ;;
  *.rs)
    (cd rust && cargo fmt -- "${file#rust/}") >/dev/null 2>&1
    ;;
  *.toml)
    command -v taplo >/dev/null 2>&1 && taplo fmt "$file" >/dev/null 2>&1
    ;;
esac
exit 0
