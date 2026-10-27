import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import rules
from app.assistant import FakeDraftProvider, build_draft
from app.db import get_conn

app = FastAPI(title="OrderLoop API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_now() -> datetime:
    """The clock. Tests override this dependency."""
    return datetime.now().replace(microsecond=0)


class RefundRequest(BaseModel):
    amount_cents: int
    reason: str


class DraftRequest(BaseModel):
    message: str


def problem(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def load_order(conn: sqlite3.Connection, order_id: int):
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise problem(404, "order_not_found", f"Order {order_id} does not exist.")
    rows = conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    items = [
        rules.Item(r["sku"], r["name"], r["unit_price_cents"], r["qty"], bool(r["opened"]),
                   bool(r["final_sale"]), bool(r["gift_card"]))
        for r in rows
    ]
    refunded = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    return order, items, refunded


def order_eligibility(order, items, refunded, now) -> rules.Eligibility:
    delivered = datetime.fromisoformat(order["delivered_at"]) if order["delivered_at"] else None
    return rules.eligibility(delivered, items, refunded, now)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/orders")
def list_orders(
    q: str | None = Query(None, description="Search by order id or customer name"),
    status: str | None = None,
    refund_status: Literal["none", "partial", "full"] | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    sql = (
        "SELECT o.id, o.status, o.placed_at, o.delivered_at, c.name AS customer_name, "
        "(SELECT COALESCE(SUM(unit_price_cents * qty), 0) FROM order_items WHERE order_id = o.id) AS total_cents, "
        "(SELECT COALESCE(SUM(unit_price_cents * qty), 0) FROM order_items "
        "WHERE order_id = o.id AND final_sale = 0 AND gift_card = 0) AS refundable_cents, "
        "(SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = o.id) AS refunded_cents "
        "FROM orders o JOIN customers c ON c.id = o.customer_id WHERE 1 = 1"
    )
    params: list = []
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    if q:
        sql += " AND (CAST(o.id AS TEXT) LIKE ? OR c.name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY o.id"
    orders = []
    for row in conn.execute(sql, params).fetchall():
        order = dict(row)
        order["refund_status"] = rules.refund_status(order.pop("refundable_cents"), order["refunded_cents"])
        if refund_status is None or order["refund_status"] == refund_status:
            orders.append(order)
    return orders


@app.get("/orders/{order_id}")
def get_order(order_id: int, conn: sqlite3.Connection = Depends(get_conn), now: datetime = Depends(get_now)):
    order, items, refunded = load_order(conn, order_id)
    customer = conn.execute("SELECT id, name FROM customers WHERE id = ?", (order["customer_id"],)).fetchone()
    refunds = conn.execute(
        "SELECT id, amount_cents, reason, created_at FROM refunds WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    el = order_eligibility(order, items, refunded, now)
    return {
        "id": order["id"],
        "status": order["status"],
        "placed_at": order["placed_at"],
        "delivered_at": order["delivered_at"],
        "customer": dict(customer),
        "items": [i.__dict__ | {"total_cents": i.total_cents, "refundable": i.refundable} for i in items],
        "refunds": [dict(r) for r in refunds],
        "eligibility": el.__dict__,
    }


@app.post("/orders/{order_id}/refunds", status_code=201)
def create_refund(
    order_id: int,
    body: RefundRequest,
    idempotency_key: str | None = Header(None),
    conn: sqlite3.Connection = Depends(get_conn),
    now: datetime = Depends(get_now),
):
    if not idempotency_key:
        raise problem(400, "idempotency_key_missing", "Send an Idempotency-Key header.")
    existing = conn.execute(
        "SELECT id, order_id, amount_cents, reason FROM refunds WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing:
        return {**dict(existing), "replayed": True}

    order, items, refunded = load_order(conn, order_id)
    decision = rules.decide(order_eligibility(order, items, refunded, now), body.amount_cents, body.reason)
    if not decision.ok:
        status = 422 if decision.code in {"reason_invalid", "amount_invalid", "exceeds_max"} else 409
        raise problem(status, decision.code, decision.message)

    cur = conn.execute(
        "INSERT INTO refunds (order_id, amount_cents, reason, created_at, idempotency_key) VALUES (?, ?, ?, ?, ?)",
        (order_id, body.amount_cents, body.reason.strip(), now.isoformat(), idempotency_key),
    )
    conn.commit()
    return {"id": cur.lastrowid, "order_id": order_id, "amount_cents": body.amount_cents,
            "reason": body.reason.strip(), "replayed": False}


@app.post("/orders/{order_id}/reply-draft")
def reply_draft(
    order_id: int,
    body: DraftRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    now: datetime = Depends(get_now),
):
    order, items, refunded = load_order(conn, order_id)
    el = order_eligibility(order, items, refunded, now)
    facts = {
        "order_id": order_id,
        "eligible": el.eligible,
        "max_refundable_cents": el.max_refundable_cents,
        "blockers": el.blockers,
    }
    return build_draft(FakeDraftProvider(), facts, body.message)
