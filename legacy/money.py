"""Money helpers for the nightly settlement. All amounts are integer cents."""

from decimal import ROUND_HALF_UP, Decimal

FEE_DENOMINATOR = 10000


def fee_for_order(amount_cents, fee_bps):
    """Fee on one order in whole cents, rounded down. fee_bps = basis points (250 = 2.5%)."""
    return amount_cents * fee_bps // FEE_DENOMINATOR


def split_fee(fee_cents):
    """The partner's half of a fee. With an odd number of cents the partner gets the extra cent.

    Python 2's round() rounded halves away from zero; Python 3's round() rounds halves to even.
    """
    return int((Decimal(fee_cents) / 2).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def whole_units(cents):
    """Whole currency units, rounded down (toward minus infinity), also for negative amounts."""
    return cents // 100


def fmt_money(cents):
    """Format cents as 1,234.56 (a leading minus for negative amounts)."""
    sign = "-" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    return f"{sign}{units:,}.{rest:02d}"
