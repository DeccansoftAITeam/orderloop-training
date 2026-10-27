import json
from types import SimpleNamespace

import pytest

from app.assistant import ClaudeDraftProvider, TemplateDraftProvider, invalid_amounts
from app.main import app, get_draft_provider

SECRET_REASON = "zebra-stripes-reason"


class FakeClient:
    """Stands in for anthropic.Anthropic. Records every request, replies from a script."""

    def __init__(self, *texts, stop_reason="end_turn"):
        self.texts = list(texts)
        self.stop_reason = stop_reason
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


def use(fake, model=None):
    app.dependency_overrides[get_draft_provider] = lambda: ClaudeDraftProvider(client=fake, model=model)


def draft(client, order=1001, message="Hello, this is Asha Verma, mail asha@example.test or +1 555 0199 123"):
    return client.post(f"/orders/{order}/reply-draft", json={"message": message})


def test_prompt_has_no_personal_data_or_reason(client):
    client.post("/orders/1001/refunds", json={"amount_cents": 1000, "reason": SECRET_REASON},
                headers={"Idempotency-Key": "r1"})
    fake = FakeClient("Hi {first_name}, we can refund up to $240.00 ... Kind regards")
    use(fake)
    draft(client)
    sent = json.dumps(fake.calls[0]).lower()
    for secret in ("asha", "verma", "example.test", "555", SECRET_REASON):
        assert secret not in sent
    assert "{first_name}" in sent and "[email]" in sent and "[phone]" in sent
    assert fake.calls[0]["max_tokens"] <= 1000


def test_first_name_is_substituted_locally(client):
    use(FakeClient("Hi {first_name},\n\nWe can refund up to $240.00.\n\nKind regards"))
    res = draft(client).json()
    assert res["draft"].startswith("Hi Asha,")
    assert "{first_name}" not in res["draft"]
    assert res["provider"] == "claude" and res["model"] == "claude-haiku-5-5"


def test_invented_amount_is_regenerated_then_accepted(client):
    fake = FakeClient("Hi {first_name}, refund $999.00.", "Hi {first_name}, refund up to $240.00.")
    use(fake)
    res = draft(client).json()
    assert len(fake.calls) == 2
    assert "$240.00" in res["draft"] and res["provider"] == "claude"


def test_invented_amount_twice_falls_back_with_flag(client):
    use(FakeClient("Hi {first_name}, refund $999.00."))
    res = draft(client).json()
    assert res["provider"] == "template" and res["fallback"] == "claude_draft_rejected"
    assert "$999" not in res["draft"]


def test_amount_check_accepts_provided_amounts_only():
    facts = {"max_refundable_cents": 24000, "restocking_fee_cents": 500,
             "items": [{"name": "Gift card $50", "refundable": False, "total_cents": 5000}]}
    assert invalid_amounts("up to $240.00, fee $5, card $50", facts) == []
    assert invalid_amounts("refund $1,000.00", facts) == ["1,000.00"]


def test_missing_key_is_503_not_a_crash_or_fallback(client, monkeypatch):
    monkeypatch.setenv("ORDERLOOP_DRAFT_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = draft(client)
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "draft_provider_unavailable"


def test_provider_failure_is_502_without_details(client):
    class Boom:
        messages = None

        def __init__(self):
            self.messages = self

        def create(self, **kw):
            raise RuntimeError("secret request details")

    use(Boom())
    res = draft(client)
    assert res.status_code == 502 and "secret" not in res.text


def test_status_endpoint(client, monkeypatch):
    monkeypatch.delenv("ORDERLOOP_DRAFT_PROVIDER", raising=False)
    assert client.get("/assistant/status").json() == {"provider": "template", "model": None, "configured": True}
    monkeypatch.setenv("ORDERLOOP_DRAFT_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ORDERLOOP_DRAFT_MODEL", "claude-test-model")
    body = client.get("/assistant/status").json()
    assert body == {"provider": "claude", "model": "claude-test-model", "configured": False}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    assert client.get("/assistant/status").json()["configured"] is True
    assert "not-a-real-key" not in client.get("/assistant/status").text


def test_default_is_template_with_fields(client, monkeypatch):
    monkeypatch.delenv("ORDERLOOP_DRAFT_PROVIDER", raising=False)
    res = draft(client).json()
    assert res["provider"] == "template" and res["model"] is None
    assert set(res) >= {"draft", "masked_message", "provider", "model"}
    assert res["draft"].startswith("Hi Asha,")
    assert "Asha" not in res["masked_message"] and "example.test" not in res["masked_message"]


@pytest.mark.parametrize("order,expected", [
    (1001, "Two-person tent"),                 # approved, mentions item and amount
    (1004, "cannot be refunded because"),      # partly refundable: final-sale item excluded
    (1003, "outside our 30-day refund window"),
    (1005, "final sale or gift cards"),
    (1006, "has not been delivered"),
])
def test_template_varies_by_situation(client, monkeypatch, order, expected):
    monkeypatch.delenv("ORDERLOOP_DRAFT_PROVIDER", raising=False)
    text = draft(client, order).json()["draft"]
    assert expected in text and str(order) in text


def test_template_amounts_and_fee_and_determinism():
    facts = {"order_id": 1, "eligible": True, "late": False, "days_since_delivery": 3,
             "max_refundable_cents": 24000, "blockers": [], "restocking_fee_cents": 1500,
             "items": [{"name": "Tent", "refundable": True, "total_cents": 24000}]}
    t = TemplateDraftProvider()
    out = t.draft(facts, "x")
    assert "$240.00" in out and "$15.00" in out and "Tent" in out
    assert out == t.draft(facts, "x")
    assert invalid_amounts(out, facts) == []


def test_workspace_id_is_sent_as_a_header_when_set(monkeypatch):
    seen = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    import sys, types
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-placeholder")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    from app.assistant import ClaudeDraftProvider
    ClaudeDraftProvider()._get_client()
    assert seen["default_headers"] == {"anthropic-workspace-id": "wrkspc_test"}


def test_no_workspace_header_when_not_set(monkeypatch):
    seen = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    import sys, types
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-placeholder")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    from app.assistant import ClaudeDraftProvider
    ClaudeDraftProvider()._get_client()
    assert seen["default_headers"] is None
