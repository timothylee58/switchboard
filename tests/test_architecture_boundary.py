"""
tests/test_architecture_boundary.py

The single most important test in this repo. It enforces, mechanically,
that core/ and governance/ never import a domain package — proving the
orchestration/domain separation is real, not just a folder-naming
convention. Runs in .github/workflows/core-ci.yml on every PR.

If this test ever needs to be modified to make a passing test green
again, that's a signal the boundary was violated somewhere — fix the
violation, don't loosen the test.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROTECTED_DIRS = ["core", "governance"]
REPO_ROOT = Path(__file__).resolve().parent.parent


def _imported_module_roots(py_file: Path) -> set[str]:
    """Parse a Python file's AST and return the top-level module name
    of every import statement (e.g. 'agents.devtools.agent' -> 'agents')."""
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])

    return roots


def test_core_and_governance_never_import_agents_package():
    """If this fails: something under core/ or governance/ imported
    'agents' (or a specific domain submodule) directly. That import must
    be removed — use core.registry.AgentRegistry instead, which domain
    packages register themselves INTO rather than core importing OUT of."""
    violations: list[str] = []

    for protected_dir in PROTECTED_DIRS:
        dir_path = REPO_ROOT / protected_dir
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            roots = _imported_module_roots(py_file)
            if "agents" in roots:
                violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert not violations, (
        "Architecture boundary violated — these files import the 'agents' "
        f"package directly:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return line numbers of every module/class/function docstring so
    the scanner below can skip them — explaining a forbidden pattern in
    prose is not the same as using it in live code."""
    docstring_lines: set[int] = set()
    candidates: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            candidates.append(node)
    for node in candidates:
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docstring_lines.add(body[0].value.lineno)
    return docstring_lines


def test_core_has_no_hardcoded_domain_conditionals():
    """
    Secondary check: scans for the textual pattern of a domain-name branch
    (e.g. `if domain == "devtools"`) inside core/. This is a heuristic,
    not airtight — it catches the most common boundary leak, where
    someone routes by string comparison instead of going through
    AgentRegistry / SpecialistAgent.can_handle().

    Deliberately ignores docstrings (module/class/function level):
    explaining what core must NOT do (e.g. "never write
    `from agents.devtools import X`") is legitimate documentation, not
    a leak. Only string literals used in actual code count.
    """
    suspicious_tokens = ["devtools", "sme_ops", "support"]  # extend per registered domains
    violations: list[str] = []

    for protected_dir in PROTECTED_DIRS:
        dir_path = REPO_ROOT / protected_dir
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
            docstring_lines = _docstring_nodes(tree)

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if node.lineno in docstring_lines:
                    continue  # part of a docstring, not live code
                lowered = node.value.lower()
                for token in suspicious_tokens:
                    if token in lowered:
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} "
                            f"contains literal '{token}' in code (not docstring)"
                        )

    assert not violations, (
        "Possible domain-name leak into core/governance — found literal "
        f"domain identifiers in code:\n" + "\n".join(f"  - {v}" for v in violations)
    )
