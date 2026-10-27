"""OrderLoop MCP server (read-only). Server name: orderloop.

Tools:
  lookup_order(order_id)             order facts, customer contact details masked
  check_refund_eligibility(order_id) the refund rules applied to one order
  list_orders_needing_attention()    orders a support agent should look at

Run (from the repository root):
  uv run --project backend --group mcp python mcp/orderloop_server.py

The database is read from $ORDERLOOP_DB (default: the backend's default
backend/orderloop.db) and is opened read-only. Never print to stdout in this
file: stdout is the MCP protocol channel. Log to stderr if you need to.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# The server reuses the application's own rules and database helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import rules  # noqa: E402
from app.db import db_path  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

mcp = MCPServer(
    "orderloop",
    instructions=(
        "Read-only access to OrderLoop orders and the refund rules. "
        "Money is integer cents. Customer email and phone are masked. "
        "These tools cannot create or change refunds."
    ),
)


def _connect() -> sqlite3.Connection:
    path = Path(db_path()).resolve()
    if not path.exists():
        raise ToolError(f"Database not found at {path}. Run 'uv run python -m app.seed' in backend/.")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def mask_email(email: str) -> str:
    """asha.verma@example.test -> a***@example.test"""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def mask_phone(phone: str) -> str:
    """+1-555-0101 -> ***-0101 (last four digits only)"""
    digits = [c for c in phone if c.isdigit()]
    return "***-" + "".join(digits[-4:]) if digits else "***"


def _load(conn: sqlite3.Connection, order_id: int):
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ToolError(f"Order {order_id} does not exist.")
    rows = conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    items = [
        rules.Item(r["sku"], r["name"], r["unit_price_cents"], r["qty"], bool(r["opened"]),
                   bool(r["final_sale"]), bool(r["gift_card"]))
        for r in rows
    ]
    refunds = conn.execute(
        "SELECT id, amount_cents, reason, created_at FROM refunds WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return order, items, [dict(r) for r in refunds]


def _eligibility(order, items, refunds, now: datetime) -> rules.Eligibility:
    delivered = datetime.fromisoformat(order["delivered_at"]) if order["delivered_at"] else None
    return rules.eligibility(delivered, items, sum(r["amount_cents"] for r in refunds), now)


@mcp.tool()
def lookup_order(order_id: int) -> dict:
    """Look up one OrderLoop order by its numeric id (for example 1002).

    Returns status, dates, line items (price in cents, flags for opened, final sale and gift card),
    refunds already issued, and the customer's name with email and phone MASKED.
    Use this first to read the facts of an order. It does not say whether a refund is allowed:
    use check_refund_eligibility for that. Read-only.
    """
    with _connect() as conn:
        order, items, refunds = _load(conn, order_id)
        customer = conn.execute("SELECT id, name, email, phone FROM customers WHERE id = ?",
                                (order["customer_id"],)).fetchone()
    return {
        "order_id": order["id"],
        "status": order["status"],
        "placed_at": order["placed_at"],
        "delivered_at": order["delivered_at"],
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "email_masked": mask_email(customer["email"]),
            "phone_masked": mask_phone(customer["phone"]),
        },
        "items": [i.__dict__ | {"total_cents": i.total_cents, "refundable": i.refundable} for i in items],
        "refunds": refunds,
    }


@mcp.tool()
def check_refund_eligibility(order_id: int) -> dict:
    """Apply OrderLoop's refund rules to one order (numeric id) and return the result.

    Returns eligible (bool), days_since_delivery, late (more than 30 days after delivery),
    max_refundable_cents (what is still refundable, after earlier refunds), qualifying_skus,
    blockers (for example not_delivered, no_refundable_items, nothing_left_to_refund),
    and the policy limits: window_days and lead_approval_threshold_cents.
    It reports facts only. It never creates a refund and never decides for the agent. Read-only.
    """
    with _connect() as conn:
        order, items, refunds = _load(conn, order_id)
    el = _eligibility(order, items, refunds, _now())
    return {
        "order_id": order_id,
        "eligible": el.eligible,
        "days_since_delivery": el.days_since_delivery,
        "late": el.late,
        "max_refundable_cents": el.max_refundable_cents,
        "qualifying_skus": el.qualifying_skus,
        "blockers": el.blockers,
        "window_days": rules.REFUND_WINDOW_DAYS,
        "lead_approval_threshold_cents": rules.LEAD_APPROVAL_THRESHOLD_CENTS,
    }


@mcp.tool()
def list_orders_needing_attention() -> list[dict]:
    """List orders a support agent should look at, each with the reasons.

    Reasons: late (past the refund window), not_delivered, high_value (refundable amount above the
    lead-approval threshold), part_refunded. Orders with no reason are left out. Read-only.
    Returns a list of {order_id, status, reasons}.
    """
    now = _now()
    found: list[dict] = []
    with _connect() as conn:
        for row in conn.execute("SELECT id FROM orders ORDER BY id").fetchall():
            order, items, refunds = _load(conn, row["id"])
            el = _eligibility(order, items, refunds, now)
            reasons = []
            if el.late:
                reasons.append("late")
            if "not_delivered" in el.blockers:
                reasons.append("not_delivered")
            if el.max_refundable_cents > rules.LEAD_APPROVAL_THRESHOLD_CENTS:
                reasons.append("high_value")
            if refunds:
                reasons.append("part_refunded")
            if reasons:
                found.append({"order_id": order["id"], "status": order["status"], "reasons": reasons})
    return found


if __name__ == "__main__":
    mcp.run()  # stdio transport
