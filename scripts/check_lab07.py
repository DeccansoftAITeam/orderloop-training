"""Check for Lab 7 (Hooks). Standard library only.

Run from the repository root:  python scripts/check_lab07.py

It reads .claude/settings.json, then feeds sample hook input (JSON on stdin)
to your hook scripts and checks the exit codes and decisions.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def run_hook(script: str, payload, project_dir: Path = ROOT, timeout: int = 180):
    """Run a hook script the way Claude Code does: JSON on stdin, project dir in env."""
    path = HOOKS / script
    if not path.exists():
        return None
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    data = payload if isinstance(payload, str) else json.dumps(payload)
    try:
        return subprocess.run(
            [sys.executable, str(path)], input=data, capture_output=True, text=True,
            cwd=project_dir, env=env, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None


def denies(result) -> bool:
    """True if the hook blocks: exit code 2 with a reason, or JSON permissionDecision 'deny'."""
    if result is None:
        return False
    if result.returncode == 2 and result.stderr.strip():
        return True
    try:
        out = json.loads(result.stdout)
        return result.returncode == 0 and out["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        return False


def allows(result) -> bool:
    return result is not None and result.returncode == 0 and "deny" not in result.stdout


def bash(command: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(ROOT)}


def read(path: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path}, "cwd": str(ROOT)}


def edit(path: str) -> dict:
    return {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": path}, "tool_response": {}}


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- settings.json -------------------------------------------------------
settings_path = ROOT / ".claude" / "settings.json"
check(settings_path.exists(), ".claude/settings.json exists")
settings: dict = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        check(True, "settings.json is valid JSON")
    except json.JSONDecodeError as exc:
        check(False, f"settings.json is valid JSON ({exc})")


def entries(event: str) -> list[dict]:
    found = []
    for group in settings.get("hooks", {}).get(event, []):
        for hook in group.get("hooks", []):
            found.append({"matcher": group.get("matcher", "*"), **hook})
    return found


def uses(entry: dict, script: str) -> bool:
    return script in json.dumps(entry)


pre, post = entries("PreToolUse"), entries("PostToolUse")
guard = next((e for e in pre if uses(e, "guard_secrets.py")), None)
check(guard is not None and guard.get("type") == "command", "PreToolUse runs guard_secrets.py as a command hook")
if guard:
    check("Bash" in guard["matcher"] and "Read" in guard["matcher"], "the guard matcher covers Bash and Read")
    check(guard.get("onFailure") == "block", 'the guard sets "onFailure": "block" (fails closed)')
    check("CLAUDE_PROJECT_DIR" in json.dumps(guard), "the guard path starts from CLAUDE_PROJECT_DIR")
tests_hook = next((e for e in post if uses(e, "run_tests.py")), None)
check(tests_hook is not None, "PostToolUse runs run_tests.py")
if tests_hook:
    check("Edit" in tests_hook["matcher"], "the test hook matcher covers Edit")
    check(isinstance(tests_hook.get("timeout"), int), "the test hook sets a timeout")
audit = next((e for e in pre + post if uses(e, "audit_log.py")), None)
check(audit is not None, "audit_log.py is registered as a hook")
if audit:
    check(audit.get("onFailure") != "block", "the audit hook fails open (no onFailure: block)")

# --- guard_secrets.py ----------------------------------------------------
env_path = str(ROOT / ".env")
csv_path = str(ROOT / "seed" / "customers.csv")
rules_path = str(ROOT / "backend" / "app" / "rules.py")
for label, payload in [
    ("Read of .env", read(env_path)),
    ("Read of seed/customers.csv", read(csv_path)),
    ("cat .env", bash("cat .env")),
    ("head seed/customers.csv", bash("head -3 seed/customers.csv")),
    ("grep -rn ... . (the Lab 6 gap)", bash("grep -rn ORDERLOOP_FAKE_KEY .")),
    ("rg KEY (recursive by default)", bash("rg KEY")),
    ("a python one-liner that opens .env", bash("python -c \"print(open('.env').read())\"")),
]:
    check(denies(run_hook("guard_secrets.py", payload)), f"guard blocks: {label}")
for label, payload in [
    ("Read of backend/app/rules.py", read(rules_path)),
    ("cat .env.example", bash("cat .env.example")),
    ("cd backend && uv run pytest -q", bash("cd backend && uv run pytest -q")),
    ("grep -rn refund backend/app", bash("grep -rn refund backend/app")),
    ("git status", bash("git status")),
]:
    check(allows(run_hook("guard_secrets.py", payload)), f"guard allows: {label}")
bad = run_hook("guard_secrets.py", "this is not json")
check(bad is not None and bad.returncode == 2, "guard fails closed on unreadable input (exit 2)")
blocked = run_hook("guard_secrets.py", read(env_path))
check(blocked is not None and len((blocked.stderr + blocked.stdout).strip()) > 20, "the block message gives a reason")

# --- run_tests.py --------------------------------------------------------
skip = run_hook("run_tests.py", edit(str(ROOT / "README.md")))
check(skip is not None and skip.returncode == 0 and not skip.stdout.strip(), "test hook ignores edits outside backend/app")
ok = run_hook("run_tests.py", edit(rules_path))
check(ok is not None and ok.returncode == 0 and "block" not in ok.stdout, "test hook is silent when the tests pass")

tmp = Path(tempfile.mkdtemp(prefix="lab07-"))
try:
    if (HOOKS / "run_tests.py").exists():
        shutil.copytree(ROOT / "backend", tmp / "backend",
                        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
        with (tmp / "backend" / "app" / "rules.py").open("a", encoding="utf-8") as f:
            f.write("\nraise RuntimeError('lab07 deliberate break')\n")
    broken = run_hook("run_tests.py", edit(str(tmp / "backend" / "app" / "rules.py")), project_dir=tmp)
    fed_back = False
    if broken is not None:
        try:
            out = json.loads(broken.stdout)
            fed_back = out.get("decision") == "block" and "RuntimeError" in out.get("reason", "")
        except Exception:
            fed_back = broken.returncode == 2 and "RuntimeError" in broken.stderr
    check(fed_back, "test hook feeds failing output back to Claude (decision block, or exit 2 with stderr)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- audit_log.py --------------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="lab07-"))
try:
    secret_cmd = "curl -d 'asha.verma@example.test +1-555-0101 ORDERLOOP_FAKE_KEY=sk-FAKE-do-not-use-123456'"
    event = {"hook_event_name": "PreToolUse", "session_id": "abcd1234", "tool_name": "Bash",
             "tool_input": {"command": secret_cmd}}
    res = run_hook("audit_log.py", event, project_dir=tmp)
    check(res is not None and res.returncode == 0, "audit hook exits 0")
    logs = list(tmp.rglob("*.log")) + list(tmp.rglob("*.jsonl"))
    text = logs[0].read_text(encoding="utf-8") if logs else ""
    check(bool(text.strip()), "audit hook writes a line to a log file under .claude/")
    check("Bash" in text, "the audit line names the tool")
    leaked = [s for s in ("asha.verma", "example.test", "555-0101", "sk-FAKE", "123456") if s in text]
    check(not leaked, "the audit line holds no email, phone or key" + (f" (found: {leaked})" if leaked else ""))
    junk = run_hook("audit_log.py", "not json", project_dir=tmp)
    check(junk is not None and junk.returncode == 0, "audit hook fails open on bad input (exit 0)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- git hygiene ---------------------------------------------------------
check(git("ls-files", ".env") == "", ".env is not tracked")
check(git("ls-files", ".claude/audit.log") == "", "the audit log is not tracked")
check(bool(git("ls-files", ".claude/settings.json", ".claude/hooks")), "settings.json and the hooks are tracked by git")
check(bool(git("log", "--oneline", "--", ".claude/settings.json", ".claude/hooks")), "you committed the settings and hooks")
check(git("status", "--porcelain", "--", ".claude/settings.json", ".claude/hooks") == "", "no uncommitted changes in the settings and hooks")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
