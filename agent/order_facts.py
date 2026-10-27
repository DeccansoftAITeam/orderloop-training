"""Read-only order facts for the Lab 20 agent.

One small function that looks an order up and applies the refund rules from
backend/app/rules.py. It never writes to the database and never returns
customer name, email, phone or address.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import rules  # noqa: E402
from app.db import connect  # noqa: E402
from app.seed import seed  # noqa: E402

FIXED_NOW = datetime(2030, 3, 1, 10, 0, 0)


def fixture_connection(now: datetime = FIXED_NOW) -> sqlite3.Connection:
    """An in-memory database with the synthetic seed data, at a fixed date.

    Used by --dry-run so results never depend on today's date.
    """
    conn = connect(":memory:")
    seed(conn, now)
    return conn


def order_facts(conn: sqlite3.Connection, order_id: int, now: datetime) -> dict:
    """Return the facts about one order, or {"error": ...} if it does not exist."""
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        return {"error": f"order {order_id} does not exist"}
    rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    items = [
        rules.Item(r["sku"], r["name"], r["unit_price_cents"], r["qty"], bool(r["opened"]),
                   bool(r["final_sale"]), bool(r["gift_card"]))
        for r in rows
    ]
    refunded = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    delivered = datetime.fromisoformat(order["delivered_at"]) if order["delivered_at"] else None
    el = rules.eligibility(delivered, items, refunded, now)
    return {
        "order_id": order_id,
        "eligible": el.eligible,
        "late": el.late,
        "days_since_delivery": el.days_since_delivery,
        "max_refundable_cents": el.max_refundable_cents,
        "already_refunded_cents": refunded,
        "blockers": el.blockers,
        "lead_approval_threshold_cents": rules.LEAD_APPROVAL_THRESHOLD_CENTS,
    }
