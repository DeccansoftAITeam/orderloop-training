"""Check for Lab 19 (Evals). Standard library only.

Run from the repository root:  python scripts/check_lab19.py

It never calls a model. It grades the recorded sample transcripts in evals/recorded/ with YOUR runner,
and also feeds your runner damaged copies of them to see that your graders can fail.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
RECORDED = EVALS / "recorded"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def replay(folder: Path) -> tuple[int, str]:
    runner = EVALS / "run_evals.py"
    if not runner.exists():
        return -1, ""
    try:
        proc = subprocess.run([sys.executable, str(runner), "--replay", str(folder)], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return -1, ""
    return proc.returncode, proc.stdout


def rate(out: str, label: str) -> str:
    m = re.search(rf"^{label}:\s*(\d+)/(\d+)", out, re.M)
    return f"{m.group(1)}/{m.group(2)}" if m else "none"


def edit(folder: Path, case: str, **changes) -> None:
    for path in folder.glob(f"{case}.*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data), encoding="utf-8")


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the golden set ---------------------------------------------------------------
recorded_ids = sorted({p.name.split(".")[0] for p in (RECORDED / "with-code").glob("*.json")})
check(len(recorded_ids) == 6, "six recorded cases ship with the lab")
cases_path = EVALS / "cases.json"
check(cases_path.exists(), "evals/cases.json exists")
cases = []
if cases_path.exists():
    try:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        check(isinstance(cases, list), "cases.json is a JSON list")
    except json.JSONDecodeError as exc:
        check(False, f"cases.json is valid JSON ({exc})")
if not isinstance(cases, list):
    cases = []
ids = [c.get("id") for c in cases if isinstance(c, dict)]
check(len(cases) == 6 and len(set(ids)) == 6, "cases.json holds exactly 6 cases with different ids")
check(sorted(i for i in ids if i) == recorded_ids, "the case ids match the recorded transcripts: " + ", ".join(recorded_ids))
fields_ok = bool(cases) and all(
    isinstance(c, dict) and all(k in c for k in ("id", "prompt", "expect", "max_turns", "max_cost_usd")) for c in cases
)
check(fields_ok, "every case has id, prompt, expect, max_turns and max_cost_usd")
check(fields_ok and all(c["max_turns"] <= 10 and c["max_cost_usd"] <= 0.5 for c in cases), "every case caps turns (10 or fewer) and cost ($0.50 or less)")
check(fields_ok and all("ANSWER" in c["prompt"] for c in cases), "every prompt asks for a final ANSWER line so a program can grade it")

# --- the runner source ---------------------------------------------------------------
runner = EVALS / "run_evals.py"
src = runner.read_text(encoding="utf-8") if runner.exists() else ""
check(runner.exists(), "evals/run_evals.py exists")
for needle in ("--output-format", "--max-turns", "--max-budget-usd", "--replay", "--dry-run"):
    check(needle in src, f"run_evals.py uses {needle}")
check("bypassPermissions" not in src and "dangerously-skip-permissions" not in src, "run_evals.py does not bypass permissions")

# --- replay grading -------------------------------------------------------------------
code, out = replay(RECORDED / "with-code")
check(code == 0 and rate(out, "PASS RATE") == "6/6", f"replay of recorded/with-code: PASS RATE 6/6 (got {rate(out, 'PASS RATE')})")
check("COST:" in out, "the report prints the total COST")
code, out = replay(RECORDED / "from-memory")
check(code == 0 and rate(out, "PASS RATE") == "1/6", f"replay of recorded/from-memory: PASS RATE 1/6 (got {rate(out, 'PASS RATE')})")

tmp = Path(tempfile.mkdtemp(prefix="lab19-"))
try:
    # graders must be able to fail: wrong answer, too many turns, error, too costly, missing file
    damaged = tmp / "damaged"
    shutil.copytree(RECORDED / "with-code", damaged)
    edit(damaged, "lead-threshold", result="Probably more.\nANSWER: 25000")
    edit(damaged, "reason-max", num_turns=99)
    edit(damaged, "gift-card", is_error=True, subtype="error_max_turns")
    edit(damaged, "window-days", total_cost_usd=5.0)
    for p in damaged.glob("late-code.*.json"):
        p.unlink()
    code, out = replay(damaged)
    check(code == 0 and rate(out, "PASS RATE") == "1/6",
          f"damaged transcripts (wrong answer, 99 turns, error, $5 cost, missing file): PASS RATE 1/6 (got {rate(out, 'PASS RATE')})")

    # one flaky run out of two: fails the case, but pass@k still counts it
    flaky = tmp / "flaky"
    shutil.copytree(RECORDED / "with-code", flaky)
    p = flaky / "day-30-late.2.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["result"] = "ANSWER: yes"
    p.write_text(json.dumps(data), encoding="utf-8")
    code, out = replay(flaky)
    check(rate(out, "PASS RATE") == "5/6" and rate(out, "PASS@K") == "6/6",
          f"one flaky run: PASS RATE 5/6 and PASS@K 6/6 (got {rate(out, 'PASS RATE')} and {rate(out, 'PASS@K')})")

    # an empty folder must score zero, not crash into a pass
    empty = tmp / "empty"
    empty.mkdir()
    code, out = replay(empty)
    check(code == 0 and rate(out, "PASS RATE") == "0/6", f"an empty folder scores 0/6, not a pass (got {rate(out, 'PASS RATE')})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- dry run calls nothing ------------------------------------------------------------
if runner.exists():
    before = set(EVALS.rglob("*.json"))
    dry = subprocess.run([sys.executable, str(runner), "--label", "check-dry", "--dry-run"], cwd=ROOT,
                         capture_output=True, text=True, timeout=60)
    shutil.rmtree(EVALS / "runs" / "check-dry", ignore_errors=True)
    check(dry.returncode == 0 and set(EVALS.rglob("*.json")) == before, "--dry-run exits 0 and writes no transcripts")
else:
    check(False, "--dry-run exits 0 and writes no transcripts")

# --- your results page -------------------------------------------------------------------
results = EVALS / "results.md"
body = results.read_text(encoding="utf-8") if results.exists() else ""
check(results.exists(), "evals/results.md exists")
check("with-code" in body and "from-memory" in body, "results.md names both versions: with-code and from-memory")
check(len(re.findall(r"PASS RATE", body)) >= 2, "results.md shows the pass rate of both versions")
check(re.search(r"^decision:\s*\S+", body, re.I | re.M) is not None, "results.md has a 'Decision:' line")
check(re.search(r"wrong reason|lucky guess", body, re.I) is not None, "results.md notes a pass that a code grader cannot explain (a lucky guess, the wrong reason)")

# --- committed ----------------------------------------------------------------------------
tracked = git("ls-files", "evals/cases.json", "evals/run_evals.py", "evals/results.md")
check(len(tracked.splitlines()) == 3, "cases.json, run_evals.py and results.md are tracked by git")
check(git("status", "--porcelain", "--", "evals") == "", "no uncommitted changes in evals/")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
