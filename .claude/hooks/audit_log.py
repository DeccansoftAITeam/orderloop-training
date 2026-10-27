"""PreToolUse audit hook: append one line per tool call to .claude/audit.log.

Logs the tool and a short, redacted target. Never logs prompts, file contents or
customer data. Fail open: an audit problem must never stop the work.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\+?\d[\d\s().-]{6,}\d"), "[PHONE]"),
    (re.compile(r"\b(sk|pk|ghp|xox[a-z])[-_][\w-]{6,}"), "[KEY]"),
    (re.compile(r"(?i)\b([\w]*(key|token|password|secret)[\w]*)=\S+"), r"\1=[REDACTED]"),
]


def redact(text: str) -> str:
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    return text[:120]


def main() -> None:
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    tool_input = event.get("tool_input") or {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    target = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") or ""
    line = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session": str(event.get("session_id", ""))[:8],
        "tool": event.get("tool_name", ""),
        "target": redact(str(target).replace(str(root), ".")),
    }
    log = root / ".claude" / "audit.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


try:
    main()
except Exception:
    pass  # fail open
sys.exit(0)
