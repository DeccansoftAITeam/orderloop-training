from tests.test_api import post_refund


def test_stats_on_seeded_data_counts_the_existing_refund(client):
    body = client.get("/stats/refunds").json()
    assert body == {"refund_count": 1, "refunded_cents": 5000}


def test_stats_include_refunds_posted_through_the_api(client):
    post_refund(client, 1001, 2500, key="s-1")
    post_refund(client, 1001, 1000, key="s-2")
    body = client.get("/stats/refunds").json()
    assert body == {"refund_count": 3, "refunded_cents": 8500}
