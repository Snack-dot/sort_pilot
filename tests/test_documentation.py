from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "sort_pilot"
FUNCTION_MAP = ROOT / "docs" / "FUNCTION_MAP.md"


def _callables() -> list[tuple[Path, str, int, str]]:
    """Collect every package class/function with its qualified display name."""
    found: list[tuple[Path, str, int, str]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((path, node.name, node.lineno, ast.get_docstring(node) or ""))
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            found.append(
                                (
                                    path,
                                    f"{node.name}.{child.name}",
                                    child.lineno,
                                    ast.get_docstring(child) or "",
                                )
                            )
    return found


def test_every_package_callable_has_a_docstring():
    missing = [f"{path}:{line} {name}" for path, name, line, doc in _callables() if not doc]
    assert not missing, "Missing callable documentation:\n" + "\n".join(missing)


def test_function_map_mentions_every_callable():
    documentation = FUNCTION_MAP.read_text(encoding="utf-8")
    missing = [
        name
        for _, name, _, _ in _callables()
        if name not in documentation and name.rsplit(".", 1)[-1] not in documentation
    ]
    assert not missing, "Missing FUNCTION_MAP symbols:\n" + "\n".join(missing)
