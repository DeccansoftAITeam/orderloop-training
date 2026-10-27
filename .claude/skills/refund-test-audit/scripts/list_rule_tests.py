"""List test names under a folder and flag the ones that do not state a behaviour.

Usage:  python list_rule_tests.py [tests_folder]     (default: backend/tests)
Exit code 0 when every name is fine, 1 when at least one is weak.
Standard library only.
"""

import ast
import re
import sys
from pathlib import Path

MIN_WORDS = 3


def weakness(name: str) -> str | None:
    words = name.removeprefix("test_").split("_")
    if len(words) < MIN_WORDS:
        return f"only {len(words)} word(s); needs at least {MIN_WORDS}"
    if re.fullmatch(r"\d{1,2}", words[-1]):
        return "ends in a counter instead of a behaviour"
    return None


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "backend/tests")
    weak = 0
    total = 0
    for path in sorted(folder.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1
                problem = weakness(node.name)
                if problem:
                    weak += 1
                    print(f"WEAK {node.name}  ({path.as_posix()}:{node.lineno})  {problem}")
    print(f"{total} tests, {weak} weak")
    return 1 if weak else 0


if __name__ == "__main__":
    sys.exit(main())
