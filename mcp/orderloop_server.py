"""OrderLoop MCP server (read-only). Run over stdio.

Tools: lookup_order, check_refund_eligibility, list_orders_needing_attention.
Resource: orderloop://refund-policy
Customer e-mail and phone are masked in every output. Logs go to stderr only.
"""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

# The app code lives in backend/app. Put backend/ on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from app import rules  # noqa: E402
from app.db import connect, db_path  # noqa: E402

log = logging.getLogger("orderloop")  # MCPServer sends logging to stderr
server = MCPServer("orderloop", instructions="Read-only access to OrderLoop orders and refund rules.")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)


def now() -> datetime:
    """The clock. Tests replace this function."""
    return datetime.now().replace(microsecond=0)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def mask_phone(phone: str) -> str:
    digits = [c for c in phone if c.isdigit()]
    return "***" + "".join(digits[-4:]) if len(digits) >= 4 else "***"


def open_db() -> sqlite3.Connection:
    path = db_path()
    if not Path(path).exists():  # connect() would silently create an empty file
        raise ToolError("The OrderLoop database does not exist. Seed it: cd backend && uv run python -m app.seed")
    conn = connect(path)
    conn.execute("PRAGMA query_only = ON")  # the server can never write
    try:
        conn.execute("SELECT 1 FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        conn.close()
        raise ToolError("The OrderLoop database has no tables. Seed it: cd backend && uv run python -m app.seed")
    return conn


def load(conn: sqlite3.Connection, order_id: int):
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ToolError(f"Order {order_id} does not exist.")
    rows = conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    items = [
        rules.Item(r["sku"], r["name"], r["unit_price_cents"], r["qty"],
                   bool(r["opened"]), bool(r["final_sale"]), bool(r["gift_card"]))
        for r in rows
    ]
    refunded = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    return order, items, refunded


def eligibility_for(order, items, refunded) -> rules.Eligibility:
    delivered = datetime.fromisoformat(order["delivered_at"]) if order["delivered_at"] else None
    return rules.eligibility(delivered, items, refunded, now())


@server.tool(annotations=READ_ONLY)
def lookup_order(order_id: Annotated[int, Field(gt=0, description="Order number, e.g. 1001")]) -> dict[str, Any]:
    """Look up one order: status, dates, items, refunds so far and the customer's masked contact details."""
    log.info("lookup_order %s", order_id)
    with open_db() as conn:
        order, items, refunded = load(conn, order_id)
        customer = conn.execute("SELECT name, email, phone FROM customers WHERE id = ?",
                                (order["customer_id"],)).fetchone()
        refunds = conn.execute(
            "SELECT amount_cents, created_at FROM refunds WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()
    return {
        "order_id": order["id"],
        "status": order["status"],
        "placed_at": order["placed_at"],
        "delivered_at": order["delivered_at"],
        "customer": {
            "name": customer["name"],
            "email": mask_email(customer["email"]),
            "phone": mask_phone(customer["phone"]),
        },
        "items": [
            {"sku": i.sku, "name": i.name, "unit_price_cents": i.unit_price_cents, "qty": i.qty,
             "opened": i.opened, "final_sale": i.final_sale, "gift_card": i.gift_card}
            for i in items
        ],
        "refunded_cents": refunded,
        "refunds": [dict(r) for r in refunds],
    }


@server.tool(annotations=READ_ONLY)
def check_refund_eligibility(order_id: Annotated[int, Field(gt=0, description="Order number, e.g. 1001")]) -> dict[str, Any]:
    """Say whether an order can be refunded under the refund rules, and the most that can be refunded (integer cents). Does not create a refund."""
    log.info("check_refund_eligibility %s", order_id)
    with open_db() as conn:
        order, items, refunded = load(conn, order_id)
    el = eligibility_for(order, items, refunded)
    return {
        "order_id": order_id,
        "eligible": el.eligible,
        "late": el.late,
        "days_since_delivery": el.days_since_delivery,
        "max_refundable_cents": el.max_refundable_cents,
        "qualifying_skus": el.qualifying_skus,
        "blockers": el.blockers,
        "lead_approval_threshold_cents": rules.LEAD_APPROVAL_THRESHOLD_CENTS,
    }


@server.tool(annotations=READ_ONLY)
def list_orders_needing_attention() -> dict[str, Any]:
    """List refundable orders a person should look at: late ones, ones above the lead-approval threshold, and part-refunded ones."""
    log.info("list_orders_needing_attention")
    found = []
    with open_db() as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM orders ORDER BY id")]
        for order_id in ids:
            order, items, refunded = load(conn, order_id)
            el = eligibility_for(order, items, refunded)
            if not el.eligible:
                continue
            flags = []
            if el.late:
                flags.append("late")
            if el.max_refundable_cents > rules.LEAD_APPROVAL_THRESHOLD_CENTS:
                flags.append("above_lead_threshold")
            if refunded > 0:
                flags.append("partially_refunded")
            if flags:
                name = conn.execute("SELECT name FROM customers WHERE id = ?", (order["customer_id"],)).fetchone()[0]
                found.append({"order_id": order_id, "customer_name": name, "flags": flags,
                              "max_refundable_cents": el.max_refundable_cents})
    return {"count": len(found), "orders": found}


@server.resource("orderloop://refund-policy", mime_type="text/plain")
def refund_policy() -> str:
    """The refund rules the OrderLoop app enforces."""
    return (
        f"Refund window: {rules.REFUND_WINDOW_DAYS} days from delivery (exactly {rules.REFUND_WINDOW_DAYS} is on time).\n"
        "Late refunds need a support lead.\n"
        "Final-sale items and gift cards cannot be refunded.\n"
        "A refund can never exceed what remains after earlier refunds.\n"
        f"Refunds above {rules.LEAD_APPROVAL_THRESHOLD_CENTS} cents need lead approval.\n"
        f"A refund reason is {rules.MIN_REASON_LENGTH} to {rules.MAX_REASON_LENGTH} characters.\n"
    )


if __name__ == "__main__":
    server.run()  # stdio
