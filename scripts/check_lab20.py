"""Check for Lab 20 (Agent SDK). Standard library only.

Run from the repository root:  python scripts/check_lab20.py

It never calls a model and needs no API key. It runs your script in --dry-run
mode and reads its source to check how the live path is configured.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "agent" / "triage_agent.py"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def dry_run(order: int, requested: int):
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--order", str(order), "--requested", str(requested), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None


def parsed(result):
    try:
        return json.loads(result.stdout)
    except Exception:
        return None


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")
check((ROOT / "agent" / "order_facts.py").exists(), "agent/order_facts.py is present (shipped with the lab)")
check(SCRIPT.exists(), "agent/triage_agent.py exists")

if SCRIPT.exists():
    source = SCRIPT.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
        check(True, "triage_agent.py is valid Python")
    except SyntaxError as exc:
        tree = None
        check(False, f"triage_agent.py is valid Python ({exc})")

    # --- the live path: how the SDK is configured -----------------------
    if tree is not None:
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        check("claude_agent_sdk" in imported, "imports from claude_agent_sdk")
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        options = next((c for c in calls if getattr(c.func, "id", "") == "ClaudeAgentOptions"), None)
        check(options is not None, "builds a ClaudeAgentOptions")
        if options is not None:
            kw = {k.arg: k.value for k in options.keywords if k.arg}
            for name in ("allowed_tools", "permission_mode", "max_turns", "max_budget_usd", "output_format",
                         "mcp_servers", "strict_mcp_config"):
                check(name in kw, f"ClaudeAgentOptions sets {name}")
            if "allowed_tools" in kw:
                try:
                    allowed = ast.literal_eval(kw["allowed_tools"])
                except Exception:
                    allowed = None
                check(isinstance(allowed, list) and allowed and all(str(a).startswith("mcp__") for a in allowed),
                      "allowed_tools lists only mcp__ tools (no Bash, Write or Edit)")
            if "tools" in kw:
                check(ast.dump(kw["tools"]) == ast.dump(ast.List(elts=[], ctx=ast.Load())),
                      "tools=[] turns the built-in tools off")
            else:
                check(False, "tools=[] turns the built-in tools off")
        check(any(getattr(c.func, "id", "") == "tool" or getattr(c.func, "attr", "") == "tool" for c in calls)
              and "create_sdk_mcp_server" in source, "defines a custom tool and serves it with create_sdk_mcp_server")
        check("bypassPermissions" not in source and "dangerously" not in source.lower(),
              "no bypass mode anywhere in the script")
        check("structured_output" in source, "reads structured_output from the result message")
        top_level_sdk = any(isinstance(n, (ast.Import, ast.ImportFrom)) and "claude_agent_sdk" in ast.dump(n)
                            for n in tree.body)
        check(not top_level_sdk, "the SDK is imported inside the live function, so --dry-run needs no SDK")

    # --- dry-run behaviour (deterministic) ------------------------------
    cases = [
        (1001, 18000, "approve", 18000),
        (1007, 20000, "approve", 10000),
        (1003, 7000, "needs_lead", 0),
        (1008, 45000, "needs_lead", 0),
        (1005, 5000, "reject", 0),
        (1006, 4500, "reject", 0),
        (999, 100, "reject", 0),
    ]
    for order, requested, want, cents in cases:
        res = dry_run(order, requested)
        out = parsed(res) if res is not None and res.returncode == 0 else None
        ok = (out is not None and out.get("recommendation") == want and out.get("approved_cents") == cents
              and out.get("mode") == "dry-run" and isinstance(out.get("reasons"), list) and out["reasons"])
        check(ok, f"--dry-run order {order}, {requested} cents -> {want}, {cents} cents")
    first, second = dry_run(1003, 7000), dry_run(1003, 7000)
    check(first is not None and second is not None and first.stdout == second.stdout and first.stdout != "",
          "--dry-run gives the same output twice")
    res = dry_run(1001, 18000)
    leaked = [s for s in ("verma", "example.test", "555-01", "Larch") if res is not None and s in res.stdout]
    check(res is not None and not leaked, "the output holds no customer name, email, phone or address")
    nodb = subprocess.run([sys.executable, str(SCRIPT), "--dry-run"], cwd=ROOT, capture_output=True, text=True)
    check(nodb.returncode != 0, "missing --order is rejected")

# --- dependency and git hygiene -----------------------------------------
pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
check("claude-agent-sdk" in pyproject, "backend/pyproject.toml lists claude-agent-sdk")
check(git("ls-files", "agent/triage_agent.py") != "", "triage_agent.py is tracked by git")
check(bool(git("log", "--oneline", "--", "agent/triage_agent.py")), "you committed the script")
check(git("status", "--porcelain", "--", "agent", "backend/pyproject.toml", "backend/uv.lock") == "",
      "no uncommitted changes in agent/ and the backend dependencies")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
