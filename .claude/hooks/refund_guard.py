"""PreToolUse guard for the Refund Triage agent. Standard library only.

Blocks (exit code 2, reason on stderr):
  1. Any call that would create or change a refund outside the console:
     a Bash command that posts to /refunds, writes to the refunds table, or opens the database file.
  2. Any call from the refund-triage subagent to a tool other than its two read tools.
  3. Any orderloop MCP tool that is not one of the three known read-only tools.
Fails closed: input it cannot read blocks the call.
"""

import json
import re
import sys

ALLOWED_FOR_AGENT = {
    "mcp__orderloop__lookup_order",
    "mcp__orderloop__check_refund_eligibility",
}
# Claude Code's own tool for handing a subagent's report back (auto mode). Not ours to block.
HARNESS_TOOLS = {"SubagentHandback"}
KNOWN_ORDERLOOP_TOOLS = ALLOWED_FOR_AGENT | {"mcp__orderloop__list_orders_needing_attention"}
REFUND_WRITE = re.compile(
    r"/refunds\b|insert\s+into\s+refunds|update\s+refunds|delete\s+from\s+refunds|orderloop\.db",
    re.IGNORECASE,
)


def block(reason: str) -> None:
    print(f"Blocked by refund_guard.py: {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        tool = event["tool_name"]
        tool_input = event.get("tool_input") or {}
    except Exception as exc:  # fail closed
        block(f"could not read the hook input ({exc}).")

    agent = event.get("agent_type")

    if tool.startswith("mcp__orderloop__") and tool not in KNOWN_ORDERLOOP_TOOLS:
        block(f"{tool} is not a known read-only orderloop tool.")

    if agent == "refund-triage" and tool not in ALLOWED_FOR_AGENT | HARNESS_TOOLS:
        block(f"the refund-triage agent may only call lookup_order and check_refund_eligibility, not {tool}.")

    if tool == "Bash" and REFUND_WRITE.search(str(tool_input.get("command", ""))):
        block("refunds are recorded by a human in the OrderLoop console, never from a command.")

    sys.exit(0)


main()
