#!/usr/bin/env bash
# PreToolUse on Edit|Write: refuse writes to territory this session does not own.
#
# docs-code-update/authoritative_design/ belongs to a separate, concurrently
# running workflow with its own brief, ownership ledger and mechanical
# verifiers. An edit from here corrupts its anchors and its banned-word checks.
#
# Exit 2 blocks the call and returns stderr to the model as the reason.
set -uo pipefail

file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)"
[ -n "$file" ] || exit 0

case "$file" in
  *docs-code-update/authoritative_design/*)
    echo "BLOCKED: docs-code-update/authoritative_design/ is owned by a separate workflow." >&2
    echo "It has its own brief (_scripts/AUTHOR_BRIEF.md), a file-ownership ledger, and" >&2
    echo "mechanical verifiers with anchors pinned to 70a8f4fe1. Read it; do not edit it." >&2
    echo "See the 'Off-limits' section of AGENTS.md." >&2
    exit 2
    ;;
  */.git/*|*/rust/target/*)
    echo "BLOCKED: $file is generated or VCS-internal state, not source." >&2
    exit 2
    ;;
esac
exit 0
