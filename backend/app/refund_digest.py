"""Daily refund digest for the support lead.

This module is the change under review in Lab 14. It is not wired into the API yet.

Inputs are plain dicts:
  refunds:   {"id": str, "customer_id": str, "amount_cents": int, "reason": str}
  customers: {"id": str, "name": str, "email": str}
"""

import logging

log = logging.getLogger("refund_digest")

LARGE_REFUND_CENTS = 20000


def build_digest(refunds, customers):
    total = 0
    for r in refunds:
        total += r["amount_cents"]
    average_cents = total / len(refunds)

    by_customer = {}
    for r in refunds:
        for c in customers:
            if c["id"] == r["customer_id"]:
                log.info("refund %s for %s <%s>: %s cents", r["id"], c["name"], c["email"], r["amount_cents"])
                by_customer[c["email"]] = by_customer.get(c["email"], 0) + r["amount_cents"]

    large = [r["id"] for r in refunds if r["amount_cents"] >= LARGE_REFUND_CENTS]

    return {
        "count": len(refunds),
        "total_cents": total,
        "average_cents": average_cents,
        "by_customer": by_customer,
        "large": large,
    }
