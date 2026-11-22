"""The layer table in AGENTS.md, as a test: a forbidden import fails CI, not just a review.

Relative imports are banned by ruff (TID252), so every import here is absolute.
"""

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[1] / "src" / "budget"


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def imports(tree: ast.Module) -> set[str]:
    """Absolute module names a file imports; `from budget import x` counts as `budget.x`."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module == "budget":
            names |= {f"budget.{alias.name}" for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def files(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def under(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


@pytest.mark.parametrize("path", files("domain"), ids=rel)
def test_domain_imports_only_stdlib_and_domain(path: Path) -> None:
    bad = {
        name
        for name in imports(parse(path))
        if not under(name, ("budget.domain",)) and name.split(".")[0] not in sys.stdlib_module_names
    }
    assert not bad, f"{rel(path)}: domain/ is pure Python, but imports {sorted(bad)}"


@pytest.mark.parametrize("path", files("services"), ids=rel)
def test_services_do_not_know_about_http(path: Path) -> None:
    ok = ("budget.domain", "budget.models", "budget.errors", "budget.security", "budget.services")
    names = imports(parse(path))
    bad = {n for n in names if under(n, ("budget",)) and not under(n, ok)}
    bad |= {n for n in names if under(n, ("fastapi", "starlette", "pydantic"))}
    assert not bad, f"{rel(path)}: services/ must not import {sorted(bad)}"


@pytest.mark.parametrize("path", files("api"), ids=rel)
def test_api_runs_no_sql(path: Path) -> None:
    ok = (
        "budget.api",
        "budget.services",
        "budget.schemas",
        "budget.db",  # SessionDep only, checked below
        "budget.security",
        "budget.models",  # type hints only (e.g. CurrentUser); not checked by this test
    )
    tree = parse(path)
    names = imports(tree)
    bad = {n for n in names if under(n, ("budget",)) and not under(n, ok)}
    bad |= {n for n in names if under(n, ("sqlalchemy",))}
    bad |= {
        f"budget.db.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "budget.db"
        for alias in node.names
        if alias.name != "SessionDep"  # SessionLocal / engine would allow SQL under any name
    }
    # A session is any parameter typed SessionDep, whatever it is called; it may only be passed on.
    sessions = {
        node.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.arg)
        and isinstance(node.annotation, ast.Name)
        and node.annotation.id == "SessionDep"
    }
    bad |= {
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in sessions
    }
    assert not bad, f"{rel(path)}: api/ must not use {sorted(bad)}"


TOP_LEVEL = sorted(p for p in SRC.glob("*.py") if p.name != "main.py")  # main.py wires routers


@pytest.mark.parametrize("path", TOP_LEVEL, ids=rel)
def test_shared_modules_do_not_import_upper_layers(path: Path) -> None:
    bad = {n for n in imports(parse(path)) if under(n, ("budget.api", "budget.services"))}
    assert not bad, f"{rel(path)}: dependencies point down only, but imports {sorted(bad)}"


def test_every_layer_has_files() -> None:
    # Guards the parametrized tests above against passing vacuously after a rename or move.
    assert all(files(layer) for layer in ("domain", "services", "api")) and TOP_LEVEL
