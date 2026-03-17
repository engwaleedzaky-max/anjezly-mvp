# file: storage.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from config import PROVIDERS_XLSX, REQUESTS_XLSX
from db import db_enabled, fetch_last_providers, fetch_last_requests, insert_provider, insert_request
from models import ChatState


def _ensure_header(ws: Worksheet, headers: Sequence[str]) -> None:
    if ws.max_row == 1 and ws.max_column == 1 and ws["A1"].value is None:
        ws.append(list(headers))


def save_request_to_excel(state: ChatState) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")

    if REQUESTS_XLSX.exists():
        wb = load_workbook(REQUESTS_XLSX)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "requests"

    headers = ["created_at", "القسم", "الخدمة", "الاسم", "الهاتف", "العنوان", "التفاصيل", "source"]
    _ensure_header(ws, headers)

    ws.append(
        [
            created_at,
            state.category_name,
            state.service_name,
            state.name,
            state.phone,
            state.address,
            state.details,
            "web_chat",
        ]
    )
    wb.save(REQUESTS_XLSX)

    # Neon insert (لا نكسر الطلب لو حصل خطأ)
    if db_enabled():
        try:
            insert_request(
                {
                    "category_name": state.category_name,
                    "service_name": state.service_name,
                    "customer_name": state.name,
                    "customer_phone": state.phone,
                    "address": state.address,
                    "details": state.details,
                    "source": "web_chat",
                }
            )
        except Exception as e:
            print("[NEON] insert_request error:", repr(e))


def save_provider_to_excel(state: ChatState) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")

    if PROVIDERS_XLSX.exists():
        wb = load_workbook(PROVIDERS_XLSX)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "providers"

    headers = ["created_at", "الاسم", "الهاتف", "المهنة", "ماذا تضيف للفريق", "تصنع ايه من البيت", "source"]
    _ensure_header(ws, headers)

    ws.append(
        [
            created_at,
            state.p_name,
            state.p_phone,
            state.p_profession,
            state.p_contrib,
            state.p_home,
            "web_chat",
        ]
    )
    wb.save(PROVIDERS_XLSX)

    if db_enabled():
        try:
            insert_provider(
                {
                    "provider_name": state.p_name,
                    "provider_phone": state.p_phone,
                    "profession": state.p_profession,
                    "contrib": state.p_contrib,
                    "home_make": state.p_home,
                    "source": "web_chat",
                }
            )
        except Exception as e:
            print("[NEON] insert_provider error:", repr(e))


def export_requests_xlsx(path: Path, limit: int = 50) -> Path:
    rows = fetch_last_requests(limit) if db_enabled() else []
    wb = Workbook()
    ws = wb.active
    ws.title = "requests"
    ws.append(["created_at", "القسم", "الخدمة", "الاسم", "الهاتف", "العنوان", "التفاصيل", "source"])

    for r in rows:
        ws.append(
            [
                str(r["created_at"]),
                str(r["category_name"]),
                str(r["service_name"]),
                str(r["customer_name"]),
                str(r["customer_phone"]),
                str(r["address"]),
                str(r["details"]),
                str(r.get("source", "web_chat")),
            ]
        )
    wb.save(path)
    return path


def export_providers_xlsx(path: Path, limit: int = 50) -> Path:
    rows = fetch_last_providers(limit) if db_enabled() else []
    wb = Workbook()
    ws = wb.active
    ws.title = "providers"
    ws.append(["created_at", "الاسم", "الهاتف", "المهنة", "ماذا تضيف للفريق", "تصنع ايه من البيت", "source"])

    for r in rows:
        ws.append(
            [
                str(r["created_at"]),
                str(r["provider_name"]),
                str(r["provider_phone"]),
                str(r["profession"]),
                str(r["contrib"]),
                str(r["home_make"]),
                str(r.get("source", "web_chat")),
            ]
        )
    wb.save(path)
    return path