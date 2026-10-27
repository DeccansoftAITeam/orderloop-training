"""Nightly settlement for Kestrel Outfitters' marketplace merchants.

Usage:  python settle.py YYYY-MM-DD DATA_DIR

Reads merchants.csv, orders.csv and refunds.csv from DATA_DIR and prints the settlement
report on standard output (UTF-8, one report per run date). Warnings go to standard error.
Only rows dated on or before the run date count.
"""

import os
import sys
from dataclasses import dataclass

import loader
import money


@dataclass
class Line:
    """One merchant's settlement line."""

    merchant: dict
    orders: int = 0
    gross: int = 0
    refunds: int = 0
    fee: int = 0
    partner: int = 0

    def net(self):
        return self.gross - self.refunds - self.fee

    def sort_key(self):
        # Report order: unrated merchants (tier None) first, then by tier,
        # then higher net first, then by merchant id. (Python 2 sorted None before numbers.)
        tier = self.merchant["tier"]
        return (tier is not None, tier or 0, -self.net(), self.merchant["id"])


def settle(run_date, data_dir):
    merchants = loader.load_merchants(os.path.join(data_dir, "merchants.csv"))
    orders, bad_orders = loader.load_orders(os.path.join(data_dir, "orders.csv"))
    refunds, bad_refunds = loader.load_refunds(os.path.join(data_dir, "refunds.csv"))

    lines = {mid: Line(merchant) for mid, merchant in merchants.items()}

    paid = {}
    future = 0
    cancelled = 0
    unknown_merchant = 0
    smallest = sys.maxsize
    for o in orders:
        if o["date"] > run_date:
            future += 1
            continue
        if o["status"] == "CANCELLED":
            cancelled += 1
            continue
        if o["merchant_id"] not in merchants:
            unknown_merchant += 1
            continue
        line = lines[o["merchant_id"]]
        line.orders += 1
        line.gross += o["amount"]
        line.fee += money.fee_for_order(o["amount"], line.merchant["fee_bps"])
        paid[o["id"]] = o
        if o["amount"] < smallest:
            smallest = o["amount"]

    orphans = []
    for r in refunds:
        if r["date"] > run_date:
            continue
        if r["order_id"] not in paid:
            orphans.append(r)
            continue
        lines[paid[r["order_id"]]["merchant_id"]].refunds += r["amount"]

    for line in lines.values():
        line.partner = money.split_fee(line.fee)

    ordered = sorted(lines.values(), key=Line.sort_key)

    print("Nightly settlement for " + run_date)
    print("=" * 78)
    print("%-16s %4s %6s %12s %10s %9s %12s %6s" % (
        "Merchant", "Tier", "Orders", "Gross", "Refunds", "Fee", "Net", "Units"))
    for line in ordered:
        tier = line.merchant["tier"]
        tier_text = "-" if tier is None else str(tier)
        print("%-16s %4s %6d %12s %10s %9s %12s %6d" % (
            line.merchant["name"][:16], tier_text, line.orders,
            money.fmt_money(line.gross), money.fmt_money(line.refunds),
            money.fmt_money(line.fee), money.fmt_money(line.net()),
            money.whole_units(line.net())))
    print("-" * 78)

    total_orders = sum(line.orders for line in ordered)
    total_gross = sum(line.gross for line in ordered)
    total_refunds = sum(line.refunds for line in ordered)
    total_fee = sum(line.fee for line in ordered)
    total_partner = sum(line.partner for line in ordered)
    total_net = total_gross - total_refunds - total_fee

    print("Totals: orders=%d gross=%s refunds=%s fee=%s net=%s" % (
        total_orders, money.fmt_money(total_gross), money.fmt_money(total_refunds),
        money.fmt_money(total_fee), money.fmt_money(total_net)))
    print("Partner share of fees: " + money.fmt_money(total_partner))
    ratio = total_refunds * 1000 // total_gross
    print("Refund ratio: %d.%d%%" % (ratio // 10, ratio % 10))
    print("Average order (cents):", total_gross // total_orders)
    print("Smallest order: " + money.fmt_money(smallest))
    print("First line:", ordered[0].merchant["id"])
    print("Merchants we pay: %d" % len([line for line in ordered if line.net() > 0]))
    print("Merchants who owe us: %d" % len([line for line in ordered if line.net() < 0]))
    print("Ignored: future=%d cancelled=%d unknown_merchant=%d" % (future, cancelled, unknown_merchant))
    print("Rows skipped: orders=%d refunds=%d" % (len(bad_orders), len(bad_refunds)))
    if orphans:
        print("Orphan refunds: " + " ".join(sorted(r["id"] for r in orphans)))
    else:
        print("Orphan refunds: none")


def main(argv):
    if len(argv) != 3:
        print("usage: settle.py YYYY-MM-DD DATA_DIR", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    try:
        if len(argv[1]) != 10:
            raise ValueError("run date must look like 2030-03-01")
        settle(argv[1], argv[2])
    except ValueError as e:
        print(f"settle: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
