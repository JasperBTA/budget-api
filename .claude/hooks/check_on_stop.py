"""Stop: before the agent ends its turn, run mypy and the database-free tests.

Runs only when Python files changed, and only once per stop (stop_hook_active), so a failure
sends the agent back to fix it instead of looping forever.
"""

import json
import os
import subprocess
import sys

CHECKS = (
    ["uv", "run", "--frozen", "mypy", "src", "tests", "scripts"],
    ["uv", "run", "--frozen", "pytest", "-q", "tests/unit", "tests/test_architecture.py"],
)


def python_changed(root: str) -> bool:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "*.py"], cwd=root, capture_output=True, text=True
    )
    return bool(status.stdout.strip())


def main() -> int:
    event = json.load(sys.stdin)
    root = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if event.get("stop_hook_active") or not python_changed(root):
        return 0
    for command in CHECKS:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if result.returncode != 0:
            output = (result.stdout + result.stderr)[-4000:]
            print(f"`{' '.join(command[3:])}` failed; fix it before finishing:\n", file=sys.stderr)
            print(output, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
