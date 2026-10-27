"""Refund statistics. Money is integer cents."""

import sqlite3


def refund_stats(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS total FROM refunds").fetchone()
    return {"refund_count": row["n"], "refunded_cents": row["total"]}
