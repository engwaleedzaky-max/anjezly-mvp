# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import urllib.request
from typing import Optional

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS
from utils import safe_trunc
from models import ChatState

def _telegram_send(chat_id: str, text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print("[TELEGRAM] ERROR:", repr(e))
        return False

def notify_new_request(state: ChatState) -> None:
    if not TELEGRAM_CHAT_IDS:
        return
    text = (
        "🟢 طلب جديد (طالب خدمة)\n\n"
        f"القسم: {state.category_name}\n"
        f"الخدمة: {state.service_name}\n"
        f"الاسم: {safe_trunc(state.name, 80)}\n"
        f"الهاتف: {state.phone}\n"
        f"العنوان: {safe_trunc(state.address, 120)}\n"
        f"التفاصيل: {safe_trunc(state.details, 500)}\n"
    )
    for cid in TELEGRAM_CHAT_IDS:
        _telegram_send(cid, text)

def notify_new_provider(state: ChatState) -> None:
    if not TELEGRAM_CHAT_IDS:
        return
    text = (
        "🟣 تسجيل جديد (مقدم خدمة)\n\n"
        f"الاسم: {safe_trunc(state.p_name, 80)}\n"
        f"الهاتف: {state.p_phone}\n"
        f"المهنة: {safe_trunc(state.p_profession, 120)}\n"
        f"يضيف للفريق: {safe_trunc(state.p_contrib, 200)}\n"
        f"من البيت: {safe_trunc(state.p_home, 200)}\n"
    )
    for cid in TELEGRAM_CHAT_IDS:
        _telegram_send(cid, text)
