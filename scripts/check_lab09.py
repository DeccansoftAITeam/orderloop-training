"""Check for Lab 9 (MCP: build a server). Standard library only.

Run from the repository root:  python scripts/check_lab09.py

It seeds a throwaway database, starts YOUR server (mcp/orderloop_server.py) over stdio
exactly as Claude Code does, talks to it with raw JSON-RPC lines, and checks the results.
It also runs your tests and reads .mcp.json.
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SERVER = ROOT / "mcp" / "orderloop_server.py"
UV = shutil.which("uv")
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def python_cmd(*args: str) -> list[str]:
    """Run Python inside the backend project (uv), or with this interpreter if uv is missing."""
    if UV:
        return [UV, "run", "--project", str(BACKEND), "python", *args]
    return [sys.executable, *args]


class Rpc:
    """Minimal MCP client over stdio: one JSON message per line."""

    def __init__(self, env: dict) -> None:
        self.proc = subprocess.Popen(
            python_cmd(str(SERVER)), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", cwd=ROOT, env=env,
        )
        self.lines: queue.Queue = queue.Queue()
        self.noise: list[str] = []
        threading.Thread(target=self._pump, daemon=True).start()
        self.next_id = 0

    def _pump(self) -> None:
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message: dict) -> None:
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None, timeout: float = 90):
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        while True:
            try:
                line = self.lines.get(timeout=timeout)
            except queue.Empty:
                return None
            if line is None:
                return None
            try:
                message = json.loads(line)
            except ValueError:
                self.noise.append(line.strip()[:80])  # something other than JSON on stdout
                continue
            if message.get("id") == self.next_id:
                return message

    def call(self, name: str, arguments: dict | None = None):
        reply = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        return (reply or {}).get("result")

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def payload(result) -> dict:
    """The tool's dict, from structuredContent (preferred) or the JSON text content."""
    if not result:
        return {}
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    try:
        return json.loads(result["content"][0]["text"])
    except Exception:
        return {}


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

check(SERVER.exists(), "mcp/orderloop_server.py exists")
source = SERVER.read_text(encoding="utf-8") if SERVER.exists() else ""
bad_print = [
    line for line in source.splitlines()
    if re.search(r"\bprint\(", line) and "stderr" not in line and not line.lstrip().startswith("#")
]
check(SERVER.exists() and not bad_print, "the server never prints to stdout (stdout belongs to the protocol)")

