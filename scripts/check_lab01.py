"""Check for Lab 1 (First session and memory). Standard library only.

Run from the repository root:  python scripts/check_lab01.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


agents = ROOT / "AGENTS.md"
text = read(agents)
lines = [ln for ln in text.splitlines() if ln.strip()]
low = text.lower()

check(agents.exists(), "AGENTS.md exists in the project root")
check(10 <= len(lines) <= 100, f"AGENTS.md is between 10 and 100 non-empty lines (found {len(lines)})")
check("30 days" in low, "AGENTS.md states the 30-day refund window")
check("restocking" in low, "AGENTS.md states the restocking fee rule")
check("final-sale" in low or "final sale" in low, "AGENTS.md states that final-sale items cannot be refunded")
check("gift card" in low, "AGENTS.md states that gift cards cannot be refunded")
check("lead" in low, "AGENTS.md states the lead-approval rule")
check("integer cents" in low or "cents" in low, "AGENTS.md states that money is integer cents")
check(re.search(r"pytest", text) is not None, "AGENTS.md contains the test command")
check(re.search(r"sk-|password\s*=|api[_-]?key\s*=", low) is None, "AGENTS.md contains no secret-looking text")

claude_md = ROOT / "CLAUDE.md"
if claude_md.exists():
    check("@AGENTS.md" in read(claude_md), "CLAUDE.md imports AGENTS.md with @AGENTS.md")

for name, pattern in (("backend.md", "backend/"), ("frontend.md", "frontend/")):
    path = ROOT / ".claude" / "rules" / name
    body = read(path)
    check(path.exists(), f".claude/rules/{name} exists")
    front = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", body, re.S)
    check(bool(front) and "paths:" in front.group(1) and pattern in front.group(1),
          f".claude/rules/{name} has a paths: frontmatter that points at {pattern}")

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL CHECKS PASSED")
