# file: db.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

import psycopg
from psycopg.rows import dict_row


def get_database_url() -> str:
    return (
        os.environ.get("DATABASE_URL", "").strip()
        or os.environ.get("NEON_DATABASE_URL", "").strip()
    )


def db_enabled() -> bool:
    return bool(get_database_url())


@contextmanager
def conn_ctx() -> Iterator[psycopg.Connection]:
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    if not db_enabled():
        return

    with conn_ctx() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS service_requests (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              category_name TEXT NOT NULL,
              service_name  TEXT NOT NULL,
              customer_name TEXT NOT NULL,
              customer_phone TEXT NOT NULL,
              address TEXT NOT NULL,
              details TEXT NOT NULL,
              source TEXT NOT NULL DEFAULT 'web_chat'
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              provider_name TEXT NOT NULL,
              provider_phone TEXT NOT NULL,
              profession TEXT NOT NULL,
              contrib TEXT NOT NULL,
              home_make TEXT NOT NULL,
              source TEXT NOT NULL DEFAULT 'web_chat'
            );
            """
        )
        conn.commit()


def insert_request(row: Dict[str, Any]) -> None:
    if not db_enabled():
        return
    with conn_ctx() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO service_requests
              (category_name, service_name, customer_name, customer_phone, address, details, source)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(row["category_name"]),
                str(row["service_name"]),
                str(row["customer_name"]),
                str(row["customer_phone"]),
                str(row["address"]),
                str(row["details"]),
                str(row.get("source", "web_chat")),
            ),
        )
        conn.commit()


def insert_provider(row: Dict[str, Any]) -> None:
    if not db_enabled():
        return
    with conn_ctx() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO providers
              (provider_name, provider_phone, profession, contrib, home_make, source)
            VALUES
              (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(row["provider_name"]),
                str(row["provider_phone"]),
                str(row["profession"]),
                str(row["contrib"]),
                str(row["home_make"]),
                str(row.get("source", "web_chat")),
            ),
        )
        conn.commit()


def fetch_last_requests(limit: int = 50) -> List[Dict[str, Any]]:
    if not db_enabled():
        return []
    with conn_ctx() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, created_at, category_name, service_name, customer_name, customer_phone, address, details, source
            FROM service_requests
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def fetch_last_providers(limit: int = 50) -> List[Dict[str, Any]]:
    if not db_enabled():
        return []

    with conn_ctx() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id,
                   created_at,
                   name,
                   phone,
                   profession,
                   contrib,
                   home
            FROM providers
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())