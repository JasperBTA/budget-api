"""The Claude Code hooks in .claude/hooks, run the way Claude Code runs them: JSON on stdin."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

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


def test_ruff_errors_go_back_to_the_agent() -> None:
    # Inside the repo: the hook ignores files elsewhere. Deleted on exit, never committed.
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ROOT / "tests") as bad:
        bad.write("import os\nx=1\n")
        bad.flush()

        result = run("lint_changed_file.py", edit(Path(bad.name)))

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


def test_missing_base_ref_lets_the_edit_through() -> None:
    # Fail-open by design: the hook is early feedback, CI's migration diff is the gate.
    migration = ROOT / "migrations" / "versions" / "0001_initial_schema.py"
    result = run("guard_migrations.py", edit(migration), MIGRATION_BASE="origin/does-not-exist")
    assert (result.returncode, result.stdout) == (0, "")


def test_files_outside_the_repo_are_not_linted(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.py"
    scratch.write_text("import os\nx=1\n")
    assert run("lint_changed_file.py", edit(scratch), CLAUDE_PROJECT_DIR=str(ROOT)).returncode == 0


def test_failing_check_on_stop_sends_the_agent_back(tmp_path: Path) -> None:
    # A git repo with an untracked .py file and no project: the first check cannot pass.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "x.py").write_text("x = 1\n")

    result = run("check_on_stop.py", {"stop_hook_active": False}, CLAUDE_PROJECT_DIR=str(tmp_path))

    assert result.returncode == 2
    assert "fix it before finishing" in result.stderr


def test_every_hook_points_at_an_existing_script() -> None:
    # A renamed script would otherwise make its hook silently stop firing. Hooks live in
    # settings.json and in subagent headers (.claude/agents/*.md).
    sources = [ROOT / ".claude" / "settings.json", *(ROOT / ".claude" / "agents").glob("*.md")]
    scripts = {
        match
        for source in sources
        for match in re.findall(r"\.claude/hooks/[\w.-]+\.py", source.read_text())
    }
    assert len(scripts) >= 4
    assert all((ROOT / script).is_file() for script in scripts), scripts


READ_ONLY = [
    "git status --short && git diff",
    "git log --oneline -5 | head -3",
    "uv run pytest -q tests/unit 2>&1 | tail -1",
    "uv run ruff check . && uv run ruff format --check .",
    "uv run mypy src tests scripts >/dev/null",
    "grep -in 'session' src/budget/api/deps.py",
    "sed -n '1,20p' AGENTS.md",
    "uv run python -c 'import budget.domain.months as m; print(m.next_month)'",
]
WRITING = [
    "rm -rf src",
    "git checkout -- .",
    "git stash",
    "git diff --output=patch.diff",
    "sed -i '' 's/a/b/' AGENTS.md",
    "uv run ruff check --fix .",
    "uv run ruff format .",
    "echo x > AGENTS.md",
    "cat $(echo AGENTS.md)",
    "find . -name '*.pyc' -delete",
    "uv add requests",
    "git status; touch x",
]


@pytest.mark.parametrize("command", READ_ONLY)
def test_reviewer_guard_allows_read_only_commands(command: str) -> None:
    result = run(
        "guard_readonly_bash.py", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize("command", WRITING)
def test_reviewer_guard_denies_writes(command: str) -> None:
    result = run(
        "guard_readonly_bash.py", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"].startswith("Reviewer is read-only")
