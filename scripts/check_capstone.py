"""Check for the Capstone. Standard library only.

Run from the repository root:  python scripts/check_capstone.py

It checks the spec, the tests (and runs them), the guardrails, the CI file and
CAPSTONE.md. It cannot see GitHub: the green Actions run is checked by your trainer
from the pull request link in CAPSTONE.md.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []
PLACEHOLDER = re.compile(r"<[A-Za-z][^>\n]{2,}>")


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def pytest(*extra: str):
    if shutil.which("uv"):
        cmd = ["uv", "run", "pytest", "-q", *extra]
    else:
        cmd = [sys.executable, "-m", "pytest", "-q", *extra]
    try:
        return subprocess.run(cmd, cwd=ROOT / "backend", capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None


def section(text: str, heading: str) -> str | None:
    """Body of '## heading' up to the next '## ' heading, or None."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1).strip() if m else None


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- guardrails still in place ---------------------------------------------
settings_path = ROOT / ".claude" / "settings.json"
settings: dict = {}
try:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    check(True, ".claude/settings.json is valid JSON")
except Exception as exc:
    check(False, f".claude/settings.json is valid JSON ({exc})")
blob = json.dumps(settings)
for script in ("guard_secrets.py", "run_tests.py", "audit_log.py"):
    check(script in blob and (ROOT / ".claude" / "hooks" / script).exists(), f"hook {script} is still registered")
check("disableAllHooks" not in blob, "hooks are not disabled in the project settings")
check(any(".env" in r for r in settings.get("permissions", {}).get("deny", [])), "a deny rule for .env is still there")
check("bypassPermissions" not in blob, "no bypass mode in the project settings")
check(git("ls-files", ".env") == "" and git("ls-files", ".claude/audit.log") == "",
      ".env and the audit log are not tracked")

# --- CI file ---------------------------------------------------------------
ci = ROOT / ".github" / "workflows" / "ci.yml"
check(ci.exists(), ".github/workflows/ci.yml exists")
if ci.exists():
    text = ci.read_text(encoding="utf-8")
    check(re.search(r"^on:", text, re.M) is not None and "pull_request" in text, "the workflow runs on pull_request")
    check("pytest" in text, "the workflow runs the backend tests")
    check("npm run build" in text, "the workflow builds the frontend")

# --- spec ------------------------------------------------------------------
spec_dir = ROOT / "docs" / "specs"
specs = sorted(spec_dir.glob("*.md")) if spec_dir.exists() else []
check(len(specs) >= 1, "a spec exists in docs/specs/")
ac_ids: list[str] = []
if specs:
    spec = specs[0].read_text(encoding="utf-8")
    print(f"      (checking {specs[0].relative_to(ROOT).as_posix()})")
    for heading in ("Problem", "User stories", "Acceptance criteria", "Open questions", "Plan", "Approval"):
        body = section(spec, heading)
        check(body is not None and len(body) > 15, f"spec has a filled '## {heading}' section")
    check(not PLACEHOLDER.search(spec), "no template placeholders (<...>) left in the spec")
    ac_ids = sorted(set(re.findall(r"^\s*-\s*(AC-\d+)\s*:", spec, re.M)))
    check(len(ac_ids) >= 4, f"at least 4 criteria with ids AC-1, AC-2, ... (found {len(ac_ids)})")
    check(len(re.findall(r"shall", spec)) >= 4, "criteria use the EARS word 'shall'")
    check(re.search(r"\bIf\b[^\n]*\bthen\b[^\n]*\bshall\b", spec) is not None,
          "at least one unwanted-case criterion: 'If ..., then the system shall ...'")
    check(re.search(r"^Status:\s*Approved\s*$", spec, re.M) is not None, "spec says 'Status: Approved'")
    approved = re.search(r"^Approved by:\s*(\S.*)$", spec, re.M)
    check(approved is not None and "<" not in approved.group(1), "approval block names who approved")
    check(re.search(r"^Date:\s*\d{4}-\d{2}-\d{2}\s*$", spec, re.M) is not None,
          "approval block has a date (YYYY-MM-DD)")
    rows = [ln for ln in (section(spec, "Open questions") or "").splitlines()
            if ln.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln)]
    check(len(rows) >= 2 and all(len([c for c in r.split("|")[1:-1] if c.strip()]) >= 4 for r in rows[1:]),
          "open questions table has at least one row with question, owner and answer")

