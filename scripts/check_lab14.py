"""Check for Lab 14 (Agent teams). Standard library only.

Run from the repository root:  python scripts/check_lab14.py

Agent teams are interactive-only, so this script cannot see your team. It checks the
artefacts you leave behind: the team report, the fixed code, and your tests.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
REPORT = ROOT / "docs" / "team-review" / "report.md"
TEST_FILE = BACKEND / "tests" / "test_refund_digest.py"
failures: list[str] = []

# The module exactly as it shipped (used to prove your tests can fail).
BASELINE = '''
import logging
log = logging.getLogger("refund_digest")
LARGE_REFUND_CENTS = 20000


def build_digest(refunds, customers):
    total = 0
    for r in refunds:
        total += r["amount_cents"]
    average_cents = total / len(refunds)
    by_customer = {}
    for r in refunds:
        for c in customers:
            if c["id"] == r["customer_id"]:
                log.info("refund %s for %s <%s>: %s cents", r["id"], c["name"], c["email"], r["amount_cents"])
                by_customer[c["email"]] = by_customer.get(c["email"], 0) + r["amount_cents"]
    large = [r["id"] for r in refunds if r["amount_cents"] >= LARGE_REFUND_CENTS]
    return {"count": len(refunds), "total_cents": total, "average_cents": average_cents,
            "by_customer": by_customer, "large": large}
'''


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the team report ------------------------------------------------------
check(REPORT.exists(), "docs/team-review/report.md exists")
text = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""


def section(name: str) -> str:
    m = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, re.S | re.M | re.I)
    return m.group(1) if m else ""


check(bool(re.search(r"^Mode:\s*(team|fallback)\s*$", text, re.M | re.I)),
      "the report says 'Mode: team' or 'Mode: fallback' (fallback = no team was possible, subagents used)")
check(bool(re.search(r"^Display mode:\s*\S+", text, re.M | re.I)), "the report has a 'Display mode:' line")

team = section("Team")
rows = [l for l in team.splitlines() if l.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", l)]
check(len(rows) - 1 >= 3, f"the Team table lists at least 3 members besides its header (found {max(len(rows) - 1, 0)})")

findings = section("Findings")
subs = re.split(r"^###\s+.*$", findings, flags=re.M)[1:]
check(len(subs) >= 3, f"Findings has at least 3 angle sub-sections (### ...) (found {len(subs)})")
rated = [len(re.findall(r"^\s*-\s*\[(?:H|M|L)\]\s+\S", s, re.M)) for s in subs]
check(len([n for n in rated if n >= 2]) >= 3,
      "at least 3 angles list 2 or more findings as '- [H] ...', '- [M] ...' or '- [L] ...'")

topics = {
    "empty list / divide by zero": ("empty", "zero", "divid"),
    "average is a float (money)": ("float", "integer", "//"),
    "personal data in the log": ("log", "pii", "personal"),
    "email as a key": ("email", "key"),
    "unknown customer dropped": ("unknown", "missing", "dropped"),
    "large-refund boundary": ("20000", "20,000", "boundary", "strict", ">="),
    "slow nested loop": ("nested", "o(n", "quadratic", "lookup", "slow"),
}
hit = [k for k, words in topics.items() if any(w in findings.lower() for w in words)]
check(len(hit) >= 5, f"the findings cover at least 5 of the 7 real problems in the code (covered {len(hit)})")

debate = section("Debate")
check(bool(re.search(r"^Challenged finding:\s*\S.{9,}", debate, re.M | re.I)), "Debate names a 'Challenged finding:'")
check(bool(re.search(r"^Challenged by:\s*\S+", debate, re.M | re.I)), "Debate names who challenged it ('Challenged by:')")
check(bool(re.search(r"^Outcome:\s*(kept|withdrawn|changed)\b", debate, re.M | re.I)),
      "Debate has 'Outcome: kept', 'withdrawn' or 'changed'")

cost = section("Cost and cleanup")
check(bool(re.search(r"^Teammates spawned:\s*\d+", cost, re.M | re.I)), "Cost and cleanup has 'Teammates spawned: <number>'")
check(bool(re.search(r"^Teammates shut down:\s*(yes|no)\b", cost, re.M | re.I)),
      "Cost and cleanup has 'Teammates shut down: yes' or 'no'")
check(bool(re.search(r"^Cost note:\s*\S.{20,}", cost, re.M | re.I)), "Cost and cleanup has a 'Cost note:' of at least a sentence")

decision = section("Decision")
fixes = re.findall(r"^\s*-\s*Fix:\s*\S{5,}", decision, re.M | re.I)
check(len(fixes) >= 3, f"Decision lists at least 3 '- Fix: ...' items (found {len(fixes)})")

# --- behaviour of the fixed module ---------------------------------------
PROBE = r"""
import io, json, logging, sys, time
sys.path.insert(0, sys.argv[1])
stream = io.StringIO()
logging.basicConfig(stream=stream, level=logging.DEBUG)
from app.refund_digest import build_digest
cs = [{"id": "C1", "name": "Asha Verma", "email": "asha.verma@example.test"},
      {"id": "C2", "name": "Ben Ortiz", "email": "ben.ortiz@example.test"}]
