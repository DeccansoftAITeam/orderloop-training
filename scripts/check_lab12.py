"""Check for Lab 12 (Spec-driven development). Standard library only.

Run from the repository root:  python scripts/check_lab12.py

It reads your spec in docs/specs/, checks its structure (EARS criteria, grilled
open questions, work packages with disjoint files, risk tier), then checks that
the work package you finished is traceable: criterion -> test -> code, with the
tests written before the code.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SPECS = ROOT / "docs" / "specs"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def run(*cmd: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True)


def section(text: str, keyword: str) -> str:
    """Body of the first '## ' section whose heading contains keyword."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"#{1,3}\s*(\d+\.\s*)?" + keyword, line.lower()):
            body = []
            for nxt in lines[i + 1:]:
                if re.match(r"#{1,3}\s", nxt):
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


def table(body: str) -> list[dict[str, str]]:
    """Parse the first markdown table in body into rows keyed by lower-case header."""
    rows = [l.strip() for l in body.splitlines() if l.strip().startswith("|")]
    if len(rows) < 3:
        return []
    cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
    header = [h.lower() for h in cells(rows[0])]
    out = []
    for line in rows[2:]:
        values = cells(line)
        if len(values) == len(header):
            out.append(dict(zip(header, values)))
    return out


def col(row: dict[str, str], name: str) -> str:
    for key, value in row.items():
        if key.startswith(name):
            return value
    return ""


def empty(value: str) -> bool:
    return value.strip().strip("()").lower() in {"", "tbd", "todo", "?", "none yet", "n/a"}


branch = run("git", "branch", "--show-current").stdout.strip()
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the spec file ----------------------------------------------------------
specs = sorted(SPECS.glob("*.md")) if SPECS.exists() else []
check(len(specs) == 1, f"exactly one spec file in docs/specs/ (found {len(specs)})")
spec_path = specs[0] if specs else None
text = spec_path.read_text(encoding="utf-8") if spec_path else ""
low = text.lower()

check(bool(re.search(r"^status:\s*approved\s*$", text, re.M | re.I)), "spec header says 'Status: approved' (a human approved it)")
tier = re.search(r"^risk tier:\s*(\d)\s*$", text, re.M | re.I)
check(bool(tier) and tier.group(1) == "3", "spec header says 'Risk tier: 3' (this feature moves money)")
check(not re.search(r"\btbd\b", low) and not re.search(r"<[^>\n]{2,}>", text), "no TBD and no <placeholder> left in the spec")

for keyword in ("problem", "user stories", "acceptance criteria", "open questions", "design delta", "contracts", "work packages", "risk"):
    check(bool(section(text, keyword).strip()), f"spec has a non-empty '{keyword}' section")

stories = re.findall(r"^-\s*US-\d+:\s*as an? .+,\s*i want .+,\s*so that .+", text, re.M | re.I)
check(len(stories) >= 2, f"at least 2 user stories in 'As a ..., I want ..., so that ...' form (found {len(stories)})")

# --- acceptance criteria (EARS) ---------------------------------------------
criteria = table(section(text, "acceptance criteria"))
check(len(criteria) >= 5, f"at least 5 acceptance criteria (found {len(criteria)})")
ids = [col(r, "id") for r in criteria]
check(len(set(ids)) == len(ids) and all(re.fullmatch(r"AC-\d+", i) for i in ids), "criteria have unique ids AC-1, AC-2, ...")

def is_ears(text_: str) -> bool:
    t = text_.strip()
    return bool(re.search(r"\bshall\b", t, re.I)) and bool(re.match(r"(when|while|where|if|the)\b", t, re.I))

check(criteria and all(is_ears(col(r, "criterion")) for r in criteria), "every criterion contains SHALL (EARS form)")
texts = [col(r, "criterion") for r in criteria]
check(any(re.match(r"\s*when\b", t, re.I) for t in texts), "at least one WHEN (event) criterion")
check(any(re.match(r"\s*if\b.*\bthen\b", t, re.I) for t in texts), "at least one IF ... THEN (unwanted behaviour) criterion")
test_names = [col(r, "test") for r in criteria]
check(criteria and all(re.fullmatch(r"test_\w+", t) for t in test_names), "every criterion names its test (test_...)")
check(len(set(test_names)) == len(test_names), "no two criteria share a test name")

# --- open questions (grilled) -----------------------------------------------
questions = table(section(text, "open questions"))
check(len(questions) >= 3, f"at least 3 open questions recorded (found {len(questions)})")
check(questions and all(not empty(col(q, "owner")) for q in questions), "every question has an owner")
check(questions and all(not empty(col(q, "answer")) and len(col(q, "answer")) >= 10 for q in questions), "every question has a real answer")

