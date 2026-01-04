import json
import os
import urllib.request


RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, from_email: str | None = None) -> bool:
    api_key = os.getenv("RESEND_API_KEY")
    sender = from_email or os.getenv("RESEND_FROM_EMAIL")
    if not api_key or not sender:
        return False

    payload = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }

    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
