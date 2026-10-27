"""Legacy nightly digest mailer (unused sample script for Lab 18).

Credentials come from the environment. Nothing secret is stored in this file.
"""

import os
import smtplib

SMTP_HOST = os.environ.get("DIGEST_SMTP_HOST", "smtp.example.test")
SMTP_USER = os.environ["DIGEST_SMTP_USER"]
SMTP_PASSWORD = os.environ["DIGEST_SMTP_PASSWORD"]


def send(subject: str, body: str) -> None:
    with smtplib.SMTP(SMTP_HOST, 587) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail("digest@example.test", ["lead@example.test"], f"Subject: {subject}\n\n{body}")
