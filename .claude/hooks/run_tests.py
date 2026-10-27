"""PostToolUse hook: run the backend tests after an edit under backend/app.

Passing tests are silent. Failing tests are fed back to Claude.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        edited = Path(event["tool_input"]["file_path"]).as_posix()
    except Exception:
        sys.exit(0)  # not our input; do nothing

    if "/backend/app/" not in edited:
        sys.exit(0)

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    try:
        run = subprocess.run(
            ["uv", "run", "pytest", "-q", "-x", "--tb=short"],
            cwd=root / "backend", capture_output=True, text=True, timeout=100,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"run_tests.py could not run the tests: {exc}", file=sys.stderr)
        sys.exit(1)  # non-blocking error: shown, the session continues

    if run.returncode == 0:
        sys.exit(0)

    tail = "\n".join((run.stdout + run.stderr).strip().splitlines()[-30:])
    print(json.dumps({
        "decision": "block",
        "reason": f"The backend tests fail after your edit. Fix the cause, do not loosen a test.\n{tail}",
    }))
    sys.exit(0)


main()
