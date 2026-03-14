# file: app.py
"""
Minimal Service Marketplace MVP (Step 0)
- Customer creates a service request
- Provider lists requests and can accept one

Run:
  pip install fastapi uvicorn jinja2 python-multipart
  uvicorn app:app --reload

Open:
  http://127.0.0.1:8000/            (customer)
  http://127.0.0.1:8000/provider    (provider)
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

DB_PATH = Path("app.db")

Status = Literal["new", "accepted", "completed", "canceled"]


@dataclass(frozen=True)
class ServiceRequest:
    id: int
    service_type: str
    description: str
    customer_phone: str
    status: Status
    accepted_by: Optional[str]
    created_at: str


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type TEXT NOT NULL,
                description TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                accepted_by TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def row_to_request(row: sqlite3.Row) -> ServiceRequest:
    return ServiceRequest(
        id=int(row["id"]),
        service_type=str(row["service_type"]),
        description=str(row["description"]),
        customer_phone=str(row["customer_phone"]),
        status=row["status"],
        accepted_by=row["accepted_by"],
        created_at=str(row["created_at"]),
    )


app = FastAPI(title="Service Marketplace MVP")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    ensure_templates()


def ensure_templates() -> None:
    Path("templates").mkdir(exist_ok=True)

    (Path("templates") / "base.html").write_text(
        """<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>
  <style>
    body { font-family: system-ui, Arial; margin: 24px; line-height: 1.6; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin: 12px 0; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; }
    label { display: block; margin-bottom: 6px; font-weight: 600; }
    input, textarea, select, button {
      font: inherit; padding: 10px 12px; border-radius: 10px; border: 1px solid #ccc;
      width: 100%; box-sizing: border-box;
    }
    textarea { min-height: 100px; }
    .btn { cursor: pointer; }
    .btn-primary { border: none; background: #111; color: #fff; }
    .btn-secondary { background: #fff; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; border: 1px solid #ccc; }
    .muted { color: #666; }
    .split { display: grid; grid-template-columns: 1fr; gap: 12px; }
    @media (min-width: 900px) { .split { grid-template-columns: 1fr 1fr; } }
  </style>
</head>
<body>
  <div class="row" style="justify-content: space-between; align-items: center;">
    <h2 style="margin:0;">{{ title }}</h2>
    <div class="row">
      <a href="/" class="badge">واجهة العميل</a>
      <a href="/provider" class="badge">واجهة المزوّد</a>
    </div>
  </div>
  <p class="muted">{{ subtitle }}</p>
  {% block content %}{% endblock %}
</body>
</html>
""",
        encoding="utf-8",
    )

    (Path("templates") / "customer.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="split">
  <div class="card">
    <h3 style="margin-top:0;">إنشاء طلب خدمة</h3>
    <form method="post" action="/requests">
      <div style="margin-bottom:12px;">
        <label>نوع الخدمة</label>
        <select name="service_type" required>
          <option value="كهرباء">كهرباء</option>
          <option value="سباكة">سباكة</option>
          <option value="نجارة">نجارة</option>
        </select>
      </div>

      <div style="margin-bottom:12px;">
        <label>وصف المشكلة</label>
        <textarea name="description" placeholder="مثال: عطل في مفتاح النور..." required></textarea>
      </div>

      <div style="margin-bottom:12px;">
        <label>رقم الهاتف</label>
        <input name="customer_phone" placeholder="01xxxxxxxxx" required />
      </div>

      <button class="btn btn-primary" type="submit">إرسال الطلب</button>
    </form>
  </div>

  <div class="card">
    <h3 style="margin-top:0;">آخر الطلبات</h3>
    {% if requests|length == 0 %}
      <p class="muted">لا توجد طلبات بعد.</p>
    {% else %}
      {% for r in requests %}
        <div class="card" style="margin: 10px 0;">
          <div class="row" style="justify-content: space-between; align-items:center;">
            <div><b>#{{ r.id }}</b> — {{ r.service_type }}</div>
            <span class="badge">الحالة: {{ r.status }}</span>
          </div>
          <div class="muted">تاريخ: {{ r.created_at }}</div>
          <p>{{ r.description }}</p>
          <div class="muted">هاتف العميل: {{ r.customer_phone }}</div>
          {% if r.accepted_by %}
            <div class="muted">قُبل بواسطة: {{ r.accepted_by }}</div>
          {% endif %}
        </div>
      {% endfor %}
    {% endif %}
  </div>
</div>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "provider.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card">
  <h3 style="margin-top:0;">لوحة المزوّد</h3>
  <p class="muted">هذه النسخة التجريبية: اكتب اسمك كمزوّد ثم اقبل أي طلب جديد.</p>

  <form method="get" action="/provider" class="row" style="align-items:flex-end;">
    <div style="flex:1; min-width: 240px;">
      <label>اسم المزوّد</label>
      <input name="provider_name" value="{{ provider_name or '' }}" placeholder="مثال: أحمد" required />
    </div>
    <div style="min-width: 200px;">
      <label>فلتر الحالة</label>
      <select name="status">
        <option value="" {% if not status_filter %}selected{% endif %}>الكل</option>
        <option value="new" {% if status_filter == 'new' %}selected{% endif %}>new</option>
        <option value="accepted" {% if status_filter == 'accepted' %}selected{% endif %}>accepted</option>
        <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>completed</option>
        <option value="canceled" {% if status_filter == 'canceled' %}selected{% endif %}>canceled</option>
      </select>
    </div>
    <button class="btn btn-secondary" type="submit">تحديث</button>
  </form>
</div>

{% if requests|length == 0 %}
  <p class="muted">لا توجد طلبات مطابقة.</p>
{% else %}
  {% for r in requests %}
    <div class="card">
      <div class="row" style="justify-content: space-between; align-items:center;">
        <div><b>#{{ r.id }}</b> — {{ r.service_type }}</div>
        <span class="badge">الحالة: {{ r.status }}</span>
      </div>
      <div class="muted">تاريخ: {{ r.created_at }}</div>
      <p>{{ r.description }}</p>
      <div class="muted">هاتف العميل: {{ r.customer_phone }}</div>
      {% if r.accepted_by %}
        <div class="muted">قُبل بواسطة: {{ r.accepted_by }}</div>
      {% endif %}

      {% if r.status == 'new' %}
        <form method="post" action="/requests/{{ r.id }}/accept">
          <input type="hidden" name="provider_name" value="{{ provider_name }}" />
          <button class="btn btn-primary" type="submit">قبول الطلب</button>
        </form>
      {% endif %}
    </div>
  {% endfor %}
{% endif %}
{% endblock %}
""",
        encoding="utf-8",
    )


@app.get("/", response_class=HTMLResponse)
def customer_home(request: Request):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM service_requests ORDER BY id DESC LIMIT 10"
        ).fetchall()
    reqs = [row_to_request(r) for r in rows]
    return templates.TemplateResponse(
        "customer.html",
        {
            "request": request,
            "title": "تطبيق خدمات (نسخة بسيطة)",
            "subtitle": "عميل ينشئ طلب خدمة (بدون دفع/خرائط).",
            "requests": reqs,
        },
    )


@app.post("/requests")
def create_request(
    service_type: str = Form(...),
    description: str = Form(...),
    customer_phone: str = Form(...),
):
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO service_requests (service_type, description, customer_phone, status, created_at)
            VALUES (?, ?, ?, 'new', ?)
            """,
            (service_type.strip(), description.strip(), customer_phone.strip(), created_at),
        )
    return RedirectResponse("/", status_code=303)


@app.get("/provider", response_class=HTMLResponse)
def provider_dashboard(
    request: Request,
    provider_name: Optional[str] = None,
    status: Optional[str] = None,
):
    provider_name = (provider_name or "").strip()
    status_filter = (status or "").strip()

    query = "SELECT * FROM service_requests"
    params: list[str] = []

    where = []
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY id DESC LIMIT 50"

    with closing(get_conn()) as conn:
        rows = conn.execute(query, params).fetchall()

    reqs = [row_to_request(r) for r in rows]
    return templates.TemplateResponse(
        "provider.html",
        {
            "request": request,
            "title": "لوحة المزوّد",
            "subtitle": "قائمة الطلبات + قبول الطلبات الجديدة.",
            "requests": reqs,
            "provider_name": provider_name,
            "status_filter": status_filter,
        },
    )


@app.post("/requests/{request_id}/accept")
def accept_request(
    request_id: int,
    provider_name: str = Form(...),
):
    provider_name = provider_name.strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider_name is required")

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT status FROM service_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")

        if row["status"] != "new":
            raise HTTPException(status_code=409, detail="Request is not new")

        conn.execute(
            """
            UPDATE service_requests
            SET status = 'accepted', accepted_by = ?
            WHERE id = ?
            """,
            (provider_name, request_id),
        )

    return RedirectResponse(f"/provider?provider_name={provider_name}", status_code=303)