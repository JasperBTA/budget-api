"""PostToolUse (Edit|Write): run ruff on the edited Python file and hand errors back to the agent.

Exit code 2 sends stderr to the agent, which then fixes the file in the same turn.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    event = json.load(sys.stdin)
    path = event.get("tool_input", {}).get("file_path", "")
    if not path.endswith(".py") or not Path(path).exists():
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    problems = [
        result.stdout + result.stderr
        for command in (["check", path], ["format", "--check", "--diff", path])
        if (
            result := subprocess.run(
                ["uv", "run", "--frozen", "ruff", *command],
                cwd=root,
                capture_output=True,
                text=True,
            )
        ).returncode
        != 0
    ]
    if not problems:
        return 0
    print(f"ruff found problems in {path}; fix them before moving on:\n", file=sys.stderr)
    print("\n".join(problems), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
