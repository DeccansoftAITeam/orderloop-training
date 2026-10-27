"""Check for Lab 3 (Skills: build one). Standard library only.

Run from the repository root:  python scripts/check_lab03.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in [l.strip() for l in lines[1:]]:
        return {}
    end = [l.strip() for l in lines[1:]].index("---") + 1
    fields = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
check(branch != "main", f"you are on your own branch, not main (on '{branch}')")

rule = SKILLS / "add-refund-rule" / "SKILL.md"
check(rule.exists(), ".claude/skills/add-refund-rule/SKILL.md exists")
if rule.exists():
    fm = frontmatter(rule)
    check(bool(fm), "add-refund-rule has valid frontmatter between --- lines")
    desc = fm.get("description", "")
    check(len(desc) >= 40 and "refund" in desc.lower(), "description says what it does and when to use it (mentions refund)")
    check("disable-model-invocation" not in fm, "add-refund-rule can be invoked by the model")
    body = rule.read_text(encoding="utf-8")
    check("checklist.md" in body and (rule.parent / "checklist.md").exists(), "SKILL.md points to a checklist.md that exists")

summary = SKILLS / "pr-summary" / "SKILL.md"
check(summary.exists(), ".claude/skills/pr-summary/SKILL.md exists")
if summary.exists():
    fm = frontmatter(summary)
    body = summary.read_text(encoding="utf-8")
    check(fm.get("disable-model-invocation", "").lower() == "true", "pr-summary is user-invoked only (disable-model-invocation: true)")
    check("!`" in body, "pr-summary injects live git output with !`command`")
    check("$ARGUMENTS" in body, "pr-summary uses $ARGUMENTS")
    check("allowed-tools" in fm, "pr-summary pre-approves its git commands with allowed-tools")

log = subprocess.run(["git", "log", "--oneline", "main..HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
check(bool(log), "at least one commit on your branch")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
