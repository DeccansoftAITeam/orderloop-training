"""Check for Lab 6 (Permissions). Standard library only.

Run from the repository root:  python scripts/check_lab06.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip()


settings_path = ROOT / ".claude" / "settings.json"
check(settings_path.exists(), ".claude/settings.json exists")

settings: dict = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        check(True, ".claude/settings.json is valid JSON")
    except json.JSONDecodeError as err:
        check(False, f".claude/settings.json is valid JSON ({err})")

perms = settings.get("permissions", {})
allow, ask, deny = perms.get("allow", []), perms.get("ask", []), perms.get("deny", [])

check("Read(./.env)" in deny or "Read(.env)" in deny, "deny rule blocks reading .env")
check(any(r.startswith("Read(./.env.") or r.startswith("Read(.env.") for r in deny), "deny rule blocks reading .env.* files")
check(any("customers.csv" in r and r.startswith("Read(") for r in deny), "deny rule blocks reading seed/customers.csv")
check(any(r.startswith("Bash(git push origin main") for r in deny), "deny rule blocks pushing to main")
check(any(r.startswith("Bash(curl") for r in deny), "deny rule blocks curl")
check(any(r.startswith("Bash(uv run pytest") for r in allow), "allow rule covers the test command")
check(not any(r in ("Bash", "Bash(*)", "Bash(git *)") for r in allow), "allow list has no blanket Bash rule")
check(not any(r.startswith("Bash(git push") for r in allow), "git push is not allowed without asking")
check(perms.get("defaultMode") not in ("auto", "bypassPermissions"), "settings do not default to auto or bypass mode")

check(not (ROOT / ".claudeignore").exists(), ".claudeignore is gone (it has no effect)")

tracked = git("ls-files").splitlines()
check(".env" not in tracked, ".env is not tracked by git")
staged = git("status", "--porcelain", ".claude/settings.json")
check(".claude/settings.json" in tracked or (staged != "" and not staged.startswith("??")),
      ".claude/settings.json is added to git (committed or staged)")

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL CHECKS PASSED")
