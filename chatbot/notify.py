# notify.py
from __future__ import annotations

import os
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.mime.text import MIMEText


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name, default)
    return (v or "").strip()


def _send_email(subject: str, body: str) -> None:
    """
    Sends email via SMTP (Gmail recommended).
    Required env vars:
      SMTP_HOST=smtp.gmail.com
      SMTP_PORT=587
      SMTP_USER=your_gmail@gmail.com
      SMTP_PASS=app_password_16_chars
      EMAIL_FROM=your_gmail@gmail.com   (optional; defaults to SMTP_USER)
      NOTIFY_EMAIL_TO=receiver@gmail.com (can be same)
    """
    smtp_host = _env("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    email_from = _env("EMAIL_FROM") or smtp_user
    email_to = _env("NOTIFY_EMAIL_TO")

    if not (smtp_user and smtp_pass and email_to):
        print(
            "[EMAIL] Missing env vars. Need SMTP_USER, SMTP_PASS, NOTIFY_EMAIL_TO "
            f"(got SMTP_USER={bool(smtp_user)}, SMTP_PASS={bool(smtp_pass)}, NOTIFY_EMAIL_TO={bool(email_to)})"
        )
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            # Gmail uses STARTTLS on 587
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print("[EMAIL] Sent OK ->", email_to)
    except Exception as e:
        # ✅ IMPORTANT: do not crash the app
        print("[EMAIL] ERROR:", repr(e))


def _send_telegram(text: str) -> None:
    """
    Optional Telegram notification (free).
    Env vars (optional):
      TG_BOT_TOKEN=xxxxx
      TG_CHAT_ID=123456789
    """
    token = _env("TG_BOT_TOKEN")
    chat_id = _env("TG_CHAT_ID")
    if not (token and chat_id):
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        print("[TG] Sent OK")
    except Exception as e:
        print("[TG] ERROR:", repr(e))


def notify_new_request(payload: dict) -> None:
    """
    Call this after saving the request/provider.
    payload example:
      {"type":"request", "service":"...", "name":"...", "phone":"...", "address":"...", "details":"..."}
    """
    try:
        kind = (payload.get("type") or "").strip() or "request"

        if kind == "provider":
            subject = "🚀 تسجيل مقدم خدمة جديد"
            body = (
                "تم تسجيل مقدم خدمة جديد:\n\n"
                f"الاسم: {payload.get('name','')}\n"
                f"الهاتف: {payload.get('phone','')}\n"
                f"المهنة: {payload.get('profession','')}\n"
                f"ماذا يضيف للفريق: {payload.get('contrib','')}\n"
                f"ماذا يصنع من البيت: {payload.get('home','')}\n"
            )
        else:
            subject = "🟢 طلب خدمة جديد"
            body = (
                "تم استلام طلب جديد:\n\n"
                f"القسم: {payload.get('category','')}\n"
                f"الخدمة: {payload.get('service','')}\n\n"
                f"الاسم: {payload.get('name','')}\n"
                f"الهاتف: {payload.get('phone','')}\n"
                f"العنوان: {payload.get('address','')}\n"
                f"التفاصيل: {payload.get('details','')}\n"
            )

        _send_email(subject, body)
        _send_telegram(body)
    except Exception as e:
        # ✅ never crash the app
        print("[NOTIFY] ERROR:", repr(e))