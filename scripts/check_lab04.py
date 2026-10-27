"""Check for Lab 4 (Skills: compose and test). Standard library only.

Run from the repository root:  python scripts/check_lab04.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=ROOT, capture_output=True, text=True)


def parse(path: Path) -> tuple[dict[str, str], str]:
    """Return (frontmatter fields, body). Empty fields if the frontmatter is invalid."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ""
    try:
        end = [l.strip() for l in lines[1:]].index("---") + 1
    except ValueError:
        return {}, ""
    fields = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[end + 1:])


branch = run("git", "branch", "--show-current").stdout.strip()
check(branch != "main", f"you are on your own branch, not main (on '{branch}')")

# --- Skill 1: refund-test-audit, a composite skill -------------------------
audit = SKILLS / "refund-test-audit" / "SKILL.md"
check(audit.exists(), ".claude/skills/refund-test-audit/SKILL.md exists")
if audit.exists():
    fm, body = parse(audit)
    check(bool(fm), "refund-test-audit has valid frontmatter between --- lines")
    check(len(fm.get("description", "")) >= 40, "description is a real sentence (40+ characters)")
    check("disable-model-invocation" not in fm, "refund-test-audit can be chosen by Claude")
    script = audit.parent / "scripts" / "list_rule_tests.py"
    check(script.exists(), "scripts/list_rule_tests.py exists in the skill folder")
    check("${CLAUDE_SKILL_DIR}" in body and "list_rule_tests.py" in body,
          "SKILL.md runs the script through ${CLAUDE_SKILL_DIR}")
    ref = audit.parent / "naming-rules.md"
    check(ref.exists() and "naming-rules.md" in body, "SKILL.md points to a naming-rules.md that exists")
    check("disallowed-tools" in fm, "the audit is read-only while it runs (disallowed-tools)")

    # Behavioural: the script must flag weak names and accept good ones.
    if script.exists():
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "test_good.py"
            good.write_text("def test_exactly_thirty_days_is_still_on_time(): pass\n", encoding="utf-8")
            r = run(sys.executable, str(script), tmp)
            check(r.returncode == 0, "script exits 0 when every test name states its behaviour")
            weak = Path(tmp) / "test_weak.py"
            weak.write_text("def test_refund_1(): pass\ndef test_late(): pass\n", encoding="utf-8")
            r = run(sys.executable, str(script), tmp)
            check(r.returncode == 1, "script exits 1 when a test name is weak")
            weak_lines = [l for l in r.stdout.splitlines() if l.startswith("WEAK")]
            check(len(weak_lines) == 2 and any("test_refund_1" in l for l in weak_lines)
                  and any("test_late" in l for l in weak_lines),
                  "script prints one WEAK line per weak test, and none for good names")

# --- Skill 2: review-refund-change, runs in its own context ----------------
review = SKILLS / "review-refund-change" / "SKILL.md"
check(review.exists(), ".claude/skills/review-refund-change/SKILL.md exists")
if review.exists():
    fm, body = parse(review)
    check(fm.get("context") == "fork", "review-refund-change runs in a forked context (context: fork)")
    check(fm.get("agent") == "Explore", "it uses the read-only Explore agent (agent: Explore)")
    check(fm.get("background", "").lower() == "false", "it waits for the result (background: false)")
    check("!`" in body, "it injects the real diff with !`command`")
    check("allowed-tools" in fm and "git diff" in fm["allowed-tools"], "the diff command is pre-approved")
    check(len(body.strip().splitlines()) >= 3, "the body is a full task, not just guidelines")

# --- The skill did its job on the repository -------------------------------
if audit.exists() and (audit.parent / "scripts" / "list_rule_tests.py").exists():
    r = run(sys.executable, str(audit.parent / "scripts" / "list_rule_tests.py"), "backend/tests")
    check(r.returncode == 0, "every test name in backend/tests now states its behaviour")

tests = subprocess.run(["uv", "run", "pytest", "-q"], cwd=ROOT / "backend", capture_output=True, text=True)
check(tests.returncode == 0, "backend tests still pass after the renames")

log = run("git", "log", "--oneline", "lab-04-start..HEAD").stdout.strip()
check(bool(log), "at least one commit on your branch")
status = run("git", "status", "--porcelain", ".claude").stdout.strip()
check(not status, ".claude is committed (nothing left uncommitted)")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
