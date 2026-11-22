"""Relative links in the docs point at files that exist: renames must not leave dead links.

Checks inline links (with or without a title or <angle brackets>) and reference definitions
(`[id]: path`), outside code. Does not check anchors (`#section`) or HTML `<a href>`, which the
docs do not use. This is a link check only: it cannot tell whether a sentence is true.
"""

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).parents[1]
DOCS = sorted(
    [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob(".claude/**/*.md"),
    ]
)
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
INLINE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.MULTILINE)


def relative_links(text: str) -> list[str]:
    text = CODE.sub("", text)
    targets = [unquote(t.split("#", 1)[0]) for t in INLINE.findall(text) + REFERENCE.findall(text)]
    return [t for t in targets if t and not re.match(r"[a-z]+:", t)]  # skip https:, mailto:


def resolve(path: Path, link: str) -> Path:
    # GitHub resolves a leading / from the repository root, not the filesystem root.
    return ROOT / link.lstrip("/") if link.startswith("/") else path.parent / link


def test_there_are_docs_to_check() -> None:
    assert len(DOCS) >= 10


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_resolve(path: Path) -> None:
    dead = [link for link in relative_links(path.read_text()) if not resolve(path, link).exists()]
    assert not dead, f"{path.relative_to(ROOT)}: dead links {dead}"


def test_link_parser_handles_the_markdown_forms() -> None:
    text = """
[a](one.md) [b](two.md "Title") [c](<three.md>) [d](my%20file.md#part) [e](https://x.y)
[ref]: four.md
```python
x = d[0](not_a_link)
```
and `[f](not_a_link_either)` in inline code.
"""
    assert relative_links(text) == ["one.md", "two.md", "three.md", "my file.md", "four.md"]
