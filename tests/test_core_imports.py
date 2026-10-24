from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = {"aiogram", "sqlalchemy", "openai"}


def test_core_has_no_forbidden_imports() -> None:
    core_path = Path(__file__).parent / "src" / "tgtwin" / "core"
    for py in core_path.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in FORBIDDEN, f"{py} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    assert top not in FORBIDDEN, f"{py} imports from {node.module}"
