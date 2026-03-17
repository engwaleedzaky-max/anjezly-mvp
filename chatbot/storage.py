# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from openpyxl import Workbook, load_workbook

from config import REQUESTS_XLSX, PROVIDERS_XLSX, DATABASE_URL
from models import ChatState

# --- Excel helpers (best effort; on Render free disk may reset) ---

REQ_HEADERS = ["التاريخ", "القسم", "الخدمة", "الاسم", "الهاتف", "العنوان", "التفاصيل"]
PROV_HEADERS = ["التاريخ", "الاسم", "الهاتف", "المهنة", "تقدر تضيف ايه للفريق", "تعرف تصنع ايه من بيتك"]

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _ensure_xlsx(path: str, headers: list[str]) -> None:
    if os.path.exists(path):
        return
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    wb.save(path)

def save_request_to_excel(state: ChatState) -> None:
    _ensure_xlsx(REQUESTS_XLSX, REQ_HEADERS)
    wb = load_workbook(REQUESTS_XLSX)
    ws = wb.active
    ws.append([
        _utc_iso(),
        state.category_name,
        state.service_name,
        state.name,
        state.phone,
        state.address,
        state.details,
    ])
    wb.save(REQUESTS_XLSX)

def save_provider_to_excel(state: ChatState) -> None:
    _ensure_xlsx(PROVIDERS_XLSX, PROV_HEADERS)
    wb = load_workbook(PROVIDERS_XLSX)
    ws = wb.active
    ws.append([
        _utc_iso(),
        state.p_name,
        state.p_phone,
        state.p_profession,
        state.p_contrib,
        state.p_home,
    ])
    wb.save(PROVIDERS_XLSX)

# --- Neon (Postgres) helpers (persistent) ---

def neon_enabled() -> bool:
    return bool(DATABASE_URL)

def _connect():
    import psycopg
    return psycopg.connect(DATABASE_URL, autocommit=True)

def init_neon() -> bool:
    if not neon_enabled():
        return False
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS requests (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              category TEXT NOT NULL,
              service TEXT NOT NULL,
              name TEXT NOT NULL,
              phone TEXT NOT NULL,
              address TEXT NOT NULL,
              details TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS providers (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              name TEXT NOT NULL,
              phone TEXT NOT NULL,
              profession TEXT NOT NULL,
              contrib TEXT NOT NULL,
              home TEXT NOT NULL
            );
            """)
        return True
    except Exception:
        return False

def save_request_to_neon(state: ChatState) -> bool:
    if not neon_enabled():
        return False
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO requests (category, service, name, phone, address, details)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (state.category_name, state.service_name, state.name, state.phone, state.address, state.details),
            )
        return True
    except Exception:
        return False

def save_provider_to_neon(state: ChatState) -> bool:
    if not neon_enabled():
        return False
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO providers (name, phone, profession, contrib, home)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (state.p_name, state.p_phone, state.p_profession, state.p_contrib, state.p_home),
            )
        return True
    except Exception:
        return False

def list_last_requests_from_neon(limit: int = 50) -> list[dict]:
    if not neon_enabled():
        return []
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, category, service, name, phone, address, details
                FROM requests
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "created_at": r[0].isoformat(sep=" ", timespec="seconds") if hasattr(r[0], "isoformat") else str(r[0]),
                "category": r[1],
                "service": r[2],
                "name": r[3],
                "phone": r[4],
                "address": r[5],
                "details": r[6],
            }
            for r in rows
        ]
    except Exception:
        return []

def list_last_providers_from_neon(limit: int = 50) -> list[dict]:
    if not neon_enabled():
        return []
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, name, phone, profession, contrib, home
                FROM providers
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "created_at": r[0].isoformat(sep=" ", timespec="seconds") if hasattr(r[0], "isoformat") else str(r[0]),
                "name": r[1],
                "phone": r[2],
                "profession": r[3],
                "contrib": r[4],
                "home": r[5],
            }
            for r in rows
        ]
    except Exception:
        return []
