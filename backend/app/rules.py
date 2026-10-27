"""Refund rules. Pure functions: no database, no clock (the caller passes `now`).

Money is always an integer number of cents.
"""

from dataclasses import dataclass, field
from datetime import datetime

REFUND_WINDOW_DAYS = 30
LEAD_APPROVAL_THRESHOLD_CENTS = 20_000
MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 200


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    unit_price_cents: int
    qty: int
    opened: bool = False
    final_sale: bool = False
    gift_card: bool = False

    @property
    def total_cents(self) -> int:
        return self.unit_price_cents * self.qty

    @property
    def refundable(self) -> bool:
        return not (self.final_sale or self.gift_card)


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    days_since_delivery: int | None
    late: bool
    max_refundable_cents: int
    qualifying_skus: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    ok: bool
    code: str | None = None
    message: str | None = None


def days_since_delivery(delivered_at: datetime | None, now: datetime) -> int | None:
    if delivered_at is None:
        return None
    return (now.date() - delivered_at.date()).days


def eligibility(
    delivered_at: datetime | None,
    items: list[Item],
    already_refunded_cents: int,
    now: datetime,
) -> Eligibility:
    days = days_since_delivery(delivered_at, now)
    qualifying = [i for i in items if i.refundable]
    max_cents = max(sum(i.total_cents for i in qualifying) - already_refunded_cents, 0)
    late = days is not None and days > REFUND_WINDOW_DAYS  # exactly 30 days is still on time

    blockers: list[str] = []
    if days is None:
        blockers.append("not_delivered")
    if not qualifying:
        blockers.append("no_refundable_items")
    elif max_cents == 0:
        blockers.append("nothing_left_to_refund")

    return Eligibility(
        eligible=not blockers,
        days_since_delivery=days,
        late=late,
        max_refundable_cents=max_cents,
        qualifying_skus=[i.sku for i in qualifying],
        blockers=blockers,
    )


def refund_status(refundable_cents: int, refunded_cents: int) -> str:
    """Return "none", "partial" or "full" for the order queue. Money is integer cents."""
    if refunded_cents <= 0:
        return "none"
    if refunded_cents >= refundable_cents:
        return "full"
    return "partial"


def decide(el: Eligibility, amount_cents: int, reason: str) -> Decision:
    reason = reason.strip()
    if not MIN_REASON_LENGTH <= len(reason) <= MAX_REASON_LENGTH:
        return Decision(False, "reason_invalid", "Reason must be 3 to 200 characters.")
    if amount_cents <= 0:
        return Decision(False, "amount_invalid", "Amount must be greater than zero.")
    if not el.eligible:
        return Decision(False, "not_eligible", "Order is not eligible: " + ", ".join(el.blockers))
    if amount_cents > el.max_refundable_cents:
        return Decision(False, "exceeds_max", "Amount is more than the refundable maximum.")
    if el.late:
        return Decision(False, "late_requires_lead", "Late refunds need lead approval (not supported yet).")
    if amount_cents > LEAD_APPROVAL_THRESHOLD_CENTS:
        return Decision(False, "approval_required", "Large refunds need lead approval (not supported yet).")
    return Decision(True)