# --- work packages ----------------------------------------------------------
packages = table(section(text, "work packages"))
check(len(packages) >= 3, f"at least 3 work packages (found {len(packages)})")
pkg_ids = [col(p, "id") for p in packages]
check(len(set(pkg_ids)) == len(pkg_ids) and all(re.fullmatch(r"WP-\d+", i) for i in pkg_ids), "packages have unique ids WP-1, WP-2, ...")
file_sets = [{f.strip() for f in col(p, "files").split(",") if f.strip()} for p in packages]
check(file_sets and all(file_sets), "every package lists the files it owns")
owned = [f for s in file_sets for f in s]
check(len(owned) == len(set(owned)), "no file is owned by two packages")
check(criteria and all(col(r, "package") in pkg_ids for r in criteria), "every criterion belongs to an existing package")
check(packages and all(not empty(col(p, "done")) for p in packages), "every package says when it is done")

gates = section(text, "risk")
check(len(re.findall(r"^-\s*G\d+:", gates, re.M)) >= 2 and "human" in gates.lower(), "at least 2 approval gates (G1, G2, ...) and a human named in them")
check(bool(section(text, "contracts").strip()) and "(" in section(text, "contracts"), "contracts section gives at least one signature or shape")

# --- the finished package: criterion -> test -> code -------------------------
test_src = {p: p.read_text(encoding="utf-8") for p in sorted((BACKEND / "tests").glob("test_*.py"))}
all_tests = {}
for path, src in test_src.items():
    for m in re.finditer(r"^def (test_\w+)\(.*?(?=^def |\Z)", src, re.M | re.S):
        all_tests[m.group(1)] = m.group(0)

done = [r for r in criteria if col(r, "status").lower() == "done"]
done_pkgs = {col(r, "package") for r in done}
finished = [pid for pid in done_pkgs
            if all(col(r, "status").lower() == "done" for r in criteria if col(r, "package") == pid)]
check(len(finished) == 1, f"exactly one work package is fully done (found {sorted(finished) or 'none'})")
check(len([r for r in done if col(r, "package") in finished]) >= 2, "the finished package has at least 2 criteria")
check(len(done) == len([r for r in done if col(r, "package") in finished]), "no criterion outside the finished package is marked done")

app_src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / "app").glob("*.py"))
for r in done:
    ac, name = col(r, "id"), col(r, "test")
    check(name in all_tests, f"{ac}: test {name} exists in backend/tests")
    check(ac in all_tests.get(name, ""), f"{ac}: the test mentions {ac} (comment or docstring)")
    check(re.search(re.escape(ac) + r"\b", app_src) is not None, f"{ac}: the code in backend/app mentions {ac}")

if done:
    names = " or ".join(col(r, "test") for r in done)
    res = run("uv", "run", "pytest", "-q", "-k", names, cwd=BACKEND)
    check(res.returncode == 0, "the tests of the done criteria pass")
res = run("uv", "run", "pytest", "-q", cwd=BACKEND)
check(res.returncode == 0, "the whole backend test suite passes")

# the contract: rules.requires_lead_approval(amount_cents) -> bool
sys.path.insert(0, str(BACKEND))
try:
    from app import rules  # noqa: E402
    fn = getattr(rules, "requires_lead_approval", None)
except Exception:
    fn = None
check(callable(fn), "rules.requires_lead_approval exists (the WP-1 contract)")
if callable(fn):
    check(fn(rules.LEAD_APPROVAL_THRESHOLD_CENTS) is False, "exactly the threshold needs no approval")
    check(fn(rules.LEAD_APPROVAL_THRESHOLD_CENTS + 1) is True, "one cent above the threshold needs approval")
    try:
        fn(150.5)
        raised = False
    except TypeError:
        raised = True
    except Exception:
        raised = False
    check(raised, "a non-integer amount raises TypeError")

# --- git: tests were committed before the code --------------------------------
base = "lab-12-start" if run("git", "rev-parse", "--verify", "-q", "lab-12-start").returncode == 0 else "main"
commits = run("git", "log", "--reverse", "--format=%H", f"{base}..HEAD").stdout.split()
check(len(commits) >= 3, f"at least 3 commits on your branch since {base} (spec, tests, code) (found {len(commits)})")

def files_of(sha: str) -> list[str]:
    return run("git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha).stdout.split()

first_test = next((i for i, c in enumerate(commits) if any(f.startswith("backend/tests/") for f in files_of(c))), None)
first_code = next((i for i, c in enumerate(commits) if any(f.startswith("backend/app/") for f in files_of(c))), None)
check(first_test is not None and first_code is not None and first_test < first_code, "the tests were committed in an earlier commit than the code (tests first)")
first_spec = next((i for i, c in enumerate(commits) if any(f.startswith("docs/specs/") for f in files_of(c))), None)
check(first_spec is not None and first_test is not None and first_spec <= first_test, "the spec was committed no later than the first test")
check(run("git", "status", "--porcelain", "--", "docs", "backend").stdout.strip() == "", "no uncommitted changes in docs/ and backend/")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