if SERVER.exists():
    tmp = Path(tempfile.mkdtemp(prefix="orderloop-check-"))
    db = tmp / "check.db"
    env = {**os.environ, "ORDERLOOP_DB": str(db), "PYTHONIOENCODING": "utf-8"}
    seeded = subprocess.run(python_cmd("-m", "app.seed"), cwd=BACKEND, env=env, capture_output=True, text=True)
    check(seeded.returncode == 0, "a throwaway test database was seeded")
    rpc = Rpc(env)
    try:
        init = rpc.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "check_lab09", "version": "1"},
        })
        result = (init or {}).get("result", {})
        check(bool(result), "the server starts over stdio and answers the initialize request")
        check(result.get("serverInfo", {}).get("name") == "orderloop", 'the server name is "orderloop"')
        rpc.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        tools = ((rpc.request("tools/list") or {}).get("result") or {}).get("tools", [])
        names = {t["name"] for t in tools}
        expected = {"lookup_order", "check_refund_eligibility", "list_orders_needing_attention"}
        check(expected <= names, "the three tools are listed: " + ", ".join(sorted(expected)))
        check(names <= expected, "no extra tools (read-only means no refund-creating tool)")
        by_name = {t["name"]: t for t in tools}
        check(all(by_name.get(n, {}).get("description", "").strip() for n in expected), "every tool has a description")
        check("order_id" in by_name.get("lookup_order", {}).get("inputSchema", {}).get("properties", {}),
              "lookup_order takes order_id (from the type hints)")

        before = db.read_bytes() if db.exists() else b""

        res = rpc.call("lookup_order", {"order_id": 1001})
        data = payload(res)
        check(bool(res) and not res.get("isError") and data.get("order_id") == 1001, "lookup_order(1001) returns order_id 1001")
        check({i.get("sku") for i in data.get("items", [])} == {"TENT-2P", "STOVE-1"}, "lookup_order lists the order's items")
        everything = json.dumps(res)
        check("asha.verma" not in everything and "555-0101" not in everything and "Larch" not in everything,
              "lookup_order does not leak the real email, phone or address")
        customer = data.get("customer", {})
        check(customer.get("email") == "a***@example.test", "email is masked as a***@example.test")
        check(customer.get("phone") == "***0101", "phone is masked as ***0101")

        res = rpc.call("lookup_order", {"order_id": 999999})
        check(bool(res) and res.get("isError") is True, "an unknown order gives isError true (not a crash)")

        data = payload(rpc.call("check_refund_eligibility", {"order_id": 1002}))
        check(data.get("eligible") is True and data.get("late") is False and data.get("max_refundable_cents") == 9500,
              "1002 (exactly 30 days) is eligible, not late, max 9500")
        data = payload(rpc.call("check_refund_eligibility", {"order_id": 1003}))
        check(data.get("late") is True, "1003 (31 days) is late")
        data = payload(rpc.call("check_refund_eligibility", {"order_id": 1005}))
        check(data.get("eligible") is False and "no_refundable_items" in data.get("blockers", []),
              "1005 (gift card) is not eligible")
        data = payload(rpc.call("check_refund_eligibility", {"order_id": 1007}))
        check(data.get("max_refundable_cents") == 10000, "1007 counts the earlier 5000 refund: max 10000")

        data = payload(rpc.call("list_orders_needing_attention"))
        ids = sorted(o.get("order_id") for o in data.get("orders", []))
        check(ids == [1001, 1003, 1007, 1008] and data.get("count") == 4,
              "list_orders_needing_attention returns orders 1001, 1003, 1007, 1008 and count 4")

        after = db.read_bytes() if db.exists() else b""
        check(before == after, "the tools did not change the database")
        check(not rpc.noise, "nothing but protocol messages on stdout" + (f" (found: {rpc.noise[:2]})" if rpc.noise else ""))
    finally:
        rpc.close()
        shutil.rmtree(tmp, ignore_errors=True)

# --- tests -------------------------------------------------------------------
tests = BACKEND / "tests" / "test_orderloop_server.py"
check(tests.exists(), "backend/tests/test_orderloop_server.py exists")
if tests.exists():
    count = len(re.findall(r"^\s*def test_", tests.read_text(encoding="utf-8"), re.M))
    check(count >= 6, f"at least 6 tests of your own ({count} found)")
    run = None
    if UV:
        run = subprocess.run([UV, "run", "pytest", "-q", "tests/test_orderloop_server.py"],
                             cwd=BACKEND, capture_output=True, text=True)
    check(run is not None and run.returncode == 0, "your server tests pass (uv run pytest tests/test_orderloop_server.py)")

# --- registration ----------------------------------------------------------------
mcp_file = ROOT / ".mcp.json"
registered = None
if mcp_file.exists():
    try:
        registered = json.loads(mcp_file.read_text(encoding="utf-8")).get("mcpServers", {}).get("orderloop")
    except ValueError:
        pass
check(isinstance(registered, dict) and bool(registered.get("command")), '.mcp.json registers a server named "orderloop"')
check("orderloop_server.py" in json.dumps(registered or {}), "the registered command runs mcp/orderloop_server.py")
check(not re.search(r"(?i)sk-|password|secret", mcp_file.read_text(encoding="utf-8") if mcp_file.exists() else ""),
      "no secrets in .mcp.json")

base = "lab-09-start" if git("tag", "-l", "lab-09-start") else "main"
check(bool(git("log", "--oneline", f"{base}..HEAD")), "at least one commit on your branch")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
