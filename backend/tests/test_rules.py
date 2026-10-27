from datetime import datetime, timedelta

from app import rules
from app.rules import Item

NOW = datetime(2030, 3, 1, 10, 0, 0)


def delivered(days: int) -> datetime:
    return NOW - timedelta(days=days)


def tent() -> Item:
    return Item("TENT", "Tent", 18000, 1)


def test_exactly_thirty_days_is_still_on_time():
    el = rules.eligibility(delivered(30), [tent()], 0, NOW)
    assert el.eligible and not el.late


def test_thirty_one_days_is_late():
    el = rules.eligibility(delivered(31), [tent()], 0, NOW)
    assert el.late


def test_final_sale_and_gift_cards_never_qualify():
    items = [Item("A", "Socks", 1000, 2, final_sale=True), Item("G", "Gift card", 5000, 1, gift_card=True)]
    el = rules.eligibility(delivered(1), items, 0, NOW)
    assert not el.eligible
    assert "no_refundable_items" in el.blockers


def test_earlier_refunds_reduce_the_maximum():
    el = rules.eligibility(delivered(1), [tent()], 5000, NOW)
    assert el.max_refundable_cents == 13000


def test_cannot_refund_more_than_what_remains():
    el = rules.eligibility(delivered(1), [tent()], 0, NOW)
    assert rules.decide(el, 18001, "Too small").code == "exceeds_max"


def test_reason_must_be_three_to_two_hundred_characters():
    el = rules.eligibility(delivered(1), [tent()], 0, NOW)
    assert rules.decide(el, 1000, "ab").code == "reason_invalid"
    assert rules.decide(el, 1000, "x" * 201).code == "reason_invalid"
    assert rules.decide(el, 1000, "abc").ok


def test_undelivered_order_is_not_eligible():
    el = rules.eligibility(None, [tent()], 0, NOW)
    assert "not_delivered" in el.blockers


def stove(opened: bool) -> Item:
    return Item("STOVE-1", "Camp stove", 6000, 1, opened=opened)


def test_opened_item_loses_ten_percent_restocking_fee():
    el = rules.eligibility(delivered(20), [stove(opened=True)], 0, NOW)
    assert el.restocking_fee_cents == 600
    assert el.max_refundable_cents == 5400


def test_unopened_item_has_no_restocking_fee():
    el = rules.eligibility(delivered(20), [stove(opened=False)], 0, NOW)
    assert el.restocking_fee_cents == 0
    assert el.max_refundable_cents == 6000


def test_restocking_fee_rounds_down_to_whole_cents():
    odd = Item("X", "Cable", 999, 1, opened=True)
    assert odd.restocking_fee_cents == 99


def test_restocking_fee_applies_per_opened_line_only():
    el = rules.eligibility(delivered(5), [tent(), stove(opened=True)], 0, NOW)
    assert el.max_refundable_cents == 18000 + 5400


def test_final_sale_opened_item_is_still_never_refundable():
    item = Item("S", "Socks", 1000, 1, opened=True, final_sale=True)
    el = rules.eligibility(delivered(1), [item], 0, NOW)
    assert el.restocking_fee_cents == 0 and not el.eligible
