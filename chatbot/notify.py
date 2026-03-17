# file: notify.py
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

# Telegram optional (لو مش عايزه الآن سيظل معطّل بدون env vars)
import json
import urllib.parse
import urllib.request

from models import ChatState

BRAND_AR = os.getenv("BRAND_AR", "أنجزلي")


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) else default


def _safe(x: Optional[str]) -> str:
    return (x or "").strip()


def _send_email(subject: str, body: str) -> None:
    """
    Gmail:
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587 (STARTTLS) أو 465 (SSL)
      - SMTP_USER=anjezly01@gmail.com
      - SMTP_PASS=App Password (16 chars)
      - EMAIL_FROM=anjezly01@gmail.com
      - NOTIFY_EMAIL_TO=yourtarget@email.com (ممكن نفس الإيميل)
    """
    smtp_host = _env("SMTP_HOST", "")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER", "")
    smtp_pass = _env("SMTP_PASS", "")
    email_from = _env("EMAIL_FROM", smtp_user)
    email_to = _env("NOTIFY_EMAIL_TO", "")

    if not (smtp_host and smtp_user and smtp_pass and email_from and email_to):
        print("[EMAIL] Skipped: missing env vars (SMTP_HOST/SMTP_USER/SMTP_PASS/EMAIL_FROM/NOTIFY_EMAIL_TO).")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)

    if smtp_port == 465:
        # SSL
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    else:
        # STARTTLS (587 recommended)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

    print("[EMAIL] Sent OK to:", email_to)


def _send_telegram(text: str) -> None:
    """
    Supports:
      - TELEGRAM_CHAT_IDS="id1,id2,-100groupid"
      - fallback: TELEGRAM_CHAT_ID="id"
    """
    token = _env("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return

    ids_raw = _env("TELEGRAM_CHAT_IDS", "") or _env("TELEGRAM_CHAT_ID", "")
    ids = [x.strip() for x in ids_raw.split(",") if x.strip()]
    if not ids:
        return

    for chat_id in ids:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
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
            print("[TG] Sent OK ->", chat_id)
        except Exception as e:
            print("[TG] ERROR:", chat_id, repr(e))

def notify_new_request(state: ChatState) -> None:
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

    try:
        _send_email(subject, body)
    except Exception as e:
        print("[EMAIL] ERROR:", repr(e))

    try:
        _send_telegram(body)
    except Exception as e:
        print("[TG] ERROR:", repr(e))


def notify_new_provider(state: ChatState) -> None:
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
    except Exception as e:
        print("[EMAIL] ERROR:", repr(e))

    try:
        _send_telegram(body)
    except Exception as e:
        print("[TG] ERROR:", repr(e))


# aliases (لو bot.py يستورد أسماء مختلفة)
notify_request = notify_new_request
notify_provider = notify_new_provider