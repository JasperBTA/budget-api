"""PreToolUse (Bash) for the reviewer subagent: allow read-only commands, deny everything else.

Registered in the frontmatter of .claude/agents/reviewer.md, so it runs only while the reviewer
works. Allowlist, not denylist: an unknown command is refused, the reviewer reports instead.
"""

from __future__ import annotations  # hooks run on the system python3, which may be 3.9

import json
import re
import shlex
import sys

ALLOWED = (
    ("git", "status"),
    ("git", "diff"),
    ("git", "log"),
    ("git", "show"),
    ("git", "ls-files"),
    ("git", "grep"),
    ("git", "blame"),
    ("git", "rev-parse"),
    ("git", "cat-file"),
    ("git", "merge-base"),
    ("uv", "run", "pytest"),
    ("uv", "run", "mypy"),
    ("uv", "run", "ruff", "check"),
    ("uv", "run", "ruff", "format"),
    ("uv", "run", "python", "-c"),
    ("gh", "pr", "view"),
    ("gh", "pr", "diff"),
    ("gh", "pr", "checks"),
    ("ls",),
    ("cat",),
    ("head",),
    ("tail",),
    ("wc",),
    ("grep",),
    ("rg",),
    ("find",),
    ("sed",),
    ("sort",),
    ("uniq",),
    ("diff",),
    ("jq",),
    ("echo",),
    ("pwd",),
    ("which",),
)
# Flags that turn an allowed command into a writing one, per command (`grep -i` is harmless,
# `sed -i` is not). A flag also matches its `--flag=value` form.
WRITING_FLAGS = {
    "sed": {"-i", "--in-place"},
    "find": {"-delete", "-exec", "-execdir", "-fprint"},
    "sort": {"-o", "--output"},
    "git": {"--output"},
    "uv": {"--fix"},
}
HARMLESS_REDIRECTS = re.compile(r"\d?>\s*/dev/null|2>&1")
# shortcut: `uv run python -c` probes could still open a file for writing; the reviewer's prompt
# forbids it, tighten to an AST check of the snippet if that ever proves not enough.


def segments(command: str) -> list[list[str] | None]:
    """Simple commands split on `&&`, `||`, `;`, `|`, `&`, honouring quotes; None if unparsable."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [None]
    result: list[list[str] | None] = [[]]
    for token in tokens:
        if token in {"&&", "||", ";", "|", "&", ";;"}:
            result.append([])
        else:
            current = result[-1]
            assert current is not None
            current.append(token)
    return [words for words in result if words]


def refusal(command: str) -> str | None:
    """Why the command is refused, or None when it is read-only."""
    if "`" in command or "$(" in command:
        return "command substitution can hide a write"
    command = HARMLESS_REDIRECTS.sub("", command)
    if ">" in command:  # also inside quotes: refusing a harmless `print(1 > 0)` is acceptable
        return "output redirection writes a file"
    for words in segments(command):
        if words is None:
            return "unparsable command"
        if not any(tuple(words[: len(prefix)]) == prefix for prefix in ALLOWED):
            return f"`{' '.join(words[:3])}` is not on the reviewer's read-only list"
        flags = WRITING_FLAGS.get(words[0], set())
        if writing := [w for w in words if w.split("=", 1)[0] in flags]:
            return f"`{words[0]} {writing[0]}` writes files"
        if words[:4] == ["uv", "run", "ruff", "format"] and not {"--check", "--diff"} & set(words):
            return "`ruff format` without --check rewrites files"
    return None


def main() -> int:
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    reason = refusal(command)
    if reason is None:
        return 0
    decision = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"Reviewer is read-only: {reason}. Report it instead.",
    }
    print(json.dumps({"hookSpecificOutput": decision}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