def R(i, c, a): return {"id": i, "customer_id": c, "amount_cents": a, "reason": "damaged"}
out = {}
def attempt(name, fn):
    try:
        out[name] = fn()
    except Exception as exc:
        out[name] = "ERR " + type(exc).__name__
attempt("empty", lambda: build_digest([], cs))
attempt("avg", lambda: build_digest([R("a", "C1", 1001), R("b", "C2", 1002)], cs))
attempt("unknown", lambda: build_digest([R("a", "C1", 700), R("b", "C9", 500)], cs))
attempt("boundary", lambda: build_digest([R("eq", "C1", 20000), R("over", "C1", 20001)], cs))
attempt("log", lambda: build_digest([R("a", "C1", 700), R("b", "C2", 100)], cs)["total_cents"])
out["logtext"] = stream.getvalue()
big_c = [{"id": "C%d" % i, "name": "N%d" % i, "email": "n%d@example.test" % i} for i in range(4000)]
big_r = [R("R%d" % i, "C%d" % ((i * 7) % 4000), 100 + i % 50) for i in range(4000)]
t = time.perf_counter()
build_digest(big_r, big_c)
out["seconds"] = time.perf_counter() - t
print(json.dumps(out))
"""
probe = subprocess.run([sys.executable, "-c", PROBE, str(BACKEND)], capture_output=True, text=True, timeout=120)
res: dict = {}
try:
    res = json.loads(probe.stdout.strip().splitlines()[-1])
except Exception:
    last = (probe.stderr.strip().splitlines() or ["no output"])[-1]
    check(False, f"refund_digest.py can be imported and run ({last})")

if res:
    e = res.get("empty")
    check(isinstance(e, dict) and e.get("average_cents") == 0 and e.get("count") == 0 and e.get("total_cents") == 0
          and e.get("by_customer") == {} and e.get("large") == [],
          "an empty day gives count 0, total 0, average 0 and no crash")
    a = res.get("avg")
    check(isinstance(a, dict) and a.get("average_cents") == 1001 and isinstance(a.get("average_cents"), int),
          "average_cents is an integer (1001 and 1002 average to 1001)")
    u = res.get("unknown")
    check(isinstance(u, dict) and u.get("by_customer") == {"C1": 700, "unknown": 500},
          "by_customer uses customer ids and puts unmatched customers under 'unknown'")
    check(isinstance(u, dict) and sum(u.get("by_customer", {}).values()) == u.get("total_cents"),
          "the by_customer parts add up to total_cents")
    b = res.get("boundary")
    check(isinstance(b, dict) and b.get("large") == ["over"], "exactly 20000 cents is not large; 20001 is")
    lt = res.get("logtext", "")
    check(not any(s in lt for s in ("Asha", "Ben Ortiz", "example.test")), "the log holds no customer name or e-mail")
    secs = res.get("seconds")
    check(isinstance(secs, float) and secs < 0.4,
          f"4000 refunds x 4000 customers run fast (took {secs if secs is None else round(secs, 2)}s, limit 0.4s)")

# --- tests ----------------------------------------------------------------
n_tests = len(re.findall(r"^def test_", TEST_FILE.read_text(encoding="utf-8"), re.M)) if TEST_FILE.exists() else 0
check(n_tests >= 6, f"backend/tests/test_refund_digest.py has at least 6 tests (found {n_tests})")
suite = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"], cwd=BACKEND, capture_output=True, text=True)
check(suite.returncode == 0, "the backend test suite passes")

tmp = Path(tempfile.mkdtemp(prefix="lab14-"))
try:
    (tmp / "app").mkdir()
    (tmp / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp / "app" / "refund_digest.py").write_text(BASELINE, encoding="utf-8")
    shutil.copy(BACKEND / "app" / "rules.py", tmp / "app" / "rules.py")
    if TEST_FILE.exists():
        shutil.copy(TEST_FILE, tmp / "test_refund_digest.py")
    old = subprocess.run(
        ["uv", "run", "--project", str(BACKEND), "pytest", "-q", "-p", "no:cacheprovider",
         "--rootdir", str(tmp), str(tmp / "test_refund_digest.py")],
        cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(tmp)},
    )
    m = re.search(r"(\d+) failed", old.stdout)
    failed = int(m.group(1)) if m else 0
    check(failed >= 3, f"your tests catch the original flaws: {failed} fail on the original code (need at least 3)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- git hygiene ----------------------------------------------------------
tracked = git("ls-files", "docs/team-review/report.md", "backend/app/refund_digest.py", "backend/tests/test_refund_digest.py")
check(len(tracked.splitlines()) == 3 and "report.md" in tracked, "report, module and tests are tracked by git")
check(bool(git("log", "--oneline", "--", "docs/team-review/report.md")), "you committed the report")
check(git("status", "--porcelain", "--", "docs", "backend") == "", "no uncommitted changes in docs/ and backend/")
check(git("ls-files", ".claude/settings.local.json") == "", ".claude/settings.local.json (the team switch) is not committed")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
