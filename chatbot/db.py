# file: db.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

try:
    import psycopg
except Exception:
    psycopg = None  # type: ignore

from models import ChatState


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def db_enabled() -> bool:
    return bool(database_url()) and psycopg is not None


def init_db() -> None:
    if not db_enabled():
        return

    sql = """
    CREATE TABLE IF NOT EXISTS requests (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL,
      category_name TEXT NOT NULL,
      service_name TEXT NOT NULL,
      name TEXT NOT NULL,
      phone TEXT NOT NULL,
      address TEXT NOT NULL,
      details TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at DESC);

    CREATE TABLE IF NOT EXISTS providers (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL,
      name TEXT NOT NULL,
      phone TEXT NOT NULL,
      profession TEXT NOT NULL,
      contrib TEXT NOT NULL,
      home TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_providers_created_at ON providers(created_at DESC);
    """

    with psycopg.connect(database_url()) as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def save_request_db(state: ChatState) -> None:
    if not db_enabled():
        return

    sql = """
    INSERT INTO requests (created_at, category_name, service_name, name, phone, address, details)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    now = datetime.utcnow()

    with psycopg.connect(database_url()) as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    now,
                    state.category_name or "غير محدد",
                    state.service_name or "غير محدد",
                    state.name or "",
                    state.phone or "",
                    state.address or "",
                    state.details or "",
                ),
            )
        conn.commit()


def save_provider_db(state: ChatState) -> None:
    if not db_enabled():
        return

    sql = """
    INSERT INTO providers (created_at, name, phone, profession, contrib, home)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    now = datetime.utcnow()

    with psycopg.connect(database_url()) as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    now,
                    state.p_name or "",
                    state.p_phone or "",
                    state.p_profession or "",
                    state.p_contrib or "",
                    state.p_home or "",
                ),
            )
        conn.commit()


def last_requests_db(limit: int = 50) -> list[dict[str, Any]]:
    if not db_enabled():
        return []

    sql = """
    SELECT created_at, category_name, service_name, name, phone, address, details
    FROM requests
    ORDER BY created_at DESC
    LIMIT %s
    """
    with psycopg.connect(database_url()) as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "created_at": r[0].isoformat(sep=" ", timespec="seconds"),
                "category_name": r[1],
                "service_name": r[2],
                "name": r[3],
                "phone": r[4],
                "address": r[5],
                "details": r[6],
            }
        )
    return out