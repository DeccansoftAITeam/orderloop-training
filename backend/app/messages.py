"""Synthetic inbound customer messages, one per seeded order.

They give the reply panel something realistic to answer. Some contain an email address or a phone
number on purpose, so the masking step before drafting has something to mask. None contains a
customer name, because names must stay out of model prompts. All contact details are made up.
"""

CUSTOMER_MESSAGES: dict[int, str] = {
    1001: "The zipper on the tent broke on the very first night. I would like my money back. "
          "You can reach me at asha.verma@example.test.",
    1002: "I ordered the trail boots two sizes up by mistake and they are far too big. Can I send them back?",
    1003: "The shoulder strap on my 30L daypack tore after one trip. Sorry for the late message, I was travelling. "
          "Can I still return it? Call me on +1 555 0103 2222.",
    1004: "The rain jacket is too small and the clearance socks have holes. Can I return both? "
          "Please phone me on +1 555 0104 4444.",
    1005: "I bought the gift card by mistake and it is the wrong amount. Can I get a refund?",
    1006: "Where is my order? The tracking has not moved for a week and I need the head lamps for a trip.",
    1007: "You refunded part of this order already, but I would like to return the whole sleeping bag. "
          "Email me at asha.verma@example.test if you need anything.",
    1008: "The four-person tent leaks at the seams in light rain. I want a full refund, please.",
}
