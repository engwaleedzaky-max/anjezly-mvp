# file: storage.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from config import PROVIDERS_XLSX, REQUESTS_XLSX
from models import ChatState

# =========================
# Excel
# =========================
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

    _ensure_header(
        ws,
        ["created_at", "القسم", "الخدمة", "الاسم", "الهاتف", "العنوان", "التفاصيل", "source"],
    )
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


def save_provider_to_excel(state: ChatState) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")

    if PROVIDERS_XLSX.exists():
        wb = load_workbook(PROVIDERS_XLSX)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "providers"

    _ensure_header(
        ws,
        ["created_at", "الاسم", "الهاتف", "المهنة", "ماذا تضيف للفريق", "تصنع ايه من البيت", "source"],
    )
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


# =========================
# Neon (Postgres) - Optional
# =========================
def neon_enabled() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def neon_health() -> bool:
    if not neon_enabled():
        return False
    try:
        import psycopg  # type: ignore
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        return True
    except Exception:
        return False


def _neon_init_tables() -> None:
    import psycopg  # type: ignore

    ddl_requests = """
    CREATE TABLE IF NOT EXISTS requests (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      category TEXT,
      service TEXT,
      name TEXT,
      phone TEXT,
      address TEXT,
      details TEXT,
      source TEXT
    );
    """

    ddl_providers = """
    CREATE TABLE IF NOT EXISTS providers (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      name TEXT,
      phone TEXT,
      profession TEXT,
      contrib TEXT,
      home TEXT,
      source TEXT
    );
    """

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl_requests)
            cur.execute(ddl_providers)
        conn.commit()


def save_request_to_neon(state: ChatState) -> None:
    if not neon_enabled():
        return
    import psycopg  # type: ignore

    _neon_init_tables()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO requests (category, service, name, phone, address, details, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    state.category_name,
                    state.service_name,
                    state.name,
                    state.phone,
                    state.address,
                    state.details,
                    "web_chat",
                ),
            )
        conn.commit()


def save_provider_to_neon(state: ChatState) -> None:
    if not neon_enabled():
        return
    import psycopg  # type: ignore

    _neon_init_tables()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO providers (name, phone, profession, contrib, home, source)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    state.p_name,
                    state.p_phone,
                    state.p_profession,
                    state.p_contrib,
                    state.p_home,
                    "web_chat",
                ),
            )
        conn.commit()


def fetch_recent_requests_neon(limit: int = 50) -> list[dict[str, Any]]:
    if not neon_enabled():
        return []
    import psycopg  # type: ignore

    _neon_init_tables()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, category, service, name, phone, address, details
                FROM requests
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "created_at": str(r[0]),
                "category": r[1] or "",
                "service": r[2] or "",
                "name": r[3] or "",
                "phone": r[4] or "",
                "address": r[5] or "",
                "details": r[6] or "",
            }
        )
    return out


def fetch_recent_providers_neon(limit: int = 50) -> list[dict[str, Any]]:
    if not neon_enabled():
        return []
    import psycopg  # type: ignore

    _neon_init_tables()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, name, phone, profession, contrib, home
                FROM providers
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "created_at": str(r[0]),
                "name": r[1] or "",
                "phone": r[2] or "",
                "profession": r[3] or "",
                "contrib": r[4] or "",
                "home": r[5] or "",
            }
        )
    return out