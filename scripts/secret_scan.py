"""A small secret scanner for Lab 18. Standard library only.

    python scripts/secret_scan.py              scan the working tree (tracked + untracked, not ignored)
    python scripts/secret_scan.py --staged     scan only what is staged (use it from a pre-commit hook)
    python scripts/secret_scan.py --history    scan every line ever added in any commit (git log -p --all)

Exit code 0 = nothing found, 1 = something found. Found values are shown redacted.
A line that ends with the comment  scan:allow  is skipped.

This is a teaching tool. Real projects use gitleaks, trufflehog or GitHub secret scanning.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RULES = {
    "api-key-prefix": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    "aws-access-key-id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "assigned-secret": re.compile(
        r"""(?ix)(password|passwd|secret|token|api[_-]?key)\w*\s*[:=]\s*["'][^"'\s]{8,}["']"""
    ),
}

# Course scaffolding that holds fake values on purpose, and files that are not source.
SKIP_PATHS = ("scripts/check_lab", "scripts/secret_scan.py", "backend/uv.lock", "frontend/package-lock.json")
SKIP_NAMES = {".env.example"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".db", ".woff", ".woff2"}


def skipped(path: str) -> bool:
    p = path.replace("\\", "/")
    return (
        p.startswith(SKIP_PATHS)
        or p.rsplit("/", 1)[-1] in SKIP_NAMES
        or Path(p).suffix.lower() in BINARY_SUFFIXES
        or "/node_modules/" in "/" + p
    )


def redact(value: str) -> str:
    return value[:6] + "***" if len(value) > 6 else "***"


def scan_line(line: str) -> list[tuple[str, str]]:
    if "scan:allow" in line:
        return []
    return [(name, m.group(0)) for name, rx in RULES.items() for m in rx.finditer(line)]


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout


def scan_files(paths: list[str], staged: bool) -> list[str]:
    found = []
    for path in paths:
        if not path or skipped(path):
            continue
        if staged:
            text = git("show", f":{path}")
        else:
            try:
                text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            except (OSError, IsADirectoryError):
                continue
        for number, line in enumerate(text.splitlines(), start=1):
            for name, value in scan_line(line):
                found.append(f"{path}:{number}  {name}  {redact(value)}")
    return found


def scan_history() -> list[str]:
    found, commit, path = [], "", ""
    log = git("log", "-p", "--all", "--no-color", "--format=commit %h", "-U0")
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line.split()[1]
        elif line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and path and not skipped(path):
            for name, value in scan_line(line[1:]):
                found.append(f"commit {commit}  {path}  {name}  {redact(value)}")
    return sorted(set(found))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="scan staged changes only")
    mode.add_argument("--history", action="store_true", help="scan all of git history")
    args = parser.parse_args()

    if args.history:
        findings, where = scan_history(), "git history"
    elif args.staged:
        findings, where = scan_files(git("diff", "--cached", "--name-only", "--diff-filter=ACM").splitlines(), True), "staged files"
    else:
        findings, where = scan_files(git("ls-files", "-co", "--exclude-standard").splitlines(), False), "working tree"

    for item in findings:
        print("FOUND ", item)
    if findings:
        print(f"\n{len(findings)} possible secret(s) in the {where}.")
        if args.history:
            print("Removing a secret from the latest commit does not remove it from history. Rotate it.")
        return 1
    print(f"No secrets found in the {where}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
