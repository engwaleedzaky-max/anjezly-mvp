# -*- coding: utf-8 -*-
import os

# Branding
BRAND_AR = os.getenv("BRAND_AR", "أنجزلي")
SLOGAN_AR = os.getenv("SLOGAN_AR", "اطلبها، وإحنا ننجزها")

# Admin PIN
ADMIN_PIN = os.getenv("ADMIN_PIN", "4321").strip()

# Session secret (Render: set SESSION_SECRET)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")

# Telegram notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
# Comma-separated chat ids (users or group ids). Example: "123, -100123456"
TELEGRAM_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()]

# Neon Postgres (DATABASE_URL from Neon)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Excel files (local only on Render free may reset)
REQUESTS_XLSX = os.getenv("REQUESTS_XLSX", "requests.xlsx")
PROVIDERS_XLSX = os.getenv("PROVIDERS_XLSX", "providers.xlsx")
