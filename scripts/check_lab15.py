"""Check for Lab 15 (Legacy migration). Standard library only.

Run from the repository root:  python scripts/check_lab15.py

It proves four things: you wrote characterization tests BEFORE you migrated, the migrated job
prints exactly what the old job printed, no Python 2 idioms are left, and you left a rollback.
"""

import ast
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "legacy"
MODULES = ["legacy/settle.py", "legacy/money.py", "legacy/loader.py"]
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT, capture_output=True).returncode == 0


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- 1. does it run, and is the output identical to the golden files? -----
def run_job(date: str, data: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run([sys.executable, str(LEGACY / "settle.py"), date, str(data)],
                          capture_output=True, env=env, timeout=60)


def norm(b: bytes) -> str:
    return b.replace(b"\r\n", b"\n").decode("utf-8", "replace")


for golden in sorted((LEGACY / "golden").glob("settlement_*.txt")):
    date = golden.stem.split("_", 1)[1]
    res = run_job(date, LEGACY / "data")
    want = norm(golden.read_bytes())
    got = norm(res.stdout)
    check(res.returncode == 0 and got == want, f"report for {date} is identical to the golden file")
    if res.returncode == 0 and got != want:
        for n, (a, b) in enumerate(zip(got.splitlines(), want.splitlines()), 1):
            if a != b:
                print(f"      first difference, line {n}:\n        got:  {a}\n        want: {b}")
                break
    elif res.returncode != 0:
        tail = (res.stderr.decode("utf-8", "replace").strip().splitlines() or ["no error text"])[-1]
        print(f"      exit {res.returncode}: {tail}")

# --- 2. not just the two golden dates: a third run date vs an independent calculation ----
def independent(run_date: str, data: Path) -> dict:
    def table(name):
        lines = (data / name).read_text(encoding="utf-8").split("\n")
        head = lines[0].split(",")
        return [dict(zip(head, ln.split(","))) for ln in lines[1:] if ln]

    def num(s):
        try:
            return int(s)
        except ValueError:
            return None

    merchants = {m["id"]: m for m in table("merchants.csv")}
    res = {k: [0, 0, 0, 0] for k in merchants}  # orders, gross, refunds, fee
    ok_orders = {}
    for o in table("orders.csv"):
        a = num(o["amount_cents"])
        if a is None or o["date"] > run_date or o["status"].upper() != "PAID" or o["merchant_id"] not in merchants:
            continue
        r = res[o["merchant_id"]]
        r[0] += 1
        r[1] += a
        r[3] += math.floor(Fraction(a * int(merchants[o["merchant_id"]]["fee_bps"]), 10000))
        ok_orders[o["order_id"]] = o["merchant_id"]
    for f in table("refunds.csv"):
        a = num(f["amount_cents"])
        if a is None or f["date"] > run_date or f["order_id"] not in ok_orders:
            continue
        res[ok_orders[f["order_id"]]][2] += a
    return {"merchants": merchants, "res": res}


def money(c: int) -> str:
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100:,}.{c % 100:02d}"


THIRD = "2030-02-28"
res = run_job(THIRD, LEGACY / "data")
text = norm(res.stdout)
ok = res.returncode == 0
if ok:
    ind = independent(THIRD, LEGACY / "data")
    lines = text.splitlines()
    totals = [0, 0, 0, 0]
    partner = 0
    for mid, (n, g, rf, fee) in ind["res"].items():
        net = g - rf - fee
        name = ind["merchants"][mid]["name"][:16]
        row = next((ln for ln in lines if ln.startswith(name)), None)
        want = [str(n), money(g), money(rf), money(fee), money(net), str(math.floor(Fraction(net, 100)))]
        ok = ok and row is not None and row[len(name):].split()[1:] == want
        for i, v in enumerate((n, g, rf, fee)):
            totals[i] += v
        partner += math.floor(Fraction(fee, 2) + Fraction(1, 2))
    net_total = totals[1] - totals[2] - totals[3]
    expected_totals = (f"Totals: orders={totals[0]} gross={money(totals[1])} refunds={money(totals[2])} "
                       f"fee={money(totals[3])} net={money(net_total)}")
    ok = ok and expected_totals in lines and ("Partner share of fees: " + money(partner)) in lines
check(ok, f"a run date that has no golden file ({THIRD}) matches an independent calculation")

# --- 3. no Python 2 idioms left ----------------------------------------------
BANNED_NAMES = {"unicode", "basestring", "xrange", "long", "cmp", "reduce", "raw_input", "unichr", "execfile", "file"}
BANNED_ATTRS = {"has_key", "iteritems", "iterkeys", "itervalues", "maxint", "__cmp__"}
STRING_FUNCS = {"join", "upper", "lower", "split", "strip", "replace", "letters", "atoi"}
problems: list[str] = []
for rel in MODULES:
    path = ROOT / rel
    if not path.exists():
        problems.append(f"{rel} is missing")
        continue
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        problems.append(f"{rel} line {exc.lineno}: not valid Python 3 ({exc.msg})")
        continue
    if re.search(r"python2", src.splitlines()[0] if src else ""):
        problems.append(f"{rel}: shebang still says python2")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            problems.append(f"{rel} line {node.lineno}: '{node.id}' is Python 2")
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            problems.append(f"{rel} line {node.lineno}: '.{node.attr}' is Python 2")
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "string"
              and node.attr in STRING_FUNCS):
            problems.append(f"{rel} line {node.lineno}: string.{node.attr} is Python 2")
        elif isinstance(node, ast.Import) and any(a.name == "string" for a in node.names):
            problems.append(f"{rel} line {node.lineno}: 'import string' (module functions are gone in Python 3)")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "round":
            problems.append(f"{rel} line {node.lineno}: round() rounds halves to even in Python 3, not away from zero")
        elif isinstance(node, ast.Constant) and isinstance(node.value, bytes):
            problems.append(f"{rel} line {node.lineno}: bytes literal (text should be str)")
