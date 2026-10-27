"""PreToolUse guard: block reads of .env and seed/customers.csv.

Fail closed: any problem reading the input blocks the call.
Exit 2 = block; the text on stderr is shown to Claude as the reason.
"""

import json
import os
import re
import shlex
import sys

SAFE_DIRS = ("backend", "frontend", "scripts")
SEARCHERS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "findstr"}
SECRET = re.compile(r"(^|[\s/\\\"'=<>(])\.env(\.(?!example\b)[\w.-]*)?($|[\s\"';|&<>)])", re.I)
CUSTOMERS = re.compile(r"customers\.csv|seed[/\\]\*", re.I)


def block(reason: str) -> None:
    print(f"Blocked by guard_secrets.py: {reason}", file=sys.stderr)
    sys.exit(2)


def protected_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    name = p.rsplit("/", 1)[-1]
    is_env = name == ".env" or (name.startswith(".env.") and name != ".env.example")
    return is_env or p.endswith("seed/customers.csv")


def recursive_search_is_unsafe(segment: str) -> bool:
    try:
        tokens = shlex.split(segment.replace("\\", "/"))
    except ValueError:
        return True
    while tokens and re.match(r"\w+=", tokens[0]):
        tokens.pop(0)
    if not tokens:
        return False
    tool = os.path.basename(tokens[0]).lower().removesuffix(".exe")
    args = tokens[1:]
    if tool == "git" and args[:1] == ["grep"]:
        tool, args = "rg", args[1:]
    if tool not in SEARCHERS:
        return False
    flags = [a for a in args if a.startswith("-") or a.lower() == "/s"]
    recursive = tool in {"rg", "ag", "ack"} or any(
        f in ("--recursive", "--dereference-recursive", "/s")
        or re.fullmatch(r"-[A-Za-z]*[rR][A-Za-z]*", f)
        for f in flags
    )
    if not recursive:
        return False
    operands = [a for a in args if not a.startswith("-") and a.lower() != "/s"]
    paths = operands[1:]  # first operand is the pattern
    if not paths:
        return True
    for p in paths:
        norm = p.replace("\\", "/").removeprefix("./")
        if ".." in norm.split("/") or not (norm + "/").startswith(tuple(d + "/" for d in SAFE_DIRS)):
            return True
    return False


def main() -> None:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        tool = event["tool_name"]
        tool_input = event["tool_input"]
    except Exception as exc:  # fail closed
        block(f"could not read the hook input ({exc.__class__.__name__})")

    if tool == "Read":
        if protected_path(str(tool_input.get("file_path", ""))):
            block("this file holds secrets or customer data. Use .env.example or ask the user.")
    elif tool == "Grep":
        path = str(tool_input.get("path") or ".")
        try:
            rel = os.path.relpath(path, event.get("cwd") or os.getcwd())
        except ValueError:
            rel = path
        rel = rel.replace("\\", "/")
        if protected_path(rel) or ".." in rel.split("/") or not (rel + "/").startswith(
            tuple(d + "/" for d in SAFE_DIRS)
        ):
            block("the Grep tool may search only backend/, frontend/ and scripts/. "
                  "Other places can expose .env and seed/customers.csv.")
    elif tool == "Bash":
        command = str(tool_input.get("command", ""))
        if SECRET.search(command) or CUSTOMERS.search(command):
            block("the command touches .env or seed/customers.csv. Do not read them in any way.")
        for segment in re.split(r"&&|\|\||;|\||\n", command):
            if recursive_search_is_unsafe(segment):
                block("recursive search outside backend/, frontend/ and scripts/ can expose "
                      ".env and seed/customers.csv. Search a specific source folder instead.")
    sys.exit(0)


try:
    main()
except Exception as exc:  # a bug in this script must not let a call through
    block(f"internal error ({exc.__class__.__name__})")
