from app.refund_digest import build_digest

CUSTOMERS = [{"id": "C1", "name": "Asha Verma", "email": "asha.verma@example.test"}]


def test_total_of_two_refunds():
    refunds = [
        {"id": "R1", "customer_id": "C1", "amount_cents": 1000, "reason": "damaged"},
        {"id": "R2", "customer_id": "C1", "amount_cents": 500, "reason": "late"},
    ]
    assert build_digest(refunds, CUSTOMERS)["total_cents"] == 1500
