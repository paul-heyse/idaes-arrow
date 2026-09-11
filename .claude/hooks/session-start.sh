#!/usr/bin/env bash
# SessionStart: put the environment's actual state in front of the agent.
#
# An agent that starts by running `just py-test` in a tree with no solver
# binaries burns a minute and gets a collection error it then has to diagnose.
# Two seconds here avoids that.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

status="$(python3 scripts/doctor.py --format=text 2>&1 || true)"

# Hooks communicate with the model through additionalContext.
python3 - "$status" <<'PY'
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "Environment status (scripts/doctor.py):\n" + sys.argv[1],
    }
}))
PY
