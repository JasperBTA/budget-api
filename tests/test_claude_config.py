"""Subagents and slash commands in .claude/: a broken header makes Claude Code skip them."""

from pathlib import Path

import pytest

CLAUDE = Path(__file__).parents[1] / ".claude"
AGENTS = sorted((CLAUDE / "agents").glob("*.md"))
COMMANDS = sorted((CLAUDE / "commands").glob("*.md"))
# A misspelled tool is silently missing from the subagent, so names are checked against this list.
KNOWN_TOOLS = {"Read", "Grep", "Glob", "Bash", "Edit", "Write", "WebFetch", "WebSearch"}


def frontmatter(path: Path) -> dict[str, str]:
    """Top-level `key: value` pairs of the leading --- block.

    shortcut: flat one-line values only (no YAML lists, quotes or multi-line text), which is all
    these files use; switch to a YAML parser if a header needs more.
    """
    lines = path.read_text().splitlines()
    assert lines[:1] == ["---"] and "---" in lines[1:], f"{path.name}: needs a --- header block"
    end = lines.index("---", 1)
    return dict(line.split(": ", 1) for line in lines[1:end] if ": " in line)


def test_there_is_something_to_check() -> None:
    # An empty folder would make the parametrized tests below skip instead of fail.
    assert AGENTS and COMMANDS


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.name)
def test_subagents_have_name_description_and_known_tools(path: Path) -> None:
    header = frontmatter(path)
    assert header.get("name") == path.stem
    assert header.get("description")
    tools = {tool.strip() for tool in header.get("tools", "").split(",")}
    assert tools and tools <= KNOWN_TOOLS, f"unknown tools: {sorted(tools - KNOWN_TOOLS)}"


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_commands_have_a_description_and_use_their_arguments(path: Path) -> None:
    assert frontmatter(path).get("description")
    assert "$ARGUMENTS" in path.read_text()


def test_the_workflow_points_at_files_that_exist() -> None:
    # AGENTS.md sends agents to these files; a rename must not leave dead references.
    agents_md = (CLAUDE.parent / "AGENTS.md").read_text()
    for name in ("agents/reviewer.md", "commands/design-doc.md", "commands/new-endpoint.md"):
        assert f".claude/{name}" in agents_md and (CLAUDE / name).is_file()
