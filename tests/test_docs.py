"""Relative links in the docs point at files that exist: renames must not leave dead links."""

import re
from pathlib import Path

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
LINK = re.compile(r"\]\(([^)\s]+)\)")


def relative_links(path: Path) -> list[str]:
    targets = (target.split("#", 1)[0] for target in LINK.findall(path.read_text()))
    return [t for t in targets if t and not re.match(r"[a-z]+:", t)]  # skip https:, mailto:


def test_there_are_docs_to_check() -> None:
    assert len(DOCS) >= 10


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_resolve(path: Path) -> None:
    dead = [link for link in relative_links(path) if not (path.parent / link).exists()]
    assert not dead, f"{path.relative_to(ROOT)}: dead links {dead}"
