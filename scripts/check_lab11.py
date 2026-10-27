"""Check for Lab 11 (Plugin). Standard library only.

Run from the repository root:  python scripts/check_lab11.py

It reads the plugin you built in plugins/orderloop-sdlc, the marketplace file at the repository root,
feeds sample hook input (JSON on stdin) to the packaged guard hook, and runs
`claude plugin validate` when the claude command is available.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "orderloop-sdlc"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def frontmatter_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    m = re.match(r"---\r?\n(.*?)\r?\n---", path.read_text(encoding="utf-8"), re.S)
    return {kv.group(1) for line in (m.group(1).splitlines() if m else []) if (kv := re.match(r"([A-Za-z][\w-]*):", line))}


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the manifest --------------------------------------------------------
manifest_path = PLUGIN / ".claude-plugin" / "plugin.json"
manifest = load_json(manifest_path)
check(manifest is not None, "plugins/orderloop-sdlc/.claude-plugin/plugin.json exists and is valid JSON")
if manifest:
    check(manifest.get("name") == "orderloop-sdlc", 'the plugin name is "orderloop-sdlc"')
    check(bool(manifest.get("description")), "the manifest has a description")
    version = str(manifest.get("version", ""))
    parts = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    check(parts is not None, f"the version is MAJOR.MINOR.PATCH (found '{version}')")
    check(parts is not None and tuple(map(int, parts.groups())) > (1, 0, 0),
          "you bumped the version above 1.0.0")
    others = {p.name for p in (PLUGIN / ".claude-plugin").glob("*")} - {"plugin.json"} if (PLUGIN / ".claude-plugin").exists() else set()
    check(not others, "only plugin.json is inside .claude-plugin/ (components there do not load)")

# --- components ----------------------------------------------------------
check((PLUGIN / "skills" / "refund-policy" / "SKILL.md").exists(), "skills/refund-policy/SKILL.md is in the plugin")
check((PLUGIN / "skills" / "pr-summary" / "SKILL.md").exists(), "skills/pr-summary/SKILL.md is in the plugin")
agent_file = PLUGIN / "agents" / "refund-triage.md"
check(agent_file.exists(), "agents/refund-triage.md is in the plugin")
if agent_file.exists():
    keys = frontmatter_keys(agent_file)
    check(not ({"permissionMode", "hooks", "mcpServers"} & keys),
          "the packaged agent uses no frontmatter a plugin agent ignores (permissionMode, hooks, mcpServers)")
    check("mcp__orderloop__lookup_order" in agent_file.read_text(encoding="utf-8"),
          "the agent still lists the orderloop MCP tools")

# --- hooks ----------------------------------------------------------------
hooks_json = load_json(PLUGIN / "hooks" / "hooks.json")
check(hooks_json is not None and "hooks" in hooks_json, "hooks/hooks.json exists with a top-level hooks key")
entry = None
if hooks_json:
    for group in hooks_json.get("hooks", {}).get("PreToolUse", []):
        for h in group.get("hooks", []):
            if "refund_guard.py" in json.dumps(h):
                entry = h
check(entry is not None and entry.get("type") == "command", "hooks.json runs refund_guard.py on PreToolUse")
script = None
if entry:
    text = json.dumps(entry)
    check("${CLAUDE_PLUGIN_ROOT}" in text, "the hook path starts from ${CLAUDE_PLUGIN_ROOT}")
    check("CLAUDE_PROJECT_DIR" not in text, "the hook path does not use ${CLAUDE_PROJECT_DIR} (that is the project, not the plugin)")
    check(entry.get("onFailure") == "block", 'the hook keeps "onFailure": "block" (fails closed)')
    m = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+refund_guard\.py)", text)
    if m:
        script = PLUGIN / m.group(1)
check(script is not None and script.exists(), "the script named in hooks.json exists inside the plugin")


def run_guard(event):
    if script is None or not script.exists():
        return None
    try:
        return subprocess.run([sys.executable, str(script)], input=json.dumps(event), capture_output=True, text=True,
                              cwd=ROOT, env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}, timeout=60)
    except subprocess.TimeoutExpired:
        return None


def blocks(res) -> bool:
    return res is not None and res.returncode == 2 and bool(res.stderr.strip())


def passes(res) -> bool:
    return res is not None and res.returncode == 0


def ev(tool, tool_input, agent=None):
    e = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    if agent:
        e |= {"agent_type": agent, "agent_id": "a1b2c3"}
    return e


check(blocks(run_guard(ev("Bash", {"command": "curl -X POST localhost:8000/orders/1002/refunds"}))),
      "packaged guard blocks a refund POST")
check(blocks(run_guard(ev("Bash", {"command": "ls"}, agent="refund-triage"))),
      "packaged guard blocks Bash from the agent named refund-triage")
check(blocks(run_guard(ev("Bash", {"command": "ls"}, agent="orderloop-sdlc:refund-triage"))),
      "packaged guard blocks Bash from the NAMESPACED agent (orderloop-sdlc:refund-triage)")
check(passes(run_guard(ev("mcp__orderloop__lookup_order", {"order_id": 1002}, agent="orderloop-sdlc:refund-triage"))),
      "packaged guard lets the namespaced agent call lookup_order")
check(passes(run_guard(ev("Bash", {"command": "cd backend && uv run pytest -q"}))),
      "packaged guard lets the main session run the tests")

# --- the marketplace ------------------------------------------------------
market = load_json(ROOT / ".claude-plugin" / "marketplace.json")
check(market is not None, ".claude-plugin/marketplace.json exists at the repository root and is valid JSON")
if market:
    check(bool(market.get("name")) and "owner" in market, "the marketplace has a name and an owner")
    plugins = market.get("plugins", [])
    mine = next((p for p in plugins if p.get("name") == "orderloop-sdlc"), None)
    check(mine is not None, "the marketplace lists orderloop-sdlc (entry name equals the manifest name)")
    if mine:
        check(mine.get("source") == "./plugins/orderloop-sdlc", 'the entry source is the relative path "./plugins/orderloop-sdlc"')
        check("version" not in mine, "the version is set in plugin.json only, not also in the marketplace entry")

# --- no duplicates left in .claude/ --------------------------------------
check(not (ROOT / ".claude" / "skills" / "refund-policy").exists(), ".claude/skills/refund-policy is gone (the plugin owns it)")
check(not (ROOT / ".claude" / "skills" / "pr-summary").exists(), ".claude/skills/pr-summary is gone (the plugin owns it)")
check(not (ROOT / ".claude" / "agents" / "refund-triage.md").exists(), ".claude/agents/refund-triage.md is gone (the plugin owns it)")
settings = load_json(ROOT / ".claude" / "settings.json") or {}
check("hooks" not in settings, ".claude/settings.json no longer registers the hook (it would run twice)")
check("mcp__orderloop__lookup_order" in settings.get("permissions", {}).get("allow", []),
      ".claude/settings.json keeps the permissions (a plugin cannot ship them)")
check((ROOT / ".mcp.json").exists() and (ROOT / "mcp" / "orderloop_server.py").exists(),
      "the MCP server and .mcp.json stay in the project")

# --- claude plugin validate ----------------------------------------------
claude = shutil.which("claude")
if claude is None:
    print("SKIP  claude is not on PATH: skipping `claude plugin validate`")
else:
    for label, target in (("the plugin", PLUGIN), ("the marketplace", ROOT)):
        res = subprocess.run([claude, "plugin", "validate", str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        check(res.returncode == 0, f"`claude plugin validate` passes for {label}")

# --- git hygiene ----------------------------------------------------------
check(bool(git("ls-files", "plugins/orderloop-sdlc/.claude-plugin/plugin.json")), "the plugin is tracked by git")
check(bool(git("ls-files", ".claude-plugin/marketplace.json")), "the marketplace file is tracked by git")
check(git("status", "--porcelain", "--", "plugins", ".claude-plugin", ".claude") == "", "no uncommitted changes in plugins/, .claude-plugin/ or .claude/")
check(git("ls-files", ".claude/settings.local.json") == "", "settings.local.json is not tracked")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
