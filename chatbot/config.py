# file: chatbot_app/config.py
# =========================
from __future__ import annotations

import os
import secrets
from pathlib import Path

BRAND_AR = "أنجزلي"
SLOGAN_AR = "اطلبها، وإحنا ننجزها"

REQUESTS_XLSX = Path(os.environ.get("REQUESTS_XLSX", "requests.xlsx"))
PROVIDERS_XLSX = Path(os.environ.get("PROVIDERS_XLSX", "providers.xlsx"))

ADMIN_PIN = os.environ.get("ADMIN_PIN", "4321")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_urlsafe(32))

CMD_BACK = "__back__"
CMD_RESTART = "__restart__"

MIN_NAME = int(os.environ.get("MIN_NAME", "2"))
MIN_ADDRESS = int(os.environ.get("MIN_ADDRESS", "3"))

# ملاحظة: التفاصيل الآن تقبل أي نص غير فارغ (بدون حد أدنى للطول)

# ---- Notifications (Email / Telegram) ----
import os

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "0") or "0")
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "").strip()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()