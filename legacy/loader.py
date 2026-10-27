"""CSV loading for the nightly settlement. Input files are UTF-8."""

import csv
import sys


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield reader.line_num, row


def load_merchants(path):
    """Return {merchant id: merchant dict}. A blank tier means 'not rated yet' and becomes None."""
    merchants = {}
    for _, row in _rows(path):
        tier = row["tier"]
        merchants[row["id"]] = {
            "id": row["id"],
            "name": row["name"],
            "tier": None if tier == "" else int(tier),
            "fee_bps": int(row["fee_bps"]),
        }
    return merchants


def load_orders(path):
    """Return (orders, bad_lines). A row with a bad amount is skipped and its line number is kept."""
    orders = []
    bad = []
    for line_num, row in _rows(path):
        try:
            orders.append({
                "id": row["order_id"],
                "merchant_id": row["merchant_id"],
                "date": row["date"],
                "amount": int(row["amount_cents"]),
                "status": row["status"].upper(),
            })
        except ValueError as e:
            bad.append(line_num)
            print(f"skipped orders line {line_num}: {e}", file=sys.stderr)
    return orders, bad


def load_refunds(path):
    """Return (refunds, bad_lines), like load_orders."""
    refunds = []
    bad = []
    for line_num, row in _rows(path):
        try:
            refunds.append({
                "id": row["refund_id"],
                "order_id": row["order_id"],
                "amount": int(row["amount_cents"]),
                "date": row["date"],
            })
        except ValueError as e:
            bad.append(line_num)
            print(f"skipped refunds line {line_num}: {e}", file=sys.stderr)
    return refunds, bad
