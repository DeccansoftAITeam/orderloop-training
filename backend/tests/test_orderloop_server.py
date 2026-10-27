"""Tests for mcp/orderloop_server.py, using the SDK's in-memory client (no subprocess)."""

from datetime import datetime

import anyio
import pytest
from mcp import Client

import orderloop_server
from app.db import connect
from app.seed import seed

NOW = datetime(2030, 3, 1, 10, 0, 0)


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ORDERLOOP_DB", str(db_file))
    conn = connect(str(db_file))
    seed(conn, NOW)
    conn.close()
    monkeypatch.setattr(orderloop_server, "now", lambda: NOW)


def call(tool: str, arguments: dict | None = None):
    """Call a tool through a real MCP client connected in memory. Returns the CallToolResult."""

    async def run():
        async with Client(orderloop_server.server) as client:
            return await client.call_tool(tool, arguments or {})

    return anyio.run(run)


def test_lists_exactly_the_three_tools():
    async def run():
        async with Client(orderloop_server.server) as client:
            return await client.list_tools()

    names = {t.name for t in anyio.run(run).tools}
    assert names == {"lookup_order", "check_refund_eligibility", "list_orders_needing_attention"}


def test_lookup_order_returns_items_and_masked_contact():
    result = call("lookup_order", {"order_id": 1001})
    assert not result.is_error
    data = result.structured_content
    assert data["order_id"] == 1001
    assert {i["sku"] for i in data["items"]} == {"TENT-2P", "STOVE-1"}
    assert data["customer"]["email"] == "a***@example.test"
    assert data["customer"]["phone"] == "***0101"


def test_lookup_order_never_leaks_contact_details_or_address():
    text = str(call("lookup_order", {"order_id": 1001}))
    for secret in ("asha.verma", "555-0101", "Larch Street"):
        assert secret not in text


def test_unknown_order_is_an_error_result_not_a_crash():
    result = call("lookup_order", {"order_id": 999999})
    assert result.is_error
    assert "does not exist" in result.content[0].text


def test_missing_database_is_a_clear_error_and_creates_nothing(tmp_path, monkeypatch):
    missing = tmp_path / "nope.db"
    monkeypatch.setenv("ORDERLOOP_DB", str(missing))
    result = call("lookup_order", {"order_id": 1001})
    assert result.is_error
    assert "Seed it" in result.content[0].text
    assert not missing.exists()


def test_invalid_order_id_is_rejected():
    assert call("lookup_order", {"order_id": -5}).is_error


def test_eligibility_on_time_order():
    data = call("check_refund_eligibility", {"order_id": 1002}).structured_content
    assert data["eligible"] is True
    assert data["late"] is False
    assert data["days_since_delivery"] == 30  # exactly 30 days is still on time
    assert data["max_refundable_cents"] == 9500


def test_eligibility_late_order():
    data = call("check_refund_eligibility", {"order_id": 1003}).structured_content
    assert data["late"] is True


def test_eligibility_gift_card_is_blocked():
    data = call("check_refund_eligibility", {"order_id": 1005}).structured_content
    assert data["eligible"] is False
    assert "no_refundable_items" in data["blockers"]


def test_eligibility_counts_earlier_refunds():
    data = call("check_refund_eligibility", {"order_id": 1007}).structured_content
    assert data["max_refundable_cents"] == 10000  # 15000 minus 5000 already refunded


def test_orders_needing_attention():
    data = call("list_orders_needing_attention").structured_content
    flags = {o["order_id"]: o["flags"] for o in data["orders"]}
    assert flags == {
        1001: ["above_lead_threshold"],
        1003: ["late"],
        1007: ["partially_refunded"],
        1008: ["above_lead_threshold"],
    }
    assert data["count"] == 4


def test_tools_cannot_write():
    with orderloop_server.open_db() as conn:
        with pytest.raises(Exception):
            conn.execute("DELETE FROM orders")


def test_refund_policy_resource():
    async def run():
        async with Client(orderloop_server.server) as client:
            return await client.read_resource("orderloop://refund-policy")

    text = anyio.run(run).contents[0].text
    assert "30 days" in text
