import logging

from app.refund_digest import build_digest
from app.rules import LEAD_APPROVAL_THRESHOLD_CENTS

CUSTOMERS = [
    {"id": "C1", "name": "Asha Verma", "email": "asha.verma@example.test"},
    {"id": "C2", "name": "Ben Ortiz", "email": "ben.ortiz@example.test"},
]


def refund(rid: str, customer: str, cents: int) -> dict:
    return {"id": rid, "customer_id": customer, "amount_cents": cents, "reason": "damaged"}


def test_total_of_two_refunds():
    refunds = [refund("R1", "C1", 1000), refund("R2", "C1", 500)]
    assert build_digest(refunds, CUSTOMERS)["total_cents"] == 1500


def test_empty_day_does_not_crash():
    digest = build_digest([], CUSTOMERS)
    assert digest["count"] == 0 and digest["total_cents"] == 0
    assert digest["average_cents"] == 0 and digest["by_customer"] == {} and digest["large"] == []


def test_average_is_whole_cents():
    digest = build_digest([refund("R1", "C1", 1001), refund("R2", "C2", 1002)], CUSTOMERS)
    assert digest["average_cents"] == 1001
    assert isinstance(digest["average_cents"], int)


def test_totals_are_keyed_by_customer_id():
    digest = build_digest([refund("R1", "C1", 700), refund("R2", "C2", 100), refund("R3", "C1", 50)], CUSTOMERS)
    assert digest["by_customer"] == {"C1": 750, "C2": 100}


def test_unknown_customer_is_kept_under_unknown():
    digest = build_digest([refund("R1", "C1", 700), refund("R2", "C9", 500)], CUSTOMERS)
    assert digest["by_customer"] == {"C1": 700, "unknown": 500}
    assert sum(digest["by_customer"].values()) == digest["total_cents"]


def test_exactly_the_threshold_is_not_large():
    at = LEAD_APPROVAL_THRESHOLD_CENTS
    digest = build_digest([refund("eq", "C1", at), refund("over", "C1", at + 1)], CUSTOMERS)
    assert digest["large"] == ["over"]


def test_log_has_no_personal_data(caplog):
    with caplog.at_level(logging.DEBUG):
        build_digest([refund("R1", "C1", 700)], CUSTOMERS)
    text = caplog.text
    assert "Asha" not in text and "example.test" not in text