# --- tests -----------------------------------------------------------------
test_files = sorted((ROOT / "backend" / "tests").glob("test_capstone_*.py"))
check(len(test_files) >= 1, "backend/tests/test_capstone_<feature>.py exists")
if test_files:
    code = "\n".join(p.read_text(encoding="utf-8") for p in test_files)
    n_tests = len(re.findall(r"^\s*def test_", code, re.M))
    check(n_tests >= 4, f"at least 4 tests in the capstone test file (found {n_tests})")
    missing = [a for a in ac_ids
               if not re.search(rf"(?<![A-Za-z0-9]){a.replace('-', '[-_ ]?')}(?![0-9])", code, re.I)]
    check(bool(ac_ids) and not missing,
          "every AC id appears in a test name or docstring (ac1, AC-1 and ac_1 all count)" + (f" (missing: {', '.join(missing)})" if missing else ""))
    res = pytest(*[f"tests/{p.name}" for p in test_files])
    check(res is not None and res.returncode == 0, "the capstone tests pass")
    res = pytest()
    last = (res.stdout.strip().splitlines() or [""])[-1] if res else ""
    check(res is not None and res.returncode == 0, f"the whole backend suite passes ({last})")

# --- tests first, readable history ----------------------------------------
base = ""
for ref in ("capstone-start", "upstream/main", "origin/main", "main"):
    base = git("merge-base", "HEAD", ref)
    if base:
        break
if base:
    log = git("log", "--reverse", "--format=%H", f"{base}..HEAD").split()
    check(len(log) >= 3, f"at least 3 commits on your branch (found {len(log)})")

    def touches(commit: str, path: str) -> bool:
        return bool(git("diff-tree", "--no-commit-id", "--name-only", "-r", commit, "--", path))

    first_test = next((c for c in log if touches(c, "backend/tests/test_capstone_*")), None)
    first_app = next((c for c in log if touches(c, "backend/app")), None)
    check(first_test is not None and first_app is not None and log.index(first_test) < log.index(first_app),
          "tests were committed before the first change under backend/app (tests first)")
else:
    check(False, "found the commit your branch started from")
check(git("status", "--porcelain", "--", "backend", "docs", "CAPSTONE.md", ".github", ".claude") == "",
      "no uncommitted changes in backend, docs, CAPSTONE.md, .github or .claude")

# --- CAPSTONE.md -----------------------------------------------------------
cap = ROOT / "CAPSTONE.md"
check(cap.exists(), "CAPSTONE.md exists at the repository root")
if cap.exists():
    text = cap.read_text(encoding="utf-8")
    for heading in ("Feature", "What Claude got wrong", "Review findings", "Cost", "What I would change",
                    "Pull request"):
        body = section(text, heading)
        check(body is not None and len(body) >= 25, f"CAPSTONE.md has a filled '## {heading}' section")
    cost = section(text, "Cost") or ""
    check(re.search(r"\d", cost) is not None and re.search(r"\$|token|USD|seat|usage", cost, re.I) is not None,
          "the Cost section gives a number and its unit (dollars, tokens or seat usage)")
    pr = section(text, "Pull request") or ""
    check(re.search(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+", pr) is not None,
          "the Pull request section links your pull request (https://github.com/<you>/<repo>/pull/<n>)")
    check(not PLACEHOLDER.search(text), "no template placeholders (<...>) left in CAPSTONE.md")
    print("NOTE  Your trainer checks that the pull request shows a green Actions run.")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
