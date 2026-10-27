"""Refund triage with the Claude Agent SDK (Lab 20).

Reads ONE order through a read-only tool and prints a typed recommendation as JSON.
It never issues a refund: a human (the support lead) decides.

  python agent/triage_agent.py --order 1003 --requested 7000 --dry-run   (no model, no cost)
  python agent/triage_agent.py --order 1003 --requested 7000             (calls Claude, costs money)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from order_facts import FIXED_NOW, fixture_connection, order_facts  # noqa: E402

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendation": {"type": "string", "enum": ["approve", "needs_lead", "reject"]},
        "approved_cents": {"type": "integer", "minimum": 0},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["recommendation", "approved_cents", "reasons"],
}

SYSTEM_PROMPT = (
    "You are a refund triage assistant for a support lead. "
    "Call get_order_facts exactly once for the order. Never guess amounts or eligibility: use the facts. "
    "Rules: not eligible -> reject. Late (late is true) or an amount above "
    "lead_approval_threshold_cents -> needs_lead. Otherwise approve the smaller of the requested "
    "amount and max_refundable_cents. approved_cents is 0 unless you approve. "
    "You only recommend; you cannot issue refunds."
)


def local_decision(facts: dict, requested_cents: int) -> dict:
    """The same rules in plain Python. Stands in for the model in --dry-run."""
    if "error" in facts:
        return {"recommendation": "reject", "approved_cents": 0, "reasons": [facts["error"]]}
    if not facts["eligible"]:
        return {"recommendation": "reject", "approved_cents": 0, "reasons": facts["blockers"]}
    amount = min(requested_cents, facts["max_refundable_cents"])
    if facts["late"]:
        return {"recommendation": "needs_lead", "approved_cents": 0, "reasons": ["late_request"]}
    if amount > facts["lead_approval_threshold_cents"]:
        return {"recommendation": "needs_lead", "approved_cents": 0, "reasons": ["above_threshold"]}
    return {"recommendation": "approve", "approved_cents": amount, "reasons": ["within_policy"]}


async def run_live(conn, now, order_id: int, requested: int, message: str,
                   model: str, max_turns: int, budget: float) -> dict:
    # Imported here so --dry-run works even where the SDK is not installed.
    from claude_agent_sdk import (
        ClaudeAgentOptions, ResultMessage, create_sdk_mcp_server, query, tool,
    )

    @tool("get_order_facts", "Read-only. Returns refund eligibility facts for one order id.", {"order_id": int})
    async def get_order_facts(args):
        facts = order_facts(conn, int(args["order_id"]), now)
        return {"content": [{"type": "text", "text": json.dumps(facts)}], "is_error": "error" in facts}

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"orderloop": create_sdk_mcp_server(name="orderloop", tools=[get_order_facts])},
        tools=[],                                          # no built-in tools at all
        allowed_tools=["mcp__orderloop__get_order_facts"],  # the one tool, pre-approved
        permission_mode="dontAsk",                          # anything else is denied, never prompted
        setting_sources=[],                                 # ignore user/project settings and hooks
        strict_mcp_config=True,                             # only the MCP servers listed above
        model=model,
        max_turns=max_turns,
        max_budget_usd=budget,
        output_format={"type": "json_schema", "schema": DECISION_SCHEMA},
    )
    prompt = f"Order {order_id}. The customer asks for {requested} cents back. Customer message: {message}"
    result = None
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                result = msg
    except Exception as exc:  # the SDK raises after an error result (budget, turns); keep what we saw
        if result is None:
            return {"recommendation": "reject", "approved_cents": 0, "reasons": [f"agent_failed:{type(exc).__name__}"]}
    if result is None or result.is_error or result.subtype != "success" or not result.structured_output:
        if result is None:
            subtype = "no_result"
        elif result.subtype != "success":
            subtype = result.subtype
        else:
            subtype = "api_error" if result.is_error else "no_structured_output"
        return {"recommendation": "reject", "approved_cents": 0, "reasons": [f"agent_failed:{subtype}"]}
    return {**result.structured_output, "cost_usd": result.total_cost_usd, "turns": result.num_turns}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--order", type=int, required=True)
    ap.add_argument("--requested", type=int, required=True, help="amount asked for, in cents")
    ap.add_argument("--message", default="I would like a refund, please.")
    ap.add_argument("--dry-run", action="store_true", help="no model call: apply the rules in Python")
    ap.add_argument("--model", default="haiku", help="model alias or full model name")
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--max-budget", type=float, default=0.25, help="USD cap for the run")
    args = ap.parse_args()

    conn, now = fixture_connection(), FIXED_NOW
    if args.dry_run:
        decision = local_decision(order_facts(conn, args.order, now), args.requested)
        mode = "dry-run"
    else:
        decision = asyncio.run(
            run_live(conn, now, args.order, args.requested, args.message, args.model,
                     args.max_turns, args.max_budget)
        )
        mode = "live"
    print(json.dumps({"order_id": args.order, "mode": mode, **decision}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
