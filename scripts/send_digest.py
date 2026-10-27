"""Legacy nightly digest mailer (unused sample script for Lab 18).

All values below are FAKE. They exist so that a secret scan has something to find.
"""

import smtplib

SMTP_HOST = "smtp.example.test"
SMTP_USER = "digest-bot"
SMTP_PASSWORD = "fake-Passw0rd-not-real-4471"
DIGEST_API_KEY = "sk-FAKE-live-9f8e7d6c5b4a39281706"


def send(subject: str, body: str) -> None:
    with smtplib.SMTP(SMTP_HOST, 587) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail("digest@example.test", ["lead@example.test"], f"Subject: {subject}\n\n{body}")
