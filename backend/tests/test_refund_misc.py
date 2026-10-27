from datetime import datetime, timedelta

from app import rules
from app.rules import Item

NOW = datetime(2030, 3, 1, 10, 0, 0)


def test_order_delivered_five_days_ago_is_fully_refundable():
    items = [Item("TENT", "Tent", 18000, 1)]
    el = rules.eligibility(NOW - timedelta(days=5), items, 0, NOW)
    assert el.eligible and el.max_refundable_cents == 18000


def test_order_delivered_forty_five_days_ago_is_late():
    items = [Item("TENT", "Tent", 18000, 1)]
    el = rules.eligibility(NOW - timedelta(days=45), items, 0, NOW)
    assert el.late
