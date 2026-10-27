"""Run a headless review of the last commit and save the JSON result.

Usage (from the repository root):  python scripts/run_review.py

It runs the equivalent of:
  git show HEAD -- scripts/ai_gate.py | claude -p "<prompt>" --output-format json \
      --json-schema <scripts/review_schema.json> --max-turns 3 --tools "" --no-session-persistence
and writes what claude prints to docs/headless-run.json (UTF-8).
Arguments are passed as a list, so there is no shell quoting to get wrong on Windows.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (
    "You are a strict code reviewer. Review this diff for bugs and risks. "
    "Answer only with the structured result: a verdict and a list of findings."
)


def main() -> int:
    claude = shutil.which("claude")
    if not claude:
        print("claude is not on the PATH")
        return 2
    diff = subprocess.run(["git", "show", "HEAD", "--", "scripts/ai_gate.py"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8").stdout
    if not diff.strip():
        print("No diff for scripts/ai_gate.py in the last commit. Commit the gate script first.")
        return 2
    schema = json.dumps(json.loads((ROOT / "scripts" / "review_schema.json").read_text(encoding="utf-8")))
    cmd = [claude, "-p", PROMPT, "--output-format", "json", "--json-schema", schema,
           "--max-turns", "3", "--tools", "", "--no-session-persistence"]
    proc = subprocess.run(cmd, cwd=ROOT, input=diff, capture_output=True, text=True, encoding="utf-8", timeout=600)
    out = ROOT / "docs" / "headless-run.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(proc.stdout, encoding="utf-8")
    print(f"claude exit code: {proc.returncode}; wrote {out.relative_to(ROOT)} ({len(proc.stdout)} bytes)")
    if proc.stderr.strip():
        print("stderr:", proc.stderr.strip()[:500])
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
