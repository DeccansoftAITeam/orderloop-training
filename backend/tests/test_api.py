def post_refund(client, order_id, amount, reason="Item did not fit", key="k-1"):
    return client.post(
        f"/orders/{order_id}/refunds",
        json={"amount_cents": amount, "reason": reason},
        headers={"Idempotency-Key": key},
    )


def test_order_queue_lists_all_orders(client):
    assert len(client.get("/orders").json()) == 8


def test_order_queue_search_by_customer_name(client):
    names = {o["customer_name"] for o in client.get("/orders", params={"q": "Asha"}).json()}
    assert names == {"Asha Verma"}


def test_order_detail_shows_eligibility(client):
    body = client.get("/orders/1001").json()
    assert body["eligibility"]["eligible"] is True
    assert body["eligibility"]["max_refundable_cents"] == 24000


def test_unknown_order_is_404(client):
    assert client.get("/orders/9999").status_code == 404


def test_refund_is_recorded(client):
    res = post_refund(client, 1001, 5000)
    assert res.status_code == 201
    assert client.get("/orders/1001").json()["eligibility"]["max_refundable_cents"] == 19000


def test_same_idempotency_key_never_refunds_twice(client):
    first = post_refund(client, 1001, 5000, key="same")
    second = post_refund(client, 1001, 5000, key="same")
    assert first.status_code == 201
    assert second.json()["replayed"] is True
    assert client.get("/orders/1001").json()["eligibility"]["max_refundable_cents"] == 19000


def test_missing_idempotency_key_is_rejected(client):
    res = client.post("/orders/1001/refunds", json={"amount_cents": 100, "reason": "Too big"})
    assert res.status_code == 400


def test_late_refund_is_not_supported_yet(client):
    res = post_refund(client, 1003, 1000)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "late_requires_lead"


def test_large_refund_is_not_supported_yet(client):
    res = post_refund(client, 1008, 30000)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "approval_required"


def test_reply_draft_masks_contact_details(client):
    res = client.post("/orders/1001/reply-draft", json={"message": "Mail me at a.b@example.test or +1 555 0199 123"})
    masked = res.json()["masked_message"]
    assert "example.test" not in masked and "555" not in masked


def test_refund_status_on_each_queue_row(client):
    rows = {o["id"]: o for o in client.get("/orders").json()}
    assert rows[1001]["refund_status"] == "none"
    assert rows[1007]["refund_status"] == "partial"
    assert rows[1007]["refunded_cents"] == 5000


def test_refund_status_becomes_full_after_the_last_refund(client):
    post_refund(client, 1002, 9500)
    rows = {o["id"]: o for o in client.get("/orders").json()}
    assert rows[1002]["refund_status"] == "full"


def test_refund_status_ignores_final_sale_items(client):
    # Order 1004: only the 12000 jacket is refundable; the final-sale socks never count.
    post_refund(client, 1004, 12000)
    rows = {o["id"]: o for o in client.get("/orders").json()}
    assert rows[1004]["refund_status"] == "full"


def test_refund_status_filter_returns_matching_orders_only(client):
    ids = [o["id"] for o in client.get("/orders", params={"refund_status": "partial"}).json()]
    assert ids == [1007]


def test_refund_status_filter_combines_with_search(client):
    res = client.get("/orders", params={"refund_status": "none", "q": "Asha"}).json()
    assert all(o["refund_status"] == "none" for o in res)


def test_refund_status_filter_rejects_unknown_value(client):
    assert client.get("/orders", params={"refund_status": "bogus"}).status_code == 422


def test_refund_status_queue_does_not_expose_contact_details_or_reason(client):
    post_refund(client, 1002, 9500, reason="Secret reason text")
    row = client.get("/orders").json()[0]
    assert not ({"email", "phone", "address", "reason", "customer_email"} & set(row))
    assert "Secret reason text" not in str(client.get("/orders").json())
