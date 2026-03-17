# file: config.py
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

# Neon / Postgres
DATABASE_URL = (os.environ.get("DATABASE_URL", "") or os.environ.get("NEON_DATABASE_URL", "")).strip()

CMD_BACK = "__back__"
CMD_RESTART = "__restart__"

MIN_NAME = int(os.environ.get("MIN_NAME", "2"))
MIN_ADDRESS = int(os.environ.get("MIN_ADDRESS", "3"))