check(not problems, "no Python 2 idioms remain" + ("" if not problems else " (" + str(len(problems)) + " found)"))
for p in problems[:8]:
    print("      " + p)

# --- 4. characterization tests exist, pass, and have teeth ---------------------
tests = LEGACY / "tests"
test_money, test_golden = tests / "test_money.py", tests / "test_golden.py"
count = sum(len(re.findall(r"^def test_", p.read_text(encoding="utf-8"), re.M)) for p in tests.glob("test_*.py")) if tests.exists() else 0
check(test_money.exists() and test_golden.exists(), "legacy/tests/test_money.py and legacy/tests/test_golden.py exist")
check(count >= 8, f"at least 8 characterization tests (found {count})")
suite = subprocess.run(["uv", "run", "--project", str(ROOT / "backend"), "pytest", "-q", "-p", "no:cacheprovider"],
                       cwd=LEGACY, capture_output=True, text=True)
check(suite.returncode == 0 and "passed" in suite.stdout, "the characterization tests pass on the migrated job")

NAIVE_MONEY = '''
def fee_for_order(amount_cents, fee_bps):
    return int(amount_cents * fee_bps / 10000)

def split_fee(fee_cents):
    return round(fee_cents / 2)

def whole_units(cents):
    return int(cents / 100)

def fmt_money(cents):
    return "%d.%02d" % (cents / 100, cents % 100)
'''
tmp = Path(tempfile.mkdtemp(prefix="lab15-"))
try:
    (tmp / "money.py").write_text(NAIVE_MONEY, encoding="utf-8")
    if test_money.exists():
        shutil.copy(test_money, tmp / "test_money.py")
    old = subprocess.run(
        ["uv", "run", "--project", str(ROOT / "backend"), "pytest", "-q", "-p", "no:cacheprovider",
         "--rootdir", str(tmp), str(tmp / "test_money.py")],
        cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(tmp)})
    m = re.search(r"(\d+) failed", old.stdout)
    failed = int(m.group(1)) if m else 0
    check(failed >= 3, f"test_money.py catches a naive port (round(), int(), no commas): {failed} tests fail on it, need at least 3")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- 5. order of work, small steps, rollback ------------------------------------
base = ""
for ref in ("lab-15-start", "origin/main", "main"):
    base = git("merge-base", "HEAD", ref)
    if base:
        break
rev = ["git", "rev-list", "--reverse", f"{base}..HEAD", "--"] if base else None
first_test = migrate = []
if rev:
    first_test = subprocess.run(rev + ["legacy/tests"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    migrate = subprocess.run(rev + MODULES, cwd=ROOT, capture_output=True, text=True).stdout.split()
check(bool(first_test) and bool(migrate) and first_test[0] != migrate[0] and is_ancestor(first_test[0], migrate[0]),
      "you committed the tests BEFORE the first change to settle.py, money.py or loader.py")
check(len(migrate) >= 3, f"the migration is at least 3 small commits (found {len(migrate)})")

tag_commit = git("rev-parse", "--verify", "-q", "settle-py2-last^{commit}")
old_src = git("show", "settle-py2-last:legacy/settle.py") if tag_commit else ""
check(bool(tag_commit) and "print '" in old_src and bool(base) and is_ancestor(tag_commit, "HEAD"),
      "the git tag 'settle-py2-last' marks the last Python 2 version (your rollback point)")

note = LEGACY / "MIGRATION.md"
nt = note.read_text(encoding="utf-8") if note.exists() else ""


def part(name: str) -> str:
    m = re.search(rf"^##\s+{name}\s*$(.*?)(?=^##\s|\Z)", nt, re.S | re.M | re.I)
    return m.group(1) if m else ""


check(bool(re.search(r"^Tier:\s*(low|medium|high)\b", part("Risk tier"), re.M | re.I)),
      "legacy/MIGRATION.md: 'Risk tier' has a line 'Tier: low', 'medium' or 'high'")
check(len(part("Evidence").strip()) >= 40 and "golden" in part("Evidence").lower(),
      "legacy/MIGRATION.md: 'Evidence' says how equivalence was shown (mentions the golden files)")
check("settle-py2-last" in part("Rollback") and len(part("Rollback").strip()) >= 40,
      "legacy/MIGRATION.md: 'Rollback' names the tag settle-py2-last and says what to do")

# --- git hygiene -------------------------------------------------------------------
tracked = git("ls-files", "legacy/tests/test_money.py", "legacy/tests/test_golden.py", "legacy/MIGRATION.md")
check(len(tracked.splitlines()) == 3, "tests and MIGRATION.md are tracked by git")
check(git("status", "--porcelain", "--", "legacy") == "", "no uncommitted changes in legacy/")
check(git("ls-files", "legacy").count("__pycache__") == 0, "no __pycache__ committed")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
