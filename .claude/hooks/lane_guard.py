"""Lane guard: one policy for every parallel lane (PreToolUse on file edits).

A lane is a git branch named wp-a, wp-b, ... (or worktree-wp-a, which is what
`claude --worktree wp-a` creates). .claude/lanes.json lists the files each lane
owns. An edit outside the lane's files is denied. On any other branch the hook
does nothing, so it never gets in the way of normal work.

Test by hand:  LANE=wp-c python .claude/hooks/lane_guard.py < event.json
"""

import fnmatch
import json
import os
import subprocess
import sys


def git(cwd: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    return out.stdout.strip()


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def main() -> None:
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    cwd = event.get("cwd") or os.getcwd()
    target = (event.get("tool_input") or {}).get("file_path") or (event.get("tool_input") or {}).get("notebook_path")
    if not target:
        return

    top = git(cwd, "rev-parse", "--show-toplevel")
    lane = os.environ.get("LANE") or git(cwd, "branch", "--show-current").removeprefix("worktree-")
    if not top:
        return
    with open(os.path.join(top, ".claude", "lanes.json"), encoding="utf-8") as fh:
        lanes = json.load(fh)
    if lane not in lanes:
        return

    root = os.path.realpath(top)
    path = os.path.realpath(target if os.path.isabs(target) else os.path.join(cwd, target))
    if os.path.commonpath([root, path]) != root:
        deny(f"Lane {lane}: {target} is outside this worktree.")
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if not any(fnmatch.fnmatch(rel, pattern) for pattern in lanes[lane]):
        deny(f"Lane {lane} does not own {rel}. Owned: {', '.join(lanes[lane])}. Ask the lead to change the split.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # fail closed: a broken guard must not let edits through
        print(f"lane_guard failed: {exc}", file=sys.stderr)
        sys.exit(2)
