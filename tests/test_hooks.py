"""The Claude Code hooks in .claude/hooks, run the way Claude Code runs them: JSON on stdin."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def run(hook: str, event: dict[str, object], **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), **env},
    )


def edit(path: Path) -> dict[str, object]:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


def test_merged_migration_edit_is_denied() -> None:
    # HEAD stands in for origin/main, so the test does not depend on which refs CI fetched.
    migration = ROOT / "migrations" / "versions" / "0001_initial_schema.py"

    result = run("guard_migrations.py", edit(migration), MIGRATION_BASE="HEAD")

    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "add a new one" in decision["permissionDecisionReason"]


def test_new_migration_and_other_files_are_allowed() -> None:
    for path in (
        ROOT / "migrations" / "versions" / "0099_new.py",
        ROOT / "src" / "budget" / "main.py",
    ):
        result = run("guard_migrations.py", edit(path), MIGRATION_BASE="HEAD")
        assert (result.returncode, result.stdout) == (0, "")


def test_ruff_errors_go_back_to_the_agent(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("import os\nx=1\n")

    result = run("lint_changed_file.py", edit(bad))

    assert result.returncode == 2  # exit 2: stderr is shown to the agent
    assert "F401" in result.stderr


def test_clean_and_non_python_files_pass(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("import os\n")
    for path in (ROOT / "src" / "budget" / "main.py", notes):
        assert run("lint_changed_file.py", edit(path)).returncode == 0


def test_stop_hook_does_not_loop() -> None:
    # A second stop after a failed check must let the agent finish instead of blocking again.
    assert run("check_on_stop.py", {"stop_hook_active": True}).returncode == 0
