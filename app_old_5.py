# file: app.py
"""
Service Marketplace MVP (Step 5 - Fixed)
- Roles: طالب الخدمة (customer) / مقدم الخدمة (provider) / Admin (admin)
- Admin login requires PIN
- Providers are stored in DB; admin assigns from a dropdown list
- Admin can force reassign even for completed/canceled orders
- Services are dynamic; admin can add new services; customer selects from list
- ✅ DB migration: supports old column service_type and new service_name

Run:
  pip install fastapi uvicorn jinja2 python-multipart itsdangerous
  python -m uvicorn app:app --reload

Open:
  http://127.0.0.1:8000/login
  http://127.0.0.1:8000/admin
"""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

DB_PATH = Path("app.db")

# ✅ غيّر هذا الرقم كما تريد
ADMIN_PIN = "1234"

Role = Literal["customer", "provider", "admin"]
Status = Literal["new", "accepted", "in_progress", "completed", "canceled"]


class SessionUser(TypedDict):
    role: Role
    name: str


@dataclass(frozen=True)
class ServiceRequest:
    id: int
    service_name: str
    description: str
    customer_phone: str
    status: Status
    accepted_by: Optional[str]
    created_at: str


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        # Orders table (new schema uses service_name)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                description TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                accepted_by TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # ✅ Migration: support old column service_type -> service_name
        cols = _table_columns(conn, "service_requests")

        if "service_name" not in cols:
            conn.execute("ALTER TABLE service_requests ADD COLUMN service_name TEXT")

        cols = _table_columns(conn, "service_requests")
        if "service_type" in cols:
            # Copy old data to new column where missing
            conn.execute(
                """
                UPDATE service_requests
                SET service_name = service_type
                WHERE (service_name IS NULL OR service_name = '')
                """
            )

        # Ensure NOT NULL-ish behavior for old rows (best-effort)
        conn.execute(
            """
            UPDATE service_requests
            SET service_name = 'غير محدد'
            WHERE (service_name IS NULL OR service_name = '')
            """
        )

        # Services table (dynamic)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

        # Providers table (registered by login)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

        # Seed default services if empty
        count = conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
        if int(count) == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            defaults = [
                "كهرباء",
                "سباكة",
                "نجارة",
                "تكنولوجيا المعلومات",
                "الاتصالات",
                "التنظيف",
                "النقل",
            ]
            conn.executemany(
                "INSERT INTO services (name, is_active, created_at) VALUES (?, 1, ?)",
                [(n, now) for n in defaults],
            )


def _row_get(row: sqlite3.Row, *names: str, default: str = "") -> str:
    keys = set(row.keys())
    for n in names:
        if n in keys:
            v = row[n]
            if v is None:
                continue
            return str(v)
    return default


