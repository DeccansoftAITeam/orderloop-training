"""Check for Lab 5 (Subagents and orchestration). Standard library only.

Run from the repository root:  python scripts/check_lab05.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
AGENTS = ROOT / ".claude" / "agents"
failures: list[str] = []

REQUIRED = ["analyst", "test-author", "implementer", "reviewer", "security-reviewer", "qa"]
READ_ONLY = {"analyst", "reviewer", "security-reviewer", "qa"}  # must not have Edit or Write
WRITE_TOOLS = {"edit", "write", "notebookedit"}


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def run(*cmd: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True)


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    stripped = [l.strip() for l in lines]
    if not lines or stripped[0] != "---" or "---" not in stripped[1:]:
        return {}
    end = stripped[1:].index("---") + 1
    fields = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def tool_set(value: str) -> set[str]:
    return {t.strip().lower() for t in re.split(r"[,\s]+", value.strip("[]")) if t.strip()}


branch = run("git", "branch", "--show-current").stdout.strip()
check(branch != "main", f"you are on your own branch, not main (on '{branch}')")

# --- Subagent files -------------------------------------------------------
for name in REQUIRED:
    path = AGENTS / f"{name}.md"
    check(path.exists(), f".claude/agents/{name}.md exists")
    if not path.exists():
        continue
    fm = frontmatter(path)
    check(bool(fm), f"{name}: valid frontmatter between --- lines")
    check(fm.get("name") == name, f"{name}: 'name' is '{name}' (found '{fm.get('name', '')}')")
    check(len(fm.get("description", "")) >= 40, f"{name}: description says what it does and when to use it")
    tools = tool_set(fm.get("tools", ""))
    check(bool(tools), f"{name}: has a 'tools' allow-list (does not inherit everything)")
    if name in READ_ONLY:
        denied = tool_set(fm.get("disallowedTools", ""))
        leaked = (tools & WRITE_TOOLS) - denied
        check(not leaked, f"{name}: read-only, no Edit or Write in tools")
    body = path.read_text(encoding="utf-8").split("---", 2)[-1].strip()
    check(len(body) >= 150, f"{name}: has a real prompt body (rules and output contract)")
    if name in {"reviewer", "security-reviewer"}:
        check("VERDICT" in body, f"{name}: prompt fixes a VERDICT line in its output contract")

impl_file = AGENTS / "implementer.md"
impl = tool_set(frontmatter(impl_file).get("tools", "")) if impl_file.exists() else set()
check(bool({"edit", "write"} & impl), "implementer can edit files")

tracked = run("git", "ls-files", ".claude/agents").stdout.split()
check(len(tracked) >= len(REQUIRED), f"agent files are committed ({len(tracked)} tracked)")

# --- The feature ----------------------------------------------------------
test_names = []
for tf in (BACKEND / "tests").glob("test_*.py"):
    test_names += [l for l in tf.read_text(encoding="utf-8").splitlines()
                   if l.startswith("def test_") and "refund_status" in l]
check(len(test_names) >= 4, f"at least 4 tests with 'refund_status' in the name (found {len(test_names)})")

selected = run("uv", "run", "pytest", "-q", "-k", "refund_status", cwd=BACKEND)
passed = re.search(r"(\d+) passed", selected.stdout)
check(selected.returncode == 0 and passed is not None and int(passed.group(1)) >= 4,
      "the refund_status tests exist and pass")

probe = (
    "from app import rules\n"
    "print(rules.refund_status(10000, 0), rules.refund_status(10000, 4000), "
    "rules.refund_status(10000, 10000), rules.refund_status(0, 0))\n"
)
result = run("uv", "run", "python", "-c", probe, cwd=BACKEND)
check(result.stdout.split() == ["none", "partial", "full", "none"],
      f"rules.refund_status gives none/partial/full/none (got: {result.stdout.strip() or result.stderr.strip()[-80:]})")

api_probe = r'''
import os, tempfile
from datetime import datetime
from fastapi.testclient import TestClient
from app.db import connect
from app.main import app, get_now
from app.seed import seed

NOW = datetime(2030, 3, 1, 10, 0, 0)
path = os.path.join(tempfile.mkdtemp(), "probe.db")
os.environ["ORDERLOOP_DB"] = path
conn = connect(path); seed(conn, NOW); conn.close()
app.dependency_overrides[get_now] = lambda: NOW
c = TestClient(app)
c.post("/orders/1002/refunds", json={"amount_cents": 9500, "reason": "Did not fit"}, headers={"Idempotency-Key": "p1"})
rows = {r["id"]: r for r in c.get("/orders").json()}
print("status", rows[1001].get("refund_status"), rows[1007].get("refund_status"), rows[1002].get("refund_status"))
print("cents", rows[1007].get("refunded_cents"))
print("filter", [r["id"] for r in c.get("/orders", params={"refund_status": "partial"}).json()])
print("bad", c.get("/orders", params={"refund_status": "bogus"}).status_code)
leak = {"email", "phone", "address", "reason", "customer_email", "customer_phone"}
print("leak", sorted(leak & set(rows[1007])))
'''
api = run("uv", "run", "python", "-c", api_probe, cwd=BACKEND)
out = {l.split(" ", 1)[0]: l.split(" ", 1)[1] for l in api.stdout.splitlines() if " " in l}
check(out.get("status") == "none partial full",
      f"GET /orders shows refund_status none/partial/full (got: {out.get('status', api.stderr.strip()[-80:])})")
check(out.get("cents") == "5000", "GET /orders shows refunded_cents")
check(out.get("filter") == "[1007]", "?refund_status=partial returns only the part-refunded order")
check(out.get("bad") == "422", "an unknown refund_status filter is rejected with 422")
check(out.get("leak") == "[]", "the order list exposes no email, phone, address or reason")

full = run("uv", "run", "pytest", "-q", cwd=BACKEND)
check(full.returncode == 0, "the whole backend test suite passes")

log = run("git", "log", "--oneline", "main..HEAD").stdout.strip()
check(bool(log), "at least one commit on your branch")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
