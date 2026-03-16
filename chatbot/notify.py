# file: notify.py
from __future__ import annotations

import json
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Optional

from config import (
    BRAND_AR,
    NOTIFY_EMAIL_TO,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from models import ChatState


def _safe(s: Optional[str]) -> str:
    return (s or "").strip()


def _send_email(subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and NOTIFY_EMAIL_TO):
        return

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def _send_telegram(text: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
        obj = json.loads(payload)
        if not obj.get("ok", False):
            raise RuntimeError(f"Telegram API error: {payload}")


def notify_new_request(state: ChatState) -> None:
    """
    Fired after saving a customer request to Excel.
    """
    subject = f"{BRAND_AR} | طلب جديد"
    body = "\n".join(
        [
            "📌 طلب جديد",
            f"القسم: {_safe(state.category_name)}",
            f"الخدمة: {_safe(state.service_name)}",
            "",
            f"الاسم: {_safe(state.name)}",
            f"الهاتف: {_safe(state.phone)}",
            f"العنوان: {_safe(state.address)}",
            "",
            f"التفاصيل: {_safe(state.details)}",
        ]
    )

    # Email + Telegram (best-effort)
    try:
        _send_email(subject, body)
    except Exception:
        print("EMAIL ERROR:", repr(e))

    try:
        _send_telegram(body)
    except Exception:
        pass


def notify_new_provider(state: ChatState) -> None:
    """
    Fired after saving a provider registration to Excel.
    """
    subject = f"{BRAND_AR} | مقدم خدمة جديد"
    body = "\n".join(
        [
            "🧰 مقدم خدمة جديد",
            f"الاسم: {_safe(state.p_name)}",
            f"الهاتف: {_safe(state.p_phone)}",
            f"المهنة: {_safe(state.p_profession)}",
            f"يساهم بـ: {_safe(state.p_contrib)}",
            f"من البيت: {_safe(state.p_home)}",
        ]
    )

    try:
        _send_email(subject, body)
    except Exception:
        print("EMAIL ERROR:", repr(e))

    try:
        _send_telegram(body)
    except Exception:
        pass