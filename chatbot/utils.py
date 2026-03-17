# -*- coding: utf-8 -*-
import re

CMD_BACK = "رجوع"
CMD_RESTART = "بدء من جديد"

MIN_NAME = 2
MIN_ADDRESS = 2
MIN_DETAILS = 2

def normalize_text(s: str) -> str:
    return (s or "").strip()

def is_number_choice(s: str) -> bool:
    return bool(re.fullmatch(r"\d+", s.strip()))

def validate_phone(s: str) -> str | None:
    s = re.sub(r"\s+", "", (s or "").strip())
    digits = re.sub(r"\D+", "", s)
    if len(digits) < 10:
        return None
    return digits

def wants_restart(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"restart", "start over", "reset", "#", "ابدأ من جديد", "بدء من جديد", "start"}

def safe_trunc(s: str, n: int = 300) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n-1] + "…"
