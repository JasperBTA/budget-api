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
    root = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if not path.endswith((".py", ".pyi")) or not Path(path).exists():
        return 0
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return 0  # scratch files elsewhere are not held to this project's ruff config
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
    print("\n".join(problems)[-4000:], file=sys.stderr)  # a full reformat diff can be huge
    return 2


if __name__ == "__main__":
    sys.exit(main())
