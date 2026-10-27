"""Check for Lab 13 (Parallel work). Standard library only.

Run from the repository root:  python scripts/check_lab13.py

It checks the merged result of the three work packages (backend endpoint,
frontend filter, API docs), that each lane stayed inside the files it owns,
and that the git history shows three lane branches merged with the shared
CHANGELOG conflict resolved.
"""

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def run(*cmd: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True)


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


branch = run("git", "branch", "--show-current").stdout.strip()
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")
base = "lab-13-start" if run("git", "rev-parse", "--verify", "-q", "lab-13-start").returncode == 0 else "main"

# --- lane A: backend endpoint -------------------------------------------------
stats = read("backend/app/stats.py")
check("def refund_stats" in stats, "backend/app/stats.py defines refund_stats")
check("/stats/refunds" in read("backend/app/main.py"), "main.py has the /stats/refunds route")
tests = read("backend/tests/test_stats.py")
check(len(re.findall(r"^def test_\w+", tests, re.M)) >= 2, "backend/tests/test_stats.py has at least 2 tests")

probe = f"""
import os, sys, tempfile
from datetime import datetime
sys.path.insert(0, {str(BACKEND)!r})
from app.db import connect
from app.seed import seed
from app import stats
path = os.path.join(tempfile.mkdtemp(), "probe.db")
conn = connect(path)
seed(conn, datetime(2030, 3, 1, 10, 0, 0))
conn.execute("INSERT INTO refunds (order_id, amount_cents, reason, created_at, idempotency_key) VALUES (1001, 2500, 'probe one', '2030-03-01', 'p-1')")
conn.execute("INSERT INTO refunds (order_id, amount_cents, reason, created_at, idempotency_key) VALUES (1001, 1000, 'probe two', '2030-03-01', 'p-2')")
conn.commit()
r = stats.refund_stats(conn)
print(r["refund_count"], r["refunded_cents"])
"""
res = run("uv", "run", "python", "-c", probe, cwd=BACKEND)
check(res.stdout.split() == ["3", "8500"], f"refund_stats counts 3 refunds worth 8500 cents on probe data (got {res.stdout.split() or res.stderr.strip()[-80:]})")

# --- lane B: frontend filter ----------------------------------------------------
app_tsx, api_ts = read("frontend/src/App.tsx"), read("frontend/src/api.ts")
check("<select" in app_tsx and "delivered" in app_tsx and "shipped" in app_tsx, "App.tsx has a <select> with the delivered and shipped options")
check(re.search(r"listOrders\s*=\s*\(\s*q\s*:\s*string\s*,\s*status", api_ts) is not None, "api.ts: listOrders takes a status argument")
check("status=" in api_ts or "status" in api_ts.split("listOrders", 1)[-1], "api.ts sends the status parameter")

# --- lane C: docs -------------------------------------------------------------
api_md = read("docs/api.md")
for needle in ("/health", "/orders", "/orders/{id}", "/refunds", "/reply-draft"):
    check(needle in api_md, f"docs/api.md mentions {needle}")
check("/stats/refunds" not in api_md, "docs/api.md does not invent /stats/refunds (lane C did not know it)")

# --- the shared line ---------------------------------------------------------
log = read("CHANGELOG.md")
check("<<<<<<<" not in log and ">>>>>>>" not in log and "=======" not in log, "CHANGELOG.md holds no conflict markers")
unreleased = log.split("## Unreleased", 1)[-1].split("\n## ", 1)[0]
bullets = [l for l in unreleased.splitlines() if l.startswith("- ")]
check(len(bullets) == 2, f"CHANGELOG.md has exactly 2 bullets under Unreleased (found {len(bullets)})")
check(not any("each work package" in b for b in bullets), "the placeholder line is gone")
joined = unreleased.lower()
check(("stat" in joined or "refund" in joined) and ("filter" in joined or "status" in joined), "one bullet is about the stats endpoint and one about the status filter")

# --- tests -------------------------------------------------------------------
res = run("uv", "run", "pytest", "-q", cwd=BACKEND)
check(res.returncode == 0, "the whole backend test suite passes")
for f in ("backend/app/rules.py", ".claude/settings.json", ".claude/hooks/lane_guard.py", ".claude/lanes.json"):
    check(run("git", "diff", "--quiet", base, "--", f).returncode == 0, f"{f} is unchanged from {base}")

# --- git history: three lanes merged -------------------------------------------
lanes = json.loads(read(".claude/lanes.json") or "{}")
found: dict[str, str] = {}
for name in run("git", "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split():
    lane = re.sub(r"^worktree-", "", name)
    if lane in lanes:
        found[lane] = name
check(set(found) == set(lanes), f"lane branches wp-a, wp-b, wp-c still exist (found {sorted(found)})")
for lane, name in sorted(found.items()):
    merged = run("git", "merge-base", "--is-ancestor", name, "HEAD").returncode == 0
    check(merged, f"branch {name} is merged into {branch}")
    changed = run("git", "diff", "--name-only", f"{base}...{name}").stdout.split()
    outside = [f for f in changed if not any(fnmatch.fnmatch(f, p) for p in lanes[lane])]
    check(bool(changed) and not outside, f"lane {lane} changed only files it owns" + (f" (outside: {outside})" if outside else ""))
    own_commits = run("git", "log", "--no-merges", "--format=%h", f"{base}..{name}").stdout.split()
    check(len(own_commits) >= 1, f"lane {lane} has its own commit(s)")

merges = run("git", "log", "--merges", "--format=%h", f"{base}..HEAD").stdout.split()
check(len(merges) >= 3, f"at least 3 merge commits (git merge --no-ff, one per lane) (found {len(merges)})")

wt = [l for l in run("git", "worktree", "list", "--porcelain").stdout.splitlines() if l.startswith("worktree ")]
check(len(wt) == 1, f"the extra worktrees are removed (git worktree list shows {len(wt)})")
check(run("git", "status", "--porcelain").stdout.strip() == "", "working tree is clean")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
