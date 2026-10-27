"""A tiny eval runner for OrderLoop refund-rule questions. Standard library only.

Live run (calls a model, costs money):
    python evals/run_evals.py --label with-code --tools Read,Grep,Glob --runs 2
    python evals/run_evals.py --label try --only window-days,gift-card

Replay (no model, free, deterministic): grade transcripts that were recorded earlier
    python evals/run_evals.py --replay evals/recorded/from-memory

Print the commands without running anything:
    python evals/run_evals.py --label with-code --tools Read --dry-run

Each live run saves the raw `claude -p --output-format json` result as
evals/runs/<label>/<case-id>.<n>.json. Replay reads the same files.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(__file__).resolve().parent / "cases.json"


def load_cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def grade(case: dict, out: dict) -> dict[str, bool]:
    """Code-based graders. Every check is a plain yes or no."""
    reply = str(out.get("result", ""))
    answers = re.findall(r"^ANSWER:\s*(.+?)\s*$", reply, re.M)
    answer = answers[-1].strip("`*. ") if answers else ""
    return {
        "finished": out.get("subtype") == "success" and not out.get("is_error"),
        "answer": re.fullmatch(case["expect"], answer, re.I) is not None,
        "turns": (out.get("num_turns") or 999) <= case["max_turns"],
        "cost": (out.get("total_cost_usd") or 0.0) <= case["max_cost_usd"],
    }


def command_for(case: dict, tools: str, extra: str) -> list[str]:
    claude = shutil.which("claude") or "claude"
    command = [
        claude, "-p", case["prompt"], "--output-format", "json",
        "--max-turns", str(case["max_turns"]), "--max-budget-usd", "0.40",
        "--safe-mode", "--no-session-persistence",
    ]
    if extra:
        command += ["--append-system-prompt", extra]
    return command + ["--tools", tools]


def run_live(cases: list[dict], label: str, tools: str, extra: str, runs: int, dry: bool) -> Path:
    folder = Path(__file__).resolve().parent / "runs" / label
    folder.mkdir(parents=True, exist_ok=True)
    for case in cases:
        for n in range(1, runs + 1):
            command = command_for(case, tools, extra)
            if dry:
                print("DRY RUN:", " ".join(f'"{c}"' if " " in c or c == "" else c for c in command[:3]), "...")
                continue
            print(f"running {case['id']} #{n} ...", flush=True)
            try:
                proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=150, stdin=subprocess.DEVNULL)
                data = json.loads(proc.stdout)
            except subprocess.TimeoutExpired:
                data = {"is_error": True, "subtype": "timeout", "result": "killed after 150 seconds"}
            except json.JSONDecodeError:
                data = {"is_error": True, "subtype": "no_json", "result": proc.stderr[-300:]}
            (folder / f"{case['id']}.{n}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


def load_runs(folder: Path, case_id: str) -> list[dict]:
    runs = []
    for path in sorted(folder.glob(f"{case_id}.*.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            runs.append({"is_error": True, "subtype": "bad_json"})
    return runs


def report(cases: list[dict], folder: Path) -> None:
    print(f"\nResults for {folder.name}")
    print(f"{'case':<16}{'runs':>5}{'passed':>8}{'pass@k':>8}{'all-k':>7}{'turns':>7}{'cost':>9}  failed checks")
    any_pass = all_pass = 0
    total_cost = 0.0
    total_runs = passed_runs = 0
    for case in cases:
        runs = load_runs(folder, case["id"])
        graded = [grade(case, r) for r in runs]
        ok = [all(g.values()) for g in graded]
        failed = sorted({k for g in graded for k, v in g.items() if not v})
        cost = sum(r.get("total_cost_usd") or 0.0 for r in runs)
        turns = max([r.get("num_turns") or 0 for r in runs], default=0)
        total_cost += cost
        total_runs += len(runs)
        passed_runs += sum(ok)
        any_pass += bool(ok) and any(ok)
        all_pass += bool(ok) and all(ok)
        print(f"{case['id']:<16}{len(runs):>5}{sum(ok):>8}{'yes' if ok and any(ok) else 'no':>8}"
              f"{'yes' if ok and all(ok) else 'no':>7}{turns:>7}{cost:>9.4f}  {', '.join(failed) or '-'}")
    n = len(cases)
    print(f"\nPASS RATE: {all_pass}/{n} ({round(100 * all_pass / n)}%)  [a case passes when every run of it passes]")
    print(f"PASS@K:    {any_pass}/{n}  [a case passes when at least one run passes]")
    print(f"RUNS:      {passed_runs}/{total_runs} passed")
    print(f"COST:      ${total_cost:.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replay", metavar="FOLDER", help="grade recorded transcripts in FOLDER; call no model")
    parser.add_argument("--label", help="name for a live run; results go to evals/runs/<label>")
    parser.add_argument("--tools", default="Read,Grep,Glob", help='tools the agent may use; "" means none')
    parser.add_argument("--system-extra", default="", help="text added to the system prompt (the 'version B' of a prompt)")
    parser.add_argument("--runs", type=int, default=1, help="runs per case (flaky behaviour needs more than one)")
    parser.add_argument("--only", help="comma-separated case ids to run live (saves money while you experiment)")
    parser.add_argument("--dry-run", action="store_true", help="show the commands, run nothing")
    args = parser.parse_args()
    cases = load_cases()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    if args.replay:
        report(cases, Path(args.replay))
        return 0
    if not args.label:
        parser.error("give --label for a live run, or --replay FOLDER")
    folder = run_live(cases, args.label, args.tools, args.system_extra, args.runs, args.dry_run)
    if not args.dry_run:
        report(cases, folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
