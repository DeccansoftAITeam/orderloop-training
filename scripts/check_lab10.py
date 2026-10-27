"""Check for Lab 10 (Refund Triage agent). Standard library only.

Run from the repository root:  python scripts/check_lab10.py

It checks the structure of your skill, subagent and settings, feeds sample hook input
(JSON on stdin) to your guard hook and checks the decision, starts the orderloop MCP server
and calls its tools, and reads your evaluation table.
It does not run Claude: you run the agent yourself and record what it did.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
failures: list[str] = []

LOOKUP = "mcp__orderloop__lookup_order"
ELIGIBILITY = "mcp__orderloop__check_refund_eligibility"
LISTING = "mcp__orderloop__list_orders_needing_attention"


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def frontmatter(path: Path):
    """Return (fields, body). A field is a string or, for '- item' lines, a list of strings."""
    if not path.exists():
        return None, ""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return None, text
    fields: dict = {}
    key = None
    for line in m.group(1).split("\n"):
        item = re.match(r"\s+-\s+(.*)", line)
        kv = re.match(r"([A-Za-z][\w-]*):\s*(.*)", line)
        if item and key:
            if not isinstance(fields.get(key), list):
                fields[key] = []
            fields[key].append(item.group(1).strip())
        elif kv:
            key = kv.group(1)
            fields[key] = kv.group(2).strip()
    return fields, m.group(2)


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return value
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the skill -----------------------------------------------------------
skill_fm, skill_body = frontmatter(CLAUDE / "skills" / "refund-policy" / "SKILL.md")
check(skill_fm is not None, ".claude/skills/refund-policy/SKILL.md exists and has frontmatter")
if skill_fm is not None:
    check(skill_fm.get("name") == "refund-policy", "the skill is named refund-policy")
    check("use when" in str(skill_fm.get("description", "")).lower(), 'the skill description says "Use when ..."')
    low = skill_body.lower()
    check(all(w in low for w in ("approve", "deny", "escalate")), "the skill defines approve, deny and escalate")
    check("late" in low and "lead_approval_threshold_cents" in skill_body,
          "the skill covers late orders and reads the lead-approval threshold from the tool")
    check("customer_reply" in skill_body and "decision" in skill_body and "amount_cents" in skill_body,
          "the skill defines the structured result (decision, amount_cents, customer_reply)")
    check(not re.search(r"\b20,?000\b", skill_body), "the skill does not hard-code the threshold number")

# --- the subagent --------------------------------------------------------
agent_fm, agent_body = frontmatter(CLAUDE / "agents" / "refund-triage.md")
check(agent_fm is not None, ".claude/agents/refund-triage.md exists and has frontmatter")
if agent_fm is not None:
    check(agent_fm.get("name") == "refund-triage", "the agent is named refund-triage")
    check("when" in str(agent_fm.get("description", "")).lower(), "the agent description says when to use it")
    tools = as_list(agent_fm.get("tools"))
    check(set(tools) == {LOOKUP, ELIGIBILITY}, "tools lists exactly lookup_order and check_refund_eligibility (least privilege)")
    check(not any(t in tools for t in ("Bash", "Write", "Edit", "Read", "Grep", "Glob", "WebFetch", "PowerShell")),
          "the agent has no shell, file or web tools")
    check("refund-policy" in as_list(agent_fm.get("skills")), "the agent preloads the refund-policy skill (skills:)")
    check(bool(agent_fm.get("model")), "the agent sets a model")
    check(str(agent_fm.get("maxTurns", "")).isdigit(), "the agent sets maxTurns")
    for field in ("permissionMode", "hooks", "mcpServers"):
        check(field not in agent_fm, f"the agent does not use {field} (a plugin would ignore it)")
    check(len(agent_body.split()) > 60, "the agent has a written contract (authority, steps, output)")
    low = agent_body.lower()
    check("may not" in low or "must not" in low or "never" in low, "the contract says what the agent may NOT do")
    check("escalate" in low, "the contract says what to do when a tool fails (escalate)")

# --- settings.json -------------------------------------------------------
settings: dict = {}
sp = CLAUDE / "settings.json"
check(sp.exists(), ".claude/settings.json exists")
if sp.exists():
    try:
        settings = json.loads(sp.read_text(encoding="utf-8"))
        check(True, "settings.json is valid JSON")
    except json.JSONDecodeError as exc:
        check(False, f"settings.json is valid JSON ({exc})")
perms = settings.get("permissions", {})
allow, deny = perms.get("allow", []), perms.get("deny", [])
check(LOOKUP in allow and ELIGIBILITY in allow, "permissions.allow names the two read tools")
check(not any(a in ("Bash", "Bash(*)", "Edit", "Write", "mcp__orderloop__*", "mcp__orderloop") for a in allow),
      "permissions.allow has no broad grant (no bare Bash, Edit, Write or server wildcard)")
check(any("curl" in d or "orderloop.db" in d or "sqlite3" in d for d in deny),
      "permissions.deny blocks a way around the tools (curl, sqlite3 or the database file)")
hooks = [h for g in settings.get("hooks", {}).get("PreToolUse", []) for h in g.get("hooks", [])]
guard = next((h for h in hooks if "refund_guard.py" in json.dumps(h)), None)
check(guard is not None and guard.get("type") == "command", "PreToolUse runs refund_guard.py as a command hook")
if guard:
    check(guard.get("onFailure") == "block", 'the guard sets "onFailure": "block" (fails closed)')
    check("CLAUDE_PROJECT_DIR" in json.dumps(guard), "the guard path starts from CLAUDE_PROJECT_DIR")

# --- refund_guard.py -----------------------------------------------------
HOOK = CLAUDE / "hooks" / "refund_guard.py"


def run_hook(payload):
    if not HOOK.exists():
        return None
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
    data = payload if isinstance(payload, str) else json.dumps(payload)
    try:
        return subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True, text=True,
                              cwd=ROOT, env=env, timeout=60)
    except subprocess.TimeoutExpired:
        return None


def denies(res) -> bool:
    """True if the hook blocks: exit code 2 with a reason, or JSON permissionDecision 'deny'."""
    if res is None:
        return False
    if res.returncode == 2 and res.stderr.strip():
        return True
    try:
        out = json.loads(res.stdout)
        return res.returncode == 0 and out["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        return False


def allows(res) -> bool:
    return res is not None and res.returncode == 0 and "deny" not in res.stdout


def call(tool: str, tool_input: dict, agent: str | None = None) -> dict:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": str(ROOT)}
    if agent:
        event |= {"agent_type": agent, "agent_id": "a1b2c3"}
    return event


check(HOOK.exists(), ".claude/hooks/refund_guard.py exists")
for label, payload in [
    ("curl POST to /refunds", call("Bash", {"command": "curl -X POST http://localhost:8000/orders/1002/refunds -d '{}'"})),
    ("python one-liner posting to /refunds",
     call("Bash", {"command": "python -c \"import httpx; httpx.post('http://localhost:8000/orders/1002/refunds')\""})),
    ("INSERT INTO refunds", call("Bash", {"command": "sqlite3 backend/orderloop.db \"INSERT INTO refunds VALUES (1)\""})),
    ("opening orderloop.db", call("Bash", {"command": "python -c \"import sqlite3; sqlite3.connect('backend/orderloop.db')\""})),
    ("an unknown orderloop tool (create_refund)", call("mcp__orderloop__create_refund", {"order_id": 1002})),
    ("the agent calling Bash", call("Bash", {"command": "ls"}, agent="refund-triage")),
    ("the agent calling Read", call("Read", {"file_path": str(ROOT / "backend" / "app" / "rules.py")}, agent="refund-triage")),
    ("the agent calling the listing tool", call(LISTING, {}, agent="refund-triage")),
]:
    check(denies(run_hook(payload)), f"guard blocks: {label}")
for label, payload in [
    ("the agent calling lookup_order", call(LOOKUP, {"order_id": 1002}, agent="refund-triage")),
    ("the agent calling check_refund_eligibility", call(ELIGIBILITY, {"order_id": 1002}, agent="refund-triage")),
    ("the agent handing its report back (SubagentHandback)", call("SubagentHandback", {"message": "{}"}, agent="refund-triage")),
    ("the main session running the tests", call("Bash", {"command": "cd backend && uv run pytest -q"})),
    ("the main session calling the listing tool", call(LISTING, {})),
    ("the main session reading rules.py", call("Read", {"file_path": str(ROOT / "backend" / "app" / "rules.py")})),
]:
    check(allows(run_hook(payload)), f"guard allows: {label}")
bad = run_hook("this is not json")
check(bad is not None and bad.returncode == 2, "guard fails closed on unreadable input (exit 2)")
blocked = run_hook(call("Bash", {"command": "curl -X POST localhost:8000/orders/1/refunds"}))
check(blocked is not None and len((blocked.stderr + blocked.stdout).strip()) > 20, "the block message gives a reason")

# --- the orderloop MCP server (shipped with this lab; must still work) ----
server = ROOT / "mcp" / "orderloop_server.py"
check(server.exists(), "mcp/orderloop_server.py exists")
mcp_cfg = ROOT / ".mcp.json"
check(mcp_cfg.exists() and "orderloop" in mcp_cfg.read_text(encoding="utf-8"), ".mcp.json registers the orderloop server")


def result_json(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


tmp = Path(tempfile.mkdtemp(prefix="lab10-"))
try:
    env = {**os.environ, "ORDERLOOP_DB": str(tmp / "check.db")}
    seed = subprocess.run([sys.executable, "-m", "app.seed"], cwd=ROOT / "backend", env=env, capture_output=True, text=True)
    check(seed.returncode == 0, "a throwaway database can be seeded")
    uv = shutil.which("uv")
    if uv is None:
        check(False, "uv is installed (needed to start the MCP server)")
    elif seed.returncode == 0:
        proc = subprocess.Popen(
            [uv, "run", "--project", "backend", "--group", "mcp", "python", "mcp/orderloop_server.py"],
            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

        def rpc(msg_id, method, params=None):
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        try:
            init = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "check", "version": "0"}})
            check(init["result"]["serverInfo"]["name"] == "orderloop", "the server is named orderloop")
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
            names = {t["name"] for t in rpc(2, "tools/list")["result"]["tools"]}
            check(names == {"lookup_order", "check_refund_eligibility", "list_orders_needing_attention"},
                  "the server offers exactly the three read-only tools")
            order = rpc(3, "tools/call", {"name": "lookup_order", "arguments": {"order_id": 1002}})["result"]
            cust = result_json(order)["customer"]
            check(not order.get("isError") and "@" in cust["email_masked"] and "ben.okafor" not in json.dumps(order)
                  and cust["phone_masked"].startswith("***-"), "lookup_order returns the order with email and phone masked")
            el = rpc(4, "tools/call", {"name": "check_refund_eligibility", "arguments": {"order_id": 1003}})["result"]
            check(not el.get("isError") and result_json(el)["late"] is True, "check_refund_eligibility reports order 1003 as late")
            missing = rpc(5, "tools/call", {"name": "lookup_order", "arguments": {"order_id": 9999}})["result"]
            check(bool(missing.get("isError")), "an unknown order is an error result, not a crash")
        except Exception as exc:  # a broken server must not crash the checker
            check(False, f"the MCP server answers requests ({exc})")
        finally:
            proc.terminate()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- the evaluation table ------------------------------------------------
eval_path = ROOT / "docs" / "lab10-eval.md"
check(eval_path.exists(), "docs/lab10-eval.md exists")
if eval_path.exists():
    text = eval_path.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and cells[0].isdigit():
            rows[cells[0]] = cells
    check(len(rows) >= 3, "the table has at least three scenario rows")
    check({"1002", "1003", "1008"} <= set(rows), "the table covers orders 1002 (on time), 1003 (late) and 1008 (large)")
    for oid, want in {"1002": "approve", "1003": "escalate", "1008": "escalate"}.items():
        if oid in rows:
            check(rows[oid][2].lower() == want, f"order {oid}: the expected decision is {want}")
    filled = all(r[4].lower() in ("approve", "deny", "escalate") and r[5].lower() in ("yes", "no") for r in rows.values())
    check(bool(rows) and filled, "every row records the actual decision and yes or no under Match?")
    check("TODO" not in text and "______" not in text, "the table has no TODO or blank markers left")
    check("pii" in text.lower(), "the notes say whether any PII reached a customer reply")

# --- git hygiene ---------------------------------------------------------
mine = [".claude/agents/refund-triage.md", ".claude/skills/refund-policy/SKILL.md", ".claude/hooks/refund_guard.py",
        ".claude/settings.json", "docs/lab10-eval.md"]
check(all(git("ls-files", p) for p in mine), "your five files are tracked by git")
check(git("status", "--porcelain", "--", ".claude", "docs/lab10-eval.md") == "", "no uncommitted changes in .claude/ or the table")
check(git("ls-files", "backend/orderloop.db") == "", "the database file is not tracked")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
