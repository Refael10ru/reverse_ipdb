"""Project style rules that ruff cannot express natively.

Ruff has no bundled check to forbid a specific builtin like ``hasattr`` (its
banned-api list only covers imports), so we enforce it here instead — the
whole gate runs these on every CI push.
"""

import ast
import pathlib

LIB = pathlib.Path(__file__).resolve().parent.parent / "reverse_ipdb"

BANNED_CALLS = {"hasattr"}


def test_banned_builtins_not_used_in_library():
    offenders = []
    for path in sorted(LIB.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in BANNED_CALLS
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.func.id}()")
    assert not offenders, (
        "banned builtins used in the library (prefer EAFP / try-except): "
        + ", ".join(offenders)
    )
