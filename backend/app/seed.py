"""Load synthetic training data. All names, emails and phone numbers are made up.

Run from the backend folder:  uv run python -m app.seed
"""

import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.db import connect, init_db

CUSTOMERS_CSV = Path(__file__).resolve().parents[2] / "seed" / "customers.csv"

# (order id, customer id, days since delivery or None, items, refunded cents already)
# item = (sku, name, unit price cents, qty, opened, final_sale, gift_card)
ORDERS = [
    (1001, 1, 5, [("TENT-2P", "Two-person tent", 18000, 1, 0, 0, 0), ("STOVE-1", "Camp stove", 6000, 1, 1, 0, 0)], 0),
    (1002, 2, 30, [("BOOT-42", "Trail boots", 9500, 1, 0, 0, 0)], 0),  # exactly 30 days: still on time
    (1003, 3, 31, [("PACK-30", "30L daypack", 7000, 1, 0, 0, 0)], 0),  # 31 days: late
    (1004, 4, 8, [("JKT-M", "Rain jacket", 12000, 1, 0, 0, 0), ("SOCK-3", "Clearance socks", 1500, 3, 0, 1, 0)], 0),
    (1005, 5, 2, [("GIFT-50", "Gift card $50", 5000, 1, 0, 0, 1)], 0),
    (1006, 6, None, [("LAMP-1", "Head lamp", 4500, 2, 0, 0, 0)], 0),  # not delivered yet
    (1007, 1, 12, [("BAG-20", "Sleeping bag", 15000, 1, 0, 0, 0)], 5000),  # already part-refunded
    (1008, 2, 3, [("TENT-4P", "Four-person tent", 45000, 1, 0, 0, 0)], 0),  # above the lead-approval threshold
]


def seed(conn: sqlite3.Connection, now: datetime, customers_csv: Path = CUSTOMERS_CSV) -> None:
    init_db(conn)
    with open(customers_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            conn.execute(
                "INSERT INTO customers (id, name, email, phone, address) VALUES (?, ?, ?, ?, ?)",
                (row["id"], row["name"], row["email"], row["phone"], row["address"]),
            )
    for order_id, customer_id, days, items, refunded in ORDERS:
        delivered = None if days is None else (now - timedelta(days=days)).isoformat()
        placed = (now - timedelta(days=(days or 0) + 4)).isoformat()
        status = "shipped" if days is None else "delivered"
        conn.execute(
            "INSERT INTO orders (id, customer_id, placed_at, delivered_at, status) VALUES (?, ?, ?, ?, ?)",
            (order_id, customer_id, placed, delivered, status),
        )
        for sku, name, price, qty, opened, final_sale, gift in items:
            conn.execute(
                "INSERT INTO order_items (order_id, sku, name, unit_price_cents, qty, opened, final_sale, gift_card) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, sku, name, price, qty, opened, final_sale, gift),
            )
        if refunded:
            conn.execute(
                "INSERT INTO refunds (order_id, amount_cents, reason, created_at, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, refunded, "Wrong colour", now.isoformat(), f"seed-{order_id}"),
            )
    conn.commit()


if __name__ == "__main__":
    connection = connect()
    seed(connection, datetime.now().replace(microsecond=0))
    print("Seeded", connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0], "orders")
