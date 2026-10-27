"""Check for Lab 18 (Security and guardrails). Standard library only.

Run from the repository root:  python scripts/check_lab18.py

It does not call a model. It checks your control files, runs the secret scanner and your
pre-commit hook on throw-away input, and reads your findings table.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def run(*args: str, cwd: Path = ROOT):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)


branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- the control for tool actions (Module 8 permissions) -------------------------
settings_path = ROOT / ".claude" / "ticket-reader.settings.json"
check(settings_path.exists(), ".claude/ticket-reader.settings.json exists")
deny: list[str] = []
if settings_path.exists():
    try:
        deny = json.loads(settings_path.read_text(encoding="utf-8"))["permissions"]["deny"]
        check(True, "ticket-reader.settings.json is valid JSON with permissions.deny")
    except Exception as exc:
        check(False, f"ticket-reader.settings.json is valid JSON with permissions.deny ({exc.__class__.__name__})")
names = {d.split("(")[0] for d in deny if isinstance(d, str)}
for tool in ("Write", "Edit", "Bash", "WebFetch"):
    check(tool in names, f"the ticket reader is denied {tool}")
check("Read" not in names, "the ticket reader may still Read (it has to open the ticket)")

# --- secrets: working tree clean, source reads env, history still remembers ------
scan = run("scripts/secret_scan.py")
check(scan.returncode == 0, "secret scan of the working tree is clean" + ("" if scan.returncode == 0 else f" ({scan.stdout.strip().splitlines()[0]})"))
digest = ROOT / "scripts" / "send_digest.py"
text = digest.read_text(encoding="utf-8") if digest.exists() else ""
check("os.environ" in text or "getenv" in text, "scripts/send_digest.py reads its credentials from environment variables")
check(git("ls-files", "scripts/send_digest.py") != "", "scripts/send_digest.py is still tracked (you fixed it, you did not delete the evidence)")
hist = run("scripts/secret_scan.py", "--history")
check(hist.returncode == 1, "history scan still finds the old key (removing it from the latest commit does not erase it)")

# --- pre-commit hook -------------------------------------------------------------
hook = ROOT / ".githooks" / "pre-commit"
check(hook.exists(), ".githooks/pre-commit exists")
check(git("config", "core.hooksPath") == ".githooks", "git is configured with core.hooksPath = .githooks")
hook_text = hook.read_text(encoding="utf-8") if hook.exists() else ""
check(b"" not in (hook.read_bytes() if hook.exists() else b""), "the hook uses LF line endings (VS Code status bar: click CRLF, choose LF)")
check("secret_scan.py" in hook_text and "--staged" in hook_text, "the hook runs secret_scan.py --staged")
tmp = Path(tempfile.mkdtemp(prefix="lab18-"))
try:
    if hook.exists():
        (tmp / "scripts").mkdir()
        (tmp / ".githooks").mkdir()
        shutil.copy(ROOT / "scripts" / "secret_scan.py", tmp / "scripts" / "secret_scan.py")
        shutil.copy(hook, tmp / ".githooks" / "pre-commit")
        subprocess.run(["git", "init", "-q"], cwd=tmp)
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=tmp)
        ident = ["-c", "user.name=t", "-c", "user.email=t@example.test"]
        (tmp / "ok.txt").write_text("nothing secret here\n", encoding="utf-8")
        subprocess.run(["git", "add", "ok.txt"], cwd=tmp)
        good = subprocess.run(["git", *ident, "commit", "-q", "-m", "ok"], cwd=tmp, capture_output=True, text=True)
        (tmp / "bad.txt").write_text("API_KEY = 'sk-" + "FAKE-" + "0123456789abcdef0123'\n", encoding="utf-8")
        subprocess.run(["git", "add", "bad.txt"], cwd=tmp)
        bad = subprocess.run(["git", *ident, "commit", "-q", "-m", "bad"], cwd=tmp, capture_output=True, text=True)
        check(good.returncode == 0, "the hook lets a clean commit through")
        check(bad.returncode != 0, "the hook blocks a commit that stages a fake key")
    else:
        check(False, "the hook lets a clean commit through")
        check(False, "the hook blocks a commit that stages a fake key")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- findings table ---------------------------------------------------------------
findings = ROOT / "docs" / "lab18-findings.md"
check(findings.exists(), "docs/lab18-findings.md exists")
body = findings.read_text(encoding="utf-8") if findings.exists() else ""
rows = {}
for line in body.splitlines():
    if line.strip().startswith("|"):
        cells = [c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
        if cells:
            rows[cells[0].lower()] = cells
for label in ("baseline", "fooled-baseline", "fooled-deny", "fenced"):
    cells = rows.get(label)
    ok = bool(cells) and len(cells) >= 3 and cells[1].lower() in ("yes", "no") and cells[2].lower() in ("yes", "no")
    check(ok, f"findings table has a '{label}' row with yes/no in the ACTION and TEXT columns")
if "fooled-deny" in rows and len(rows["fooled-deny"]) >= 2:
    check(rows["fooled-deny"][1].lower() == "no", "with the deny rules, even a fooled agent could not create the file (ACTION = no)")
low = body.lower()
check(re.search(r"push protection:\s*(enabled|not available)", low) is not None, "findings records 'Push protection: enabled' (or 'not available')")
check(re.search(r"rotat", low) is not None, "findings says what happens to the old key (rotate it)")
check(len(re.findall(r"^\|.*\|\s*$", body, re.M)) >= 12, "findings holds the threat-model table and the run table")
check("sk-FAKE" not in body, "findings does not paste the key")

# --- committed ---------------------------------------------------------------------
tracked = git("ls-files", ".claude/ticket-reader.settings.json", ".githooks/pre-commit", "docs/lab18-findings.md")
check(len(tracked.splitlines()) == 3, "settings file, hook and findings are tracked by git")
check(git("status", "--porcelain", "--", ".claude", ".githooks", "docs", "scripts") == "", "no uncommitted changes in .claude, .githooks, docs and scripts")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