def row_to_request(row: sqlite3.Row) -> ServiceRequest:
    # ✅ supports both service_name (new) and service_type (old)
    service_name = _row_get(row, "service_name", "service_type", default="غير محدد")
    return ServiceRequest(
        id=int(row["id"]),
        service_name=service_name,
        description=str(row["description"]),
        customer_phone=str(row["customer_phone"]),
        status=row["status"],
        accepted_by=row["accepted_by"],
        created_at=str(row["created_at"]),
    )


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
    .btn-danger { border: none; background: #b00020; color: #fff; }
    .btn-secondary { background: #fff; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; border: 1px solid #ccc; text-decoration: none; }
    .muted { color: #666; }
    .split { display: grid; grid-template-columns: 1fr; gap: 12px; }
    @media (min-width: 900px) { .split { grid-template-columns: 1fr 1fr; } }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { border-bottom: 1px solid #eee; padding: 10px; text-align: right; vertical-align: top; }
    .table th { background: #fafafa; }
    .mini { font-size: 12px; }
  </style>
</head>
<body>
  <div class="row" style="justify-content: space-between; align-items: center;">
    <h2 style="margin:0;">{{ title }}</h2>
    <div class="row" style="align-items:center;">
      <a href="/" class="badge">واجهة طالب الخدمة</a>
      <a href="/provider" class="badge">واجهة مقدم الخدمة</a>
      <a href="/admin" class="badge">لوحة الأدمن</a>
      <a href="/login" class="badge">تسجيل دخول</a>
      <a href="/logout" class="badge">خروج</a>
    </div>
  </div>

  {% if user %}
    <p class="muted">مسجل كـ: <b>{{ user.name }}</b> ({{ user.role }})</p>
  {% else %}
    <p class="muted">غير مسجل دخول.</p>
  {% endif %}

  <p class="muted">{{ subtitle }}</p>
  {% block content %}{% endblock %}
</body>
</html>
""",
        encoding="utf-8",
    )

    (Path("templates") / "login.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 560px;">
  <h3 style="margin-top:0;">تسجيل دخول</h3>
  <p class="muted">بدون كلمة مرور (للتعلم فقط). الأدمن يتطلب PIN.</p>

  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b>خطأ:</b> {{ error }}
    </div>
  {% endif %}

  <form method="post" action="/login">
    <div style="margin-bottom:12px;">
      <label>الدور</label>
      <select id="role" name="role" required>
        <option value="customer">طالب الخدمة</option>
        <option value="provider">مقدم الخدمة</option>
        <option value="admin">مدير (Admin)</option>
      </select>
    </div>

    <div style="margin-bottom:12px;">
      <label>الاسم</label>
      <input name="name" placeholder="مثال: أحمد" required />
      <p class="muted mini" style="margin:6px 0 0;">مقدم الخدمة يتم تسجيله تلقائياً في قائمة مقدمي الخدمة.</p>
    </div>

    <div id="pinWrap" style="margin-bottom:12px; display:none;">
      <label>Admin PIN</label>
      <input name="admin_pin" placeholder="مثال: 1234" />
    </div>

    <button class="btn btn-primary" type="submit">دخول</button>
  </form>
</div>

<script>
  const role = document.getElementById('role');
  const wrap = document.getElementById('pinWrap');
  function sync() { wrap.style.display = (role.value === 'admin') ? 'block' : 'none'; }
  role.addEventListener('change', sync);
  sync();
</script>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "customer.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="split">
  <div class="card">
    <h3 style="margin-top:0;">إنشاء طلب خدمة</h3>

    {% if not user or user.role != 'customer' %}
      <div class="card">
        <p class="muted">لتجربة إنشاء الطلب: سجل دخول بدور <b>طالب الخدمة</b>.</p>
        <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
      </div>
    {% else %}
      <form method="post" action="/requests">
        <div style="margin-bottom:12px;">
          <label>نوع الخدمة</label>
          <select name="service_name" required>
            {% for s in services %}
              <option value="{{ s }}">{{ s }}</option>
            {% endfor %}
          </select>
          <p class="muted mini" style="margin:6px 0 0;">الخدمات تُدار من لوحة الأدمن.</p>
        </div>

        <div style="margin-bottom:12px;">
          <label>وصف الطلب</label>
          <textarea name="description" placeholder="مثال: عطل في مفتاح النور..." required></textarea>
        </div>

        <div style="margin-bottom:12px;">
          <label>رقم الهاتف</label>
          <input name="customer_phone" placeholder="01xxxxxxxxx" required />
        </div>

        <button class="btn btn-primary" type="submit">إرسال الطلب</button>
      </form>
    {% endif %}
  </div>

  <div class="card">
    <h3 style="margin-top:0;">آخر الطلبات</h3>
    {% if requests|length == 0 %}
      <p class="muted">لا توجد طلبات بعد.</p>
    {% else %}
      {% for r in requests %}
        <div class="card" style="margin: 10px 0;">
          <div class="row" style="justify-content: space-between; align-items:center;">
            <div><b>#{{ r.id }}</b> — {{ r.service_name }}</div>
            <span class="badge">الحالة: {{ r.status }}</span>
          </div>
          <div class="muted">تاريخ: {{ r.created_at }}</div>
          <p>{{ r.description }}</p>
          <div class="row" style="justify-content: space-between; align-items:center;">
            <div class="muted">هاتف طالب الخدمة: {{ r.customer_phone }}</div>
            <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>
          </div>
          {% if r.accepted_by %}
            <div class="muted">مقدم الخدمة: {{ r.accepted_by }}</div>
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
{% if not user or user.role != 'provider' %}
  <div class="card">
    <h3 style="margin-top:0;">واجهة مقدم الخدمة</h3>
    <p class="muted">يجب تسجيل الدخول بدور <b>مقدم الخدمة</b>.</p>
    <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
  </div>
{% else %}
  <div class="card">
    <h3 style="margin-top:0;">واجهة مقدم الخدمة</h3>
    <p class="muted">أنت مقدم خدمة: <b>{{ user.name }}</b>. يمكنك قبول الطلبات الجديدة وتحديث طلباتك فقط.</p>

    <form method="get" action="/provider" class="row" style="align-items:flex-end;">
      <div style="min-width: 240px;">
        <label>فلتر الحالة</label>
        <select name="status">
          <option value="" {% if not status_filter %}selected{% endif %}>الكل</option>
          <option value="new" {% if status_filter == 'new' %}selected{% endif %}>new</option>
          <option value="accepted" {% if status_filter == 'accepted' %}selected{% endif %}>accepted</option>
          <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>in_progress</option>
          <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>completed</option>
          <option value="canceled" {% if status_filter == 'canceled' %}selected{% endif %}>canceled</option>
        </select>
      </div>
      <button class="btn btn-secondary" type="submit" style="min-width: 140px;">تحديث</button>
    </form>
  </div>

  {% if requests|length == 0 %}
    <p class="muted">لا توجد طلبات.</p>
  {% else %}
    {% for r in requests %}
      <div class="card">
        <div class="row" style="justify-content: space-between; align-items:center;">
          <div><b>#{{ r.id }}</b> — {{ r.service_name }}</div>
          <span class="badge">الحالة: {{ r.status }}</span>
        </div>
        <div class="muted">تاريخ: {{ r.created_at }}</div>
        <p>{{ r.description }}</p>
        <div class="row" style="justify-content: space-between; align-items:center;">
          <div class="muted">هاتف طالب الخدمة: {{ r.customer_phone }}</div>
          <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>
        </div>
        {% if r.accepted_by %}
          <div class="muted">مقدم الخدمة: {{ r.accepted_by }}</div>
        {% endif %}

        {% if r.status == 'new' %}
          <form method="post" action="/requests/{{ r.id }}/accept">
            <button class="btn btn-primary" type="submit">قبول الطلب</button>
          </form>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}
{% endif %}
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "details.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card">
  <div class="row" style="justify-content: space-between; align-items:center;">
    <div><b>طلب #{{ r.id }}</b> — {{ r.service_name }}</div>
    <span class="badge">الحالة: {{ r.status }}</span>
  </div>

  <div class="muted">تاريخ: {{ r.created_at }}</div>
  <p style="margin-bottom: 0;"><b>وصف الطلب</b></p>
  <p>{{ r.description }}</p>

  <p style="margin-bottom: 0;"><b>هاتف طالب الخدمة</b></p>
  <p class="muted">{{ r.customer_phone }}</p>

  {% if r.accepted_by %}
    <p style="margin-bottom: 0;"><b>مقدم الخدمة</b></p>
    <p class="muted">{{ r.accepted_by }}</p>
  {% endif %}
</div>

<div class="card">
  <h3 style="margin-top:0;">تحديث الحالة (لمقدم الخدمة)</h3>

  {% if not user or user.role != 'provider' %}
    <p class="muted">يجب تسجيل الدخول كمقدم خدمة لتحديث الحالة.</p>
    <a class="badge" href="/login">تسجيل دخول</a>
  {% else %}
    <div class="row">
      {% if r.status == 'accepted' %}
        <form method="post" action="/requests/{{ r.id }}/status" style="min-width: 220px;">
          <input type="hidden" name="new_status" value="in_progress" />
          <button class="btn btn-primary" type="submit">بدء العمل</button>
        </form>
      {% endif %}

      {% if r.status == 'in_progress' %}
        <form method="post" action="/requests/{{ r.id }}/status" style="min-width: 220px;">
          <input type="hidden" name="new_status" value="completed" />
          <button class="btn btn-primary" type="submit">إنهاء الطلب</button>
        </form>
      {% endif %}

      {% if r.status in ['new','accepted','in_progress'] %}
        <form method="post" action="/requests/{{ r.id }}/status" style="min-width: 220px;">
          <input type="hidden" name="new_status" value="canceled" />
          <button class="btn btn-danger" type="submit">إلغاء</button>
        </form>
      {% endif %}
    </div>
  {% endif %}

  <div class="row" style="justify-content: space-between; align-items:center; margin-top: 12px;">
    <a class="badge" href="/provider">واجهة مقدم الخدمة</a>
    <a class="badge" href="/">واجهة طالب الخدمة</a>
  </div>
</div>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "admin.html").write_text(
        """{% extends "base.html" %}
{% block content %}
{% if not user or user.role != 'admin' %}
  <div class="card">
    <h3 style="margin-top:0;">لوحة الأدمن</h3>
    <p class="muted">يجب تسجيل الدخول بدور <b>admin</b> مع PIN.</p>
    <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
  </div>
{% else %}
  <div class="card">
    <h3 style="margin-top:0;">لوحة الأدمن</h3>
    <p class="muted">إدارة الطلبات + تعيين مقدم الخدمة + إدارة الخدمات.</p>
  </div>

  <div class="split">
    <div class="card">
      <h3 style="margin-top:0;">إضافة خدمة جديدة</h3>
      <form method="post" action="/admin/services/add" class="row" style="align-items:flex-end;">
        <div style="flex:1; min-width: 260px;">
          <label>اسم الخدمة</label>
          <input name="service_name" placeholder="مثال: دهانات / حدادة ..." required />
        </div>
        <button class="btn btn-primary" type="submit" style="min-width: 160px;">إضافة</button>
      </form>

      <p class="muted" style="margin: 10px 0 0;">الخدمات الحالية:</p>
      <div class="row" style="gap:6px;">
        {% for s in services %}
          <span class="badge">{{ s }}</span>
        {% endfor %}
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">مقدمو الخدمة المسجلون</h3>
      {% if providers|length == 0 %}
        <p class="muted">لا يوجد مقدمو خدمة بعد (سجّل دخول كمقدم خدمة لإضافته تلقائياً).</p>
      {% else %}
        <div class="row" style="gap:6px;">
          {% for p in providers %}
            <span class="badge">{{ p }}</span>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  </div>

  <div class="card">
    <h3 style="margin-top:0;">الطلبات</h3>
    <form method="get" action="/admin" class="row" style="align-items:flex-end;">
      <div style="min-width: 240px;">
        <label>فلتر الحالة</label>
        <select name="status">
          <option value="" {% if not status_filter %}selected{% endif %}>الكل</option>
          <option value="new" {% if status_filter == 'new' %}selected{% endif %}>new</option>
          <option value="accepted" {% if status_filter == 'accepted' %}selected{% endif %}>accepted</option>
          <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>in_progress</option>
          <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>completed</option>
          <option value="canceled" {% if status_filter == 'canceled' %}selected{% endif %}>canceled</option>
        </select>
      </div>
      <button class="btn btn-secondary" type="submit" style="min-width: 140px;">تحديث</button>
    </form>
  </div>

  {% if requests|length == 0 %}
    <p class="muted">لا توجد طلبات.</p>
  {% else %}
    <div class="card">
      <table class="table">
        <thead>
          <tr>
            <th>#</th>
            <th>الخدمة</th>
            <th>الحالة</th>
            <th>مقدم الخدمة</th>
            <th>هاتف طالب الخدمة</th>
            <th>تاريخ</th>
            <th>تحكم</th>
          </tr>
        </thead>
        <tbody>
          {% for r in requests %}
          <tr>
            <td><b>{{ r.id }}</b></td>
            <td>{{ r.service_name }}</td>
            <td><span class="badge">{{ r.status }}</span></td>
            <td class="muted">{{ r.accepted_by or '-' }}</td>
            <td class="muted">{{ r.customer_phone }}</td>
            <td class="muted">{{ r.created_at }}</td>
            <td>
              <div class="row" style="gap:8px;">
                <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>

                <form method="post" action="/admin/requests/{{ r.id }}/assign" style="min-width: 260px;">
                  <label style="margin:0 0 6px;">تعيين/تغيير مقدم الخدمة</label>
                  <select name="provider_name" required>
                    {% for p in providers %}
                      <option value="{{ p }}" {% if r.accepted_by == p %}selected{% endif %}>{{ p }}</option>
                    {% endfor %}
                  </select>

                  <label class="mini" style="margin:8px 0 0;">
                    <input type="checkbox" name="force" value="1" />
                    Force (يسمح حتى لو Completed/Canceled)
                  </label>

                  <button class="btn btn-primary" type="submit" style="margin-top:6px;">حفظ</button>
                </form>

                <form method="post" action="/admin/requests/{{ r.id }}/status" style="min-width: 220px;">
                  <label style="margin:0 0 6px;">تغيير الحالة</label>
                  <select name="new_status" required>
                    <option value="new">new</option>
                    <option value="accepted">accepted</option>
                    <option value="in_progress">in_progress</option>
                    <option value="completed">completed</option>
                    <option value="canceled">canceled</option>
                  </select>
                  <button class="btn btn-secondary" type="submit" style="margin-top:6px;">تحديث الحالة</button>
                </form>

                <form method="post" action="/admin/requests/{{ r.id }}/delete" style="min-width: 140px;">
                  <button class="btn btn-danger" type="submit">حذف</button>
                </form>
              </div>

              {% if providers|length == 0 %}
                <p class="muted mini">لا يمكن التعيين لأن قائمة مقدمي الخدمة فارغة.</p>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}
{% endif %}
{% endblock %}
""",
        encoding="utf-8",
    )


def get_session_user(request: Request) -> Optional[SessionUser]:
    raw = request.session.get("user")
    if not isinstance(raw, dict):
        return None
    role = raw.get("role")
    name = raw.get("name")
    if role not in ("customer", "provider", "admin") or not isinstance(name, str) or not name.strip():
        return None
    return {"role": role, "name": name.strip()}


def require_role(request: Request, role: Role) -> SessionUser:
    user = get_session_user(request)
    if not user or user["role"] != role:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


def list_active_services() -> list[str]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT name FROM services WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [str(r["name"]) for r in rows]


def add_service(name: str) -> None:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="service_name is required")
    now = datetime.utcnow().isoformat(timespec="seconds")
    with closing(get_conn()) as conn, conn:
        try:
            conn.execute(
                "INSERT INTO services (name, is_active, created_at) VALUES (?, 1, ?)",
                (name, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Service already exists") from None


def upsert_provider(name: str) -> None:
    name = name.strip()
    if not name:
        return
    now = datetime.utcnow().isoformat(timespec="seconds")
    with closing(get_conn()) as conn, conn:
        try:
            conn.execute(
                "INSERT INTO providers (name, is_active, created_at) VALUES (?, 1, ?)",
                (name, now),
            )
        except sqlite3.IntegrityError:
            conn.execute("UPDATE providers SET is_active = 1 WHERE name = ?", (name,))


def list_active_providers() -> list[str]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT name FROM providers WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [str(r["name"]) for r in rows]


def get_request_by_id(request_id: int) -> ServiceRequest:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return row_to_request(row)


def update_status_provider(request_id: int, *, new_status: Status, provider_name: str) -> None:
    provider_name = provider_name.strip()

    with closing(get_conn()) as conn, conn:
        row = conn.execute("SELECT status, accepted_by FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")

        current: str = row["status"]
        accepted_by: Optional[str] = row["accepted_by"]

        allowed: dict[str, set[str]] = {
            "new": {"accepted", "canceled"},
            "accepted": {"in_progress", "canceled"},
            "in_progress": {"completed", "canceled"},
            "completed": set(),
            "canceled": set(),
        }

        if new_status not in allowed.get(current, set()):
            raise HTTPException(status_code=409, detail=f"Invalid transition: {current} -> {new_status}")

        if new_status == "accepted":
            if accepted_by is not None:
                raise HTTPException(status_code=409, detail="Already accepted")
            accepted_by = provider_name

        if current in ("accepted", "in_progress"):
            if accepted_by != provider_name:
                raise HTTPException(status_code=403, detail="Not your order")

        conn.execute(
            "UPDATE service_requests SET status = ?, accepted_by = ? WHERE id = ?",
            (new_status, accepted_by, request_id),
        )


def update_status_admin(request_id: int, *, new_status: Status) -> None:
    with closing(get_conn()) as conn, conn:
        row = conn.execute("SELECT id FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")

        if new_status == "new":
            conn.execute(
                "UPDATE service_requests SET status = 'new', accepted_by = NULL WHERE id = ?",
                (request_id,),
            )
            return

        conn.execute("UPDATE service_requests SET status = ? WHERE id = ?", (new_status, request_id))


def assign_provider_admin(request_id: int, *, provider_name: str, force: bool) -> None:
    provider_name = provider_name.strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider_name is required")

    with closing(get_conn()) as conn, conn:
        row = conn.execute("SELECT status FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")

        current: str = row["status"]
        if current in ("completed", "canceled") and not force:
            raise HTTPException(status_code=409, detail="Use force to reassign completed/canceled")

        new_status = "accepted" if current == "new" else current

        conn.execute(
            "UPDATE service_requests SET accepted_by = ?, status = ? WHERE id = ?",
            (provider_name, new_status, request_id),
        )


def delete_request_admin(request_id: int) -> None:
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM service_requests WHERE id = ?", (request_id,))


app = FastAPI(title="Service Marketplace MVP")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
    same_site="lax",
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    ensure_templates()


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "تسجيل الدخول",
            "subtitle": "دخول بسيط باستخدام Session + Admin PIN.",
            "user": get_session_user(request),
            "error": error,
        },
    )


@app.post("/login")
def login_submit(
    request: Request,
    role: Role = Form(...),
    name: str = Form(...),
    admin_pin: str = Form(""),
):
    name = name.strip()
    if not name:
        return RedirectResponse("/login?error=الاسم+مطلوب", status_code=303)

    if role == "admin" and admin_pin.strip() != ADMIN_PIN:
        return RedirectResponse("/login?error=PIN+غير+صحيح", status_code=303)

    if role == "provider":
        upsert_provider(name)

    request.session["user"] = {"role": role, "name": name}

    if role == "provider":
        return RedirectResponse("/provider", status_code=303)
    if role == "admin":
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def customer_home(request: Request):
    services = list_active_services()
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 10").fetchall()
    reqs = [row_to_request(r) for r in rows]
    return templates.TemplateResponse(
        "customer.html",
        {
            "request": request,
            "title": "تطبيق خدمات (نسخة بسيطة)",
            "subtitle": "طالب الخدمة ينشئ طلب خدمة، والخدمات تُدار من الأدمن.",
            "requests": reqs,
            "services": services,
            "user": get_session_user(request),
        },
    )


@app.post("/requests")
@app.post("/requests")
def create_request(
    request: Request,
    service_name: str = Form(...),
    description: str = Form(...),
    customer_phone: str = Form(...),
):
    require_role(request, "customer")

    services = set(list_active_services())
    service_name = service_name.strip()
    if service_name not in services:
        raise HTTPException(status_code=400, detail="Unknown service. Add it via admin.")

    created_at = datetime.utcnow().isoformat(timespec="seconds")

    with closing(get_conn()) as conn, conn:
        cols = _table_columns(conn, "service_requests")

        if "service_type" in cols:
            # ✅ توافق مع DB القديمة: اكتب العمودين
            conn.execute(
                """
                INSERT INTO service_requests (service_name, service_type, description, customer_phone, status, created_at)
                VALUES (?, ?, ?, ?, 'new', ?)
                """,
                (service_name, service_name, description.strip(), customer_phone.strip(), created_at),
            )
        else:
            # ✅ DB الجديدة فقط
            conn.execute(
                """
                INSERT INTO service_requests (service_name, description, customer_phone, status, created_at)
                VALUES (?, ?, ?, 'new', ?)
                """,
                (service_name, description.strip(), customer_phone.strip(), created_at),
            )

    return RedirectResponse("/", status_code=303)

@app.get("/provider", response_class=HTMLResponse)
def provider_dashboard(request: Request, status: Optional[str] = None):
    user = get_session_user(request)
    status_filter = (status or "").strip()

    query = "SELECT * FROM service_requests"
    params: list[str] = []
    where: list[str] = []

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
            "title": "واجهة مقدم الخدمة",
            "subtitle": "قبول الطلبات الجديدة وتحديث طلباتك فقط.",
            "requests": reqs,
            "status_filter": status_filter,
            "user": user,
        },
    )


@app.get("/requests/{request_id}", response_class=HTMLResponse)
def request_details(request: Request, request_id: int):
    r = get_request_by_id(request_id)
    return templates.TemplateResponse(
        "details.html",
        {
            "request": request,
            "title": "تفاصيل الطلب",
            "subtitle": "تفاصيل الطلب وتحديث الحالة لمقدم الخدمة.",
            "r": r,
            "user": get_session_user(request),
        },
    )


@app.post("/requests/{request_id}/accept")
def accept_request(request: Request, request_id: int):
    user = require_role(request, "provider")
    update_status_provider(request_id, new_status="accepted", provider_name=user["name"])
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@app.post("/requests/{request_id}/status")
def set_status(request: Request, request_id: int, new_status: Status = Form(...)):
    user = require_role(request, "provider")
    update_status_provider(request_id, new_status=new_status, provider_name=user["name"])
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, status: Optional[str] = None):
    user = get_session_user(request)
    status_filter = (status or "").strip()

    query = "SELECT * FROM service_requests"
    params: list[str] = []
    where: list[str] = []

    if status_filter:
        where.append("status = ?")
        params.append(status_filter)

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY id DESC LIMIT 200"

    with closing(get_conn()) as conn:
        rows = conn.execute(query, params).fetchall()

    reqs = [row_to_request(r) for r in rows]
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "title": "لوحة الأدمن",
            "subtitle": "إدارة الطلبات + تعيين مقدم الخدمة + إدارة الخدمات.",
            "requests": reqs,
            "status_filter": status_filter,
            "user": user,
            "providers": list_active_providers(),
            "services": list_active_services(),
        },
    )


@app.post("/admin/services/add")
def admin_add_service(request: Request, service_name: str = Form(...)):
    require_role(request, "admin")
    add_service(service_name)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/requests/{request_id}/assign")
def admin_assign_provider(
    request: Request,
    request_id: int,
    provider_name: str = Form(...),
    force: Optional[str] = Form(None),
):
    require_role(request, "admin")
    providers = set(list_active_providers())
    if provider_name.strip() not in providers:
        raise HTTPException(status_code=400, detail="Unknown provider. Provider must login once to be registered.")
    assign_provider_admin(request_id, provider_name=provider_name, force=bool(force))
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/requests/{request_id}/status")
def admin_set_status(request: Request, request_id: int, new_status: Status = Form(...)):
    require_role(request, "admin")
    update_status_admin(request_id, new_status=new_status)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/requests/{request_id}/delete")
def admin_delete_request(request: Request, request_id: int):
    require_role(request, "admin")
    delete_request_admin(request_id)
    return RedirectResponse("/admin", status_code=303)