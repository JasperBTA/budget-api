"""PreToolUse (Edit|Write): refuse edits to migrations that are already on main.

AGENTS.md: "Never edit a migration that has been merged to main; add a new one."
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    event = json.load(sys.stdin)
    path = Path(event.get("tool_input", {}).get("file_path", ""))
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return 0  # outside the repo
    if relative.parts[:2] != ("migrations", "versions"):
        return 0
    # shortcut: compares with the local origin/main ref; run `git fetch` if it is stale.
    base = os.environ.get("MIGRATION_BASE", "origin/main")
    merged = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{base}:{relative.as_posix()}"],
        capture_output=True,
    )
    if merged.returncode != 0:
        return 0  # a new migration on this branch: editing it is fine
    reason = (
        f"{relative} is already on {base}. Merged migrations are never edited (AGENTS.md, "
        "Database and migrations): add a new one with "
        "`uv run alembic revision --autogenerate --rev-id <next> -m '<what>'`."
    )
    output = {"permissionDecision": "deny", "permissionDecisionReason": reason}
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
