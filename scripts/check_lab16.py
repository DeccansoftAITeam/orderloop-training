"""Check for Lab 16 (Review and audit). Standard library only.

Run from the repository root:  python scripts/check_lab16.py

It reads your REVIEW.md and checks that you found each problem planted in the
pull request on the branch `flawed-pr`, that each finding cites file:line in the
changed files of that branch, and that each sits under a severity heading.
"""

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


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def git_show(ref: str, path: str) -> str | None:
    res = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else None


LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4, "blocker": 4}

# id, label, minimum severity, locations (file, start anchor, end anchor or None), keyword groups.
# A finding must cite one of the locations (+/- 2 lines) and match every keyword group.
FLAWS = [
    ("weak_test", "a test was weakened to hide a changed rule", "high",
     [("backend/tests/test_rules.py", "assert el.eligible", None),
      ("backend/app/rules.py", "days >= REFUND_WINDOW_DAYS", None)],
     [r"weaken|loosen|remov|dropp|delet|relax|weaker|no longer assert|missing assert",
      r"\blate\b|30|>=|boundary|window"]),
    ("pii_logged", "customer personal data is written to the log", "high",
     [("backend/app/main.py", "log.info(", None)],
     [r"pii|personal|e-?mail|phone|customer", r"\blog"]),
    ("float_money", "money is calculated with floats", "medium",
     [("backend/app/rules.py", "def goodwill_credit", None),
      ("backend/app/main.py", "rules.round_to_cents", None)],
     [r"float|floating"]),
    ("new_dependency", "an unrequested dependency was added", "low",
     [("backend/pyproject.toml", '"arrow', None),
      ("backend/app/main.py", "import arrow", None)],
     [r"depend|arrow|package|library"]),
    ("hallucinated_helper", "the code calls a helper that does not exist", "medium",
     [("backend/app/main.py", "round_to_cents", None)],
     [r"round_to_cents",
      r"exist|hallucin|invent|undefined|not defined|missing|attributeerror|no such|made.?up|fabricat"]),
    ("no_idempotency", "the new endpoint has no idempotency check", "high",
     [("backend/app/main.py", "def goodwill_credit",
       'return {"id": cur.lastrowid, "order_id": order_id, "amount_cents": amount')],
     [r"idempoten|twice|duplicate|double|replay|retry"]),
]


def resolve_ref() -> str | None:
    for ref in ("flawed-pr", "origin/flawed-pr", "upstream/flawed-pr"):
        if git("rev-parse", "--verify", "--quiet", ref):
            return ref
    return None


def line_range(ref: str, file: str, start: str, end: str | None):
    text = git_show(ref, file)
    if text is None:
        return None
    lines = text.splitlines()
    first = next((i for i, ln in enumerate(lines, 1) if start in ln), None)
    if first is None:
        return None
    last = first
    if end:
        last = next((i for i, ln in enumerate(lines, 1) if i >= first and end in ln), first)
    return first - 2, last + 2


CITE = re.compile(r"([\w./\\-]+\.(?:py|toml|lock|md)):(\d+)(?:\s*[-–]\s*(\d+))?")
SEV = re.compile(r"\b(critical|blocker|high|medium|low)\b", re.I)


def units_of(text: str):
    """Split REVIEW.md into (severity, text) units: one per bullet, paragraph or sub-heading."""
    units: list[tuple[str | None, str]] = []
    current: list[str] = []
    severity: str | None = None

    def flush():
        nonlocal current
        body = " ".join(current).strip()
        if body:
            sev = severity
            inline = re.search(r"(?:severity\s*[:=]\s*|\[|\()\s*(critical|blocker|high|medium|low)\b", body, re.I)
            if inline:
                sev = inline.group(1).lower()
            units.append((sev, body))
        current = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = re.match(r"#{1,6}\s+(.*)", line)
        if heading:
            flush()
            title = heading.group(1)
            m = SEV.search(title)
            if m and not CITE.search(title):
                severity = m.group(1).lower()
            elif re.match(r"#{1,2}\s", line):
                severity = None
            if CITE.search(title):
                current = [title]
            continue
        if re.match(r"([-*+]|\d+[.)])\s", line):
            flush()
        current.append(line)
    flush()
    return units


# --- branch and file -----------------------------------------------------
branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")
ref = resolve_ref()
check(ref is not None, "the branch flawed-pr is available (run: git fetch origin flawed-pr)")

review_path = ROOT / "REVIEW.md"
check(review_path.exists(), "REVIEW.md exists in the repository root")
text = review_path.read_text(encoding="utf-8", errors="replace") if review_path.exists() else ""
check(len(text) > 600, "REVIEW.md has real content")

sev_headings = {
    m.group(1).lower()
    for m in re.finditer(r"^#{1,6}\s+.*?\b(critical|blocker|high|medium|low)\b", text, re.I | re.M)
}
check(len(sev_headings) >= 2, "findings are grouped under severity headings (for example '## High', '## Medium')")

# --- the planted problems ------------------------------------------------
units = units_of(text)
matched_units: dict[int, list[str]] = {}
for fid, label, min_sev, locations, groups in FLAWS:
    if ref is None:
        check(False, f"finding: {label}")
        continue
    ranges = []
    for file, start, end in locations:
        rng = line_range(ref, file, start, end)
        if rng:
            ranges.append((file, rng))
    if not ranges:
        check(False, f"finding: {label} (flawed-pr no longer has the expected code; tell the trainer)")
        continue
    found, found_sev = False, None
    for idx, (sev, body) in enumerate(units):
        if not all(re.search(g, body, re.I) for g in groups):
            continue
        for m in CITE.finditer(body):
            name = m.group(1).replace("\\", "/")
            lo = int(m.group(2))
            hi = int(m.group(3) or lo)
            for file, (a, b) in ranges:
                if name.endswith(file.split("/")[-1]) and lo <= b and hi >= a:
                    found, found_sev = True, sev
                    matched_units.setdefault(idx, []).append(fid)
                    break
            if found:
                break
        if found:
            break
    where = " or ".join(f"{f}:{r[0] + 2}" for f, r in ranges)
    check(found, f"finding: {label}, citing file:line (near {where})")
    if found:
        ok_sev = found_sev is not None and LEVELS.get(found_sev, 0) >= LEVELS[min_sev]
        check(ok_sev, f"  severity of '{fid}' is at least {min_sev} (yours: {found_sev})")

lumped = [idx for idx, ids in matched_units.items() if len(set(ids)) >= 3]
check(not lumped, "one finding per problem (do not lump three or more problems into one item)")

# --- verdict and tool results -------------------------------------------
check(bool(re.search(r"request(ed)? changes|do not merge|don'?t merge|reject|not ready to merge", text, re.I)),
      "REVIEW.md gives a verdict: request changes / do not merge")
check("code-review" in text.lower() and bool(re.search(r"false.positive", text, re.I)),
      "REVIEW.md records what /code-review found and discusses false positives")
check(bool(re.search(r"missed|did not (find|catch)|didn'?t (find|catch)|only the checklist|not caught", text, re.I)),
      "REVIEW.md says what the tool missed or what only the checklist caught")

# --- git hygiene ---------------------------------------------------------
check(git("ls-files", "REVIEW.md") != "", "REVIEW.md is committed")
check(git("status", "--porcelain", "--", "REVIEW.md") == "", "no uncommitted changes in REVIEW.md")
if git("rev-parse", "--verify", "--quiet", "main"):
    check(git("diff", "--name-only", "main...HEAD", "--", "backend") == "",
          "you did not change backend/ on your branch (a review does not fix the pull request)")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
