"""Check for Lab 2 (Plan, implement, verify). Standard library only.

Run from the repository root:  python scripts/check_lab02.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def run(*cmd: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True)


branch = run("git", "branch", "--show-current").stdout.strip()
check(branch != "main", f"you are on your own branch, not main (on '{branch}')")

tests = (BACKEND / "tests" / "test_rules.py").read_text(encoding="utf-8")
count = sum(1 for line in tests.splitlines() if line.startswith("def test_") and "restocking" in line.lower())
check(count >= 3, f"at least 3 restocking tests in test_rules.py (found {count})")

probe = (
    "from datetime import datetime, timedelta\n"
    "from app import rules\n"
    "now = datetime(2030, 3, 1)\n"
    "item = rules.Item('S', 'Stove', 6000, 1, opened=True)\n"
    "el = rules.eligibility(now - timedelta(days=20), [item], 0, now)\n"
    "print(el.max_refundable_cents, getattr(el, 'restocking_fee_cents', None))\n"
)
result = run("uv", "run", "python", "-c", probe, cwd=BACKEND)
out = result.stdout.split()
check(out[:1] == ["5400"], "an opened $60 item 20 days after delivery refunds 5400 cents")
check(out[1:2] == ["600"], "eligibility reports restocking_fee_cents = 600")

tests_run = run("uv", "run", "pytest", "-q", cwd=BACKEND)
check(tests_run.returncode == 0, "the whole backend test suite passes")

log = run("git", "log", "--oneline", "main..HEAD").stdout.strip().splitlines()
check(len(log) >= 1, "at least one commit on your branch")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
