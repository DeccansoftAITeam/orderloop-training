"""Reply drafting assistant.

The assistant only writes wording. It never decides eligibility or amounts: those arrive as
facts from the rules module. Customer text is masked before it reaches any provider.
"""

import re
from typing import Protocol

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def mask_pii(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    return PHONE.sub("[phone]", text)


class DraftProvider(Protocol):
    def draft(self, facts: dict, customer_message: str) -> str: ...


class FakeDraftProvider:
    """Offline provider used by labs and tests. Deterministic, no network."""

    def draft(self, facts: dict, customer_message: str) -> str:
        if facts["eligible"]:
            dollars = facts["max_refundable_cents"] / 100
            body = (
                f"We can refund up to ${dollars:,.2f} for order {facts['order_id']}. "
                "Please tell us how much you would like refunded."
            )
        else:
            body = (
                f"We are sorry, order {facts['order_id']} cannot be refunded right now "
                f"({', '.join(facts['blockers'])})."
            )
        return f"Hello,\n\nThank you for contacting us. {body}\n\nKind regards,\nKestrel Outfitters Support"


def build_draft(provider: DraftProvider, facts: dict, customer_message: str) -> dict:
    masked = mask_pii(customer_message)
    return {"draft": provider.draft(facts, masked), "masked_message": masked}
