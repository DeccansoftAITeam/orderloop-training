"""Capstone tests for GET /orders/{id}/refund-summary. Ids match docs/specs/refund-summary.md."""

from app import rules

FIELDS = {"order_id", "refund_count", "refunded_cents", "remaining_cents", "last_refund_at"}


def test_ac1_summary_has_the_five_fields(client):
    body = client.get("/orders/1001/refund-summary").json()
    assert set(body) == FIELDS
    assert body["order_id"] == 1001


def test_ac2_order_without_refunds_is_all_zero(client):
    body = client.get("/orders/1001/refund-summary").json()
    assert body["refund_count"] == 0
    assert body["refunded_cents"] == 0
    assert body["last_refund_at"] is None
    assert body["remaining_cents"] == 24000  # tent 18000 + opened stove 6000, nothing refunded


def test_ac3_remaining_is_refundable_minus_refunded(client):
    body = client.get("/orders/1007/refund-summary").json()  # 15000 item, 5000 already refunded
    assert body["refund_count"] == 1
    assert body["refunded_cents"] == 5000
    assert body["remaining_cents"] == 10000
    assert body["last_refund_at"] is not None


def test_ac3_remaining_never_below_zero():
    assert rules.refund_summary(refundable_cents=1000, amounts=[800, 800])["remaining_cents"] == 0


def test_ac3_final_sale_items_never_count(client):
    body = client.get("/orders/1004/refund-summary").json()  # jacket 12000 + final-sale socks
    assert body["remaining_cents"] == 12000


def test_ac3_new_refund_shows_up(client):
    client.post("/orders/1001/refunds", json={"amount_cents": 4000, "reason": "Too small"},
                headers={"Idempotency-Key": "cap-1"})
    body = client.get("/orders/1001/refund-summary").json()
    assert (body["refund_count"], body["refunded_cents"], body["remaining_cents"]) == (1, 4000, 20000)


def test_ac4_unknown_order_is_404(client):
    res = client.get("/orders/99999/refund-summary")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "order_not_found"


def test_ac5_reason_text_is_not_returned(client):
    res = client.get("/orders/1007/refund-summary")
    assert "Wrong colour" not in res.text
    assert "reason" not in res.json()
