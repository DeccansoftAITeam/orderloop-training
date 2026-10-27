"""Daily refund digest for the support lead.

This module is the change under review in Lab 14. It is not wired into the API yet.

Inputs are plain dicts:
  refunds:   {"id": str, "customer_id": str, "amount_cents": int, "reason": str}
  customers: {"id": str, "name": str, "email": str}

Money is integer cents. Nothing that identifies a customer is logged or used as a key.
"""

import logging

from app.rules import LEAD_APPROVAL_THRESHOLD_CENTS

log = logging.getLogger("refund_digest")

UNKNOWN_CUSTOMER = "unknown"


def build_digest(refunds, customers):
    known = {c["id"] for c in customers}  # one pass, then O(1) lookups

    total = 0
    by_customer: dict[str, int] = {}
    large = []
    for r in refunds:
        amount = r["amount_cents"]
        total += amount
        key = r["customer_id"] if r["customer_id"] in known else UNKNOWN_CUSTOMER
        by_customer[key] = by_customer.get(key, 0) + amount
        if amount > LEAD_APPROVAL_THRESHOLD_CENTS:
            large.append(r["id"])
        log.debug("refund %s counted for %s: %s cents", r["id"], key, amount)

    count = len(refunds)
    return {
        "count": count,
        "total_cents": total,
        "average_cents": total // count if count else 0,
        "by_customer": by_customer,
        "large": large,
    }
