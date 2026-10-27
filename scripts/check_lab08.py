"""Check for Lab 8 (MCP: connect). Standard library only.

Run from the repository root:  python scripts/check_lab08.py

It reads .mcp.json and .claude/settings.json. It does not start the server.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- .mcp.json (project scope) --------------------------------------------
mcp_file = ROOT / ".mcp.json"
check(mcp_file.exists(), ".mcp.json exists in the project root (project scope)")
config = load_json(mcp_file) if mcp_file.exists() else None
check(isinstance(config, dict), ".mcp.json is valid JSON")
servers = config.get("mcpServers", {}) if isinstance(config, dict) else {}
check(isinstance(servers, dict) and len(servers) >= 1, ".mcp.json defines at least one server under mcpServers")

stdio = {n: s for n, s in servers.items() if isinstance(s, dict) and s.get("command")}
check(bool(stdio), "at least one server is a local (stdio) server with a command")

text = mcp_file.read_text(encoding="utf-8") if mcp_file.exists() else ""
check(not re.search(r"(?i)(sk-|ghp_|bearer\s+[a-z0-9]|password|secret)", text), "no secret-looking text in .mcp.json (use ${VAR} instead)")

# --- .claude/settings.json: a deny rule on one tool of that server -------------
settings_file = ROOT / ".claude" / "settings.json"
check(settings_file.exists(), ".claude/settings.json exists")
settings = load_json(settings_file) if settings_file.exists() else None
check(isinstance(settings, dict), ".claude/settings.json is valid JSON")
deny = settings.get("permissions", {}).get("deny", []) if isinstance(settings, dict) else []
mcp_rules = [r for r in deny if isinstance(r, str) and re.fullmatch(r"mcp__[^_()][^()]*__[^()]+", r)]
check(bool(mcp_rules), "permissions.deny has a rule of the form mcp__<server>__<tool> (no parentheses)")
named = [r for r in mcp_rules if r.split("__")[1] in {re.sub(r"[^A-Za-z0-9_-]", "_", n) for n in servers}]
check(bool(named), "the deny rule names a server that is defined in .mcp.json")

base = "lab-08-start" if git("tag", "-l", "lab-08-start") else "main"
log = git("log", "--oneline", f"{base}..HEAD")
check(bool(log), "at least one commit on your branch")
check(".mcp.json" in git("ls-files").split(), ".mcp.json is committed (so the team shares it)")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
