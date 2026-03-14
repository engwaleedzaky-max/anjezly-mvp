# file: app.py
"""
أنجزلي - MVP
- Brand: أنجزلي | اطلبها، وإحنا ننجزها
- Users: طالب الخدمة (customer) + مقدم الخدمة (provider) register/login with password
- Admin: login with PIN only
- Services: dynamic (admin can add continuously)
- Admin: assign/reassign provider from dropdown with Force option
- Forgot password: reset codes created via /forgot, visible to admin, used via /reset

Run:
  pip install fastapi uvicorn jinja2 python-multipart itsdangerous
  python -m uvicorn app:app --reload

Open:
  http://127.0.0.1:8000/register
  http://127.0.0.1:8000/login
  http://127.0.0.1:8000/admin
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional, TypedDict

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

DB_PATH = Path("app.db")

# Branding
BRAND_NAME = "أنجزلي"
SLOGAN = "اطلبها، وإحنا ننجزها"
BRAND_PRIMARY = "#0F172A"  # navy
BRAND_ACCENT = "#16A34A"  # green

# Admin PIN
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


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def new_salt() -> bytes:
    return os.urandom(16)


def hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return dk.hex()


def template_ctx(request: Request, *, title: str, subtitle: str) -> dict:
    return {
        "request": request,
        "title": title,
        "subtitle": subtitle,
        "brand_name": BRAND_NAME,
        "slogan": SLOGAN,
        "brand_primary": BRAND_PRIMARY,
        "brand_accent": BRAND_ACCENT,
        "user": get_session_user(request),
    }


def get_session_user(request: Request) -> Optional[SessionUser]:
    raw = request.session.get("user")
    if not isinstance(raw, dict):
        return None
    role = raw.get("role")
    name = raw.get("name")
    if role not in ("customer", "provider", "admin"):
        return None
    if not isinstance(name, str) or not name.strip():
        return None
    return {"role": role, "name": name.strip()}


def require_role(request: Request, role: Role) -> SessionUser:
    user = get_session_user(request)
    if not user or user["role"] != role:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

def require_role_html(request: Request, role: Role) -> SessionUser | RedirectResponse: 
    user = get_session_user(request)
    if not user or user["role"] != role:
        return RedirectResponse("/login?error=يجب+تسجيل+الدخول+كأدمن", status_code=303)
    return user

def init_db() -> None:
    with closing(get_conn()) as conn, conn:
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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt_hex TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                role TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

        # Seed services once
        c = conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
        if int(c) == 0:
            now = utc_now()
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


def ensure_templates() -> None:
    Path("templates").mkdir(exist_ok=True)

    (Path("templates") / "base.html").write_text(
        """<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ brand_name }} | {{ title }}</title>
  <style>
    :root{
      --primary: {{ brand_primary }};
      --accent: {{ brand_accent }};
      --muted: #6b7280;
      --border: #e5e7eb;
      --shadow: 0 10px 25px rgba(0,0,0,.06);
    }
    body { font-family: system-ui, Arial; margin: 24px; line-height: 1.6; background: #fff; color: #111827; }
    .card { background: #fff; border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin: 12px 0; box-shadow: var(--shadow); }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    label { display: block; margin-bottom: 6px; font-weight: 800; }
    input, textarea, select, button { font: inherit; padding: 10px 12px; border-radius: 12px; border: 1px solid #d1d5db; width: 100%; box-sizing: border-box; background: #fff; }
    textarea { min-height: 110px; }

    .btn { cursor: pointer; transition: transform .05s ease, opacity .15s ease; }
    .btn:active { transform: translateY(1px); }
    .btn-primary { border: none; background: var(--accent); color: #fff; font-weight: 900; }
    .btn-primary:hover { opacity: .92; }
    .btn-secondary { background: #fff; border: 1px solid var(--border); }
    .btn-secondary:hover { border-color: #cbd5e1; }
    .btn-danger { border: none; background: #b00020; color: #fff; font-weight: 900; }
    .btn-danger:hover { opacity: .92; }

    .badge { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border); text-decoration: none; color: #111827; background: #fff; transition: background .15s ease, border-color .15s ease; white-space: nowrap; }
    .badge:hover { background: #f8fafc; border-color: #cbd5e1; }
    .badge-primary { border-color: rgba(22,163,74,.25); background: rgba(22,163,74,.08); }
    .muted { color: var(--muted); }
    .danger { color: #b00020; }
    .split { display: grid; grid-template-columns: 1fr; gap: 12px; }
    @media (min-width: 900px) { .split { grid-template-columns: 1fr 1fr; } }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { border-bottom: 1px solid #eef2f7; padding: 10px; text-align: right; vertical-align: top; }
    .table th { background: #f8fafc; }
    .mini { font-size: 12px; }

    .brand-wrap { display:flex; align-items:center; gap: 12px; }
    .brand-name { font-size: 28px; font-weight: 900; margin: 0; letter-spacing: .2px; color: var(--primary); }
    .slogan { margin: 0; color: var(--muted); }
    .topbar { display:flex; justify-content: space-between; gap: 12px; align-items:center; }
    .topbar-right { display:flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
    .logo { width: 44px; height: 44px; border-radius: 14px; background: linear-gradient(135deg, rgba(22,163,74,.18), rgba(15,23,42,.08)); display:flex; align-items:center; justify-content:center; border: 1px solid rgba(15,23,42,.10); }
    .logo svg { width: 26px; height: 26px; }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand-wrap">
      <div class="logo" aria-label="Logo">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M13 2L4 14h7l-1 8 10-14h-7l0-6z" stroke="var(--accent)" stroke-width="1.6" stroke-linejoin="round"/>
          <path d="M21 18.2a3.2 3.2 0 0 1-4.8 2.8l-5.5-5.5 2.2-2.2 5.5 5.5a.9.9 0 0 0 1.5-.6v-1.1l1.1-1.1h1.1a.9.9 0 0 0 .6-1.5l-1.2-1.2 1.9-1.9 1.2 1.2a3.2 3.2 0 0 1-2.6 5.4z" fill="var(--primary)" opacity=".9"/>
        </svg>
      </div>
      <div>
        <p class="brand-name">{{ brand_name }}</p>
        <p class="slogan">{{ slogan }}</p>
      </div>
    </div>

    <div class="topbar-right">
      <a href="/" class="badge badge-primary">واجهة طالب الخدمة</a>
      <a href="/provider" class="badge">واجهة مقدم الخدمة</a>
      <a href="/admin" class="badge">لوحة الأدمن</a>
      <a href="/register" class="badge">تسجيل</a>
      <a href="/login" class="badge">دخول</a>
      <a href="/forgot" class="badge">نسيت كلمة المرور</a>
      <a href="/logout" class="badge">خروج</a>
    </div>
  </div>

  <div style="margin-top: 14px;">
    <h2 style="margin: 0; color: var(--primary);">{{ title }}</h2>
    <p class="muted">{{ subtitle }}</p>

    {% if user %}
      <p class="muted">مسجل كـ: <b>{{ user.name }}</b> ({{ user.role }})</p>
    {% else %}
      <p class="muted">غير مسجل دخول.</p>
    {% endif %}
  </div>

  {% block content %}{% endblock %}
</body>
</html>
""",
        encoding="utf-8",
    )

    (Path("templates") / "register.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 640px;">
  <h3 style="margin-top:0;">إنشاء حساب</h3>
  <p class="muted">طالب الخدمة / مقدم الخدمة فقط. (الأدمن عبر PIN في صفحة الدخول).</p>

  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b class="danger">خطأ:</b> {{ error }}
    </div>
  {% endif %}

  <form method="post" action="/register">
    <div style="margin-bottom:12px;">
      <label>نوع الحساب</label>
      <select name="role" required>
        <option value="customer">طالب الخدمة</option>
        <option value="provider">مقدم الخدمة</option>
      </select>
    </div>

    <div style="margin-bottom:12px;">
      <label>الاسم (Unique)</label>
      <input name="name" required />
    </div>

    <div style="margin-bottom:12px;">
      <label>كلمة المرور</label>
      <input type="password" name="password" required />
    </div>

    <div style="margin-bottom:12px;">
      <label>تأكيد كلمة المرور</label>
      <input type="password" name="password2" required />
    </div>

    <button class="btn btn-primary" type="submit">تسجيل</button>
  </form>

  <p class="muted" style="margin-top:12px;">
    لديك حساب؟ <a class="badge" href="/login">تسجيل دخول</a>
  </p>
</div>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "login.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 640px;">
  <h3 style="margin-top:0;">تسجيل دخول</h3>
  <p class="muted">طالب الخدمة / مقدم الخدمة بكلمة مرور. الأدمن بـ PIN.</p>

  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b class="danger">خطأ:</b> {{ error }}
    </div>
  {% endif %}

  <form method="post" action="/login">
    <div style="margin-bottom:12px;">
      <label>الدور</label>
      <select id="role" name="role" required>
        <option value="customer">طالب الخدمة</option>
        <option value="provider">مقدم الخدمة</option>
        <option value="admin">Admin</option>
      </select>
    </div>

    <div style="margin-bottom:12px;">
      <label>الاسم</label>
      <input name="name" required />
    </div>

    <div id="pwWrap" style="margin-bottom:12px;">
      <label>كلمة المرور</label>
      <input type="password" name="password" />
    </div>

    <div id="pinWrap" style="margin-bottom:12px; display:none;">
      <label>Admin PIN</label>
      <input name="admin_pin" placeholder="مثال: 1234" />
    </div>

    <button class="btn btn-primary" type="submit">دخول</button>
  </form>

  <p class="muted" style="margin-top:12px;">
    لا يوجد حساب؟ <a class="badge" href="/register">تسجيل</a>
  </p>
</div>

<script>
  const role = document.getElementById('role');
  const pinWrap = document.getElementById('pinWrap');
  const pwWrap = document.getElementById('pwWrap');
  function sync() {
    const isAdmin = (role.value === 'admin');
    pinWrap.style.display = isAdmin ? 'block' : 'none';
    pwWrap.style.display = isAdmin ? 'none' : 'block';
  }
  role.addEventListener('change', sync);
  sync();
</script>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "forgot.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 640px;">
  <h3 style="margin-top:0;">نسيت كلمة المرور</h3>
  <p class="muted">اكتب اسمك ونوع الحساب. سيتم إنشاء كود Reset ويظهر للأدمن في لوحة الأدمن.</p>

  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b class="danger">خطأ:</b> {{ error }}
    </div>
  {% endif %}

  <form method="post" action="/forgot">
    <div style="margin-bottom:12px;">
      <label>نوع الحساب</label>
      <select name="role" required>
        <option value="customer">طالب الخدمة</option>
        <option value="provider">مقدم الخدمة</option>
      </select>
    </div>

    <div style="margin-bottom:12px;">
      <label>الاسم</label>
      <input name="name" required />
    </div>

    <button class="btn btn-primary" type="submit">إنشاء كود</button>
  </form>

  <p class="muted" style="margin-top:12px;">
    لديك كود؟ <a class="badge" href="/reset">تغيير كلمة المرور</a>
  </p>
</div>
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "reset.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 640px;">
  <h3 style="margin-top:0;">تغيير كلمة المرور</h3>
  <p class="muted">استخدم كود Reset الذي يعطيك إياه الأدمن.</p>

  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b class="danger">خطأ:</b> {{ error }}
    </div>
  {% endif %}

  <form method="post" action="/reset">
    <div style="margin-bottom:12px;">
      <label>نوع الحساب</label>
      <select name="role" required>
        <option value="customer">طالب الخدمة</option>
        <option value="provider">مقدم الخدمة</option>
      </select>
    </div>

    <div style="margin-bottom:12px;">
      <label>الاسم</label>
      <input name="name" required />
    </div>

    <div style="margin-bottom:12px;">
      <label>كود Reset</label>
      <input name="code" placeholder="6 أرقام" required />
    </div>

    <div style="margin-bottom:12px;">
      <label>كلمة المرور الجديدة</label>
      <input type="password" name="password" required />
    </div>

    <div style="margin-bottom:12px;">
      <label>تأكيد كلمة المرور</label>
      <input type="password" name="password2" required />
    </div>

    <button class="btn btn-primary" type="submit">حفظ</button>
  </form>
</div>
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
          <textarea name="description" placeholder="اشرح طلبك..." required></textarea>
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
          <div class="row" style="justify-content: space-between;">
            <div><b>#{{ r.id }}</b> — {{ r.service_name }}</div>
            <span class="badge">الحالة: {{ r.status }}</span>
          </div>
          <div class="muted">تاريخ: {{ r.created_at }}</div>
          <p>{{ r.description }}</p>
          <div class="row" style="justify-content: space-between;">
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
    <p class="muted">أنت مقدم خدمة: <b>{{ user.name }}</b>.</p>

    {% if requests|length == 0 %}
      <p class="muted">لا توجد طلبات.</p>
    {% else %}
      {% for r in requests %}
        <div class="card">
          <div class="row" style="justify-content: space-between;">
            <div><b>#{{ r.id }}</b> — {{ r.service_name }}</div>
            <span class="badge">الحالة: {{ r.status }}</span>
          </div>
          <div class="muted">تاريخ: {{ r.created_at }}</div>
          <p>{{ r.description }}</p>
          <div class="row" style="justify-content: space-between;">
            <div class="muted">هاتف طالب الخدمة: {{ r.customer_phone }}</div>
            <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>
          </div>

          {% if r.status == 'new' %}
            <form method="post" action="/requests/{{ r.id }}/accept">
              <button class="btn btn-primary" type="submit">قبول الطلب</button>
            </form>
          {% endif %}
        </div>
      {% endfor %}
    {% endif %}
  </div>
{% endif %}
{% endblock %}
""",
        encoding="utf-8",
    )

    (Path("templates") / "details.html").write_text(
        """{% extends "base.html" %}
{% block content %}
<div class="card">
  <div class="row" style="justify-content: space-between;">
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
  <div class="split">
    <div class="card">
      <h3 style="margin-top:0;">إضافة خدمة جديدة</h3>
      <form method="post" action="/admin/services/add" class="row" style="align-items:flex-end;">
        <div style="flex:1; min-width: 260px;">
          <label>اسم الخدمة</label>
          <input name="service_name" required />
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
        <p class="muted">لا يوجد مقدمو خدمة بعد (سجّل حساب كمقدم خدمة).</p>
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
    <h3 style="margin-top:0;">أكواد استعادة كلمة المرور (Reset)</h3>
    {% if reset_codes|length == 0 %}
      <p class="muted">لا توجد أكواد.</p>
    {% else %}
      <table class="table">
        <thead>
          <tr>
            <th>الاسم</th><th>الدور</th><th>الكود</th><th>ينتهي</th><th>مستخدم</th><th>تاريخ</th>
          </tr>
        </thead>
        <tbody>
          {% for x in reset_codes %}
          <tr>
            <td><b>{{ x.user_name }}</b></td>
            <td class="muted">{{ x.role }}</td>
            <td><span class="badge badge-primary">{{ x.code }}</span></td>
            <td class="muted">{{ x.expires_at }}</td>
            <td class="muted">{{ x.used }}</td>
            <td class="muted">{{ x.created_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </div>

  <div class="card">
    <h3 style="margin-top:0;">الطلبات</h3>

    {% if requests|length == 0 %}
      <p class="muted">لا توجد طلبات.</p>
    {% else %}
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
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </div>
{% endif %}
{% endblock %}
""",
        encoding="utf-8",
    )


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
    now = utc_now()
    with closing(get_conn()) as conn, conn:
        try:
            conn.execute(
                "INSERT INTO services (name, is_active, created_at) VALUES (?, 1, ?)",
                (name, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Service already exists") from None


def create_user(name: str, role: Role, password: str) -> None:
    if role not in ("customer", "provider"):
        raise HTTPException(status_code=400, detail="Invalid role")

    name = name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name too short")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 chars")

    salt = new_salt()
    password_hash = hash_password(password, salt)
    now = utc_now()

    with closing(get_conn()) as conn, conn:
        try:
            conn.execute(
                """
                INSERT INTO users (name, role, password_hash, salt_hex, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (name, role, password_hash, salt.hex(), now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Name already exists") from None


def authenticate_user(name: str, role: Role, password: str) -> bool:
    name = name.strip()
    if not name or role not in ("customer", "provider"):
        return False

    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT password_hash, salt_hex, is_active FROM users WHERE name = ? AND role = ?",
            (name, role),
        ).fetchone()

    if not row or int(row["is_active"]) != 1:
        return False

    salt = bytes.fromhex(str(row["salt_hex"]))
    expected = str(row["password_hash"])
    got = hash_password(password, salt)
    return hmac.compare_digest(expected, got)


def list_active_providers() -> list[str]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT name FROM users WHERE is_active = 1 AND role = 'provider' ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [str(r["name"]) for r in rows]


def create_reset_code(name: str, role: Role, ttl_minutes: int = 10) -> str:
    if role not in ("customer", "provider"):
        raise HTTPException(status_code=400, detail="Invalid role")
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")

    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE name = ? AND role = ? AND is_active = 1",
            (name, role),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = utc_now()
    expires_at = (datetime.fromisoformat(now) + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO password_resets (user_name, role, code, expires_at, used, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (name, role, code, expires_at, now),
        )
    return code


def reset_password_with_code(name: str, role: Role, code: str, new_password: str) -> None:
    if role not in ("customer", "provider"):
        raise HTTPException(status_code=400, detail="Invalid role")

    name = name.strip()
    code = code.strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 chars")

    now = utc_now()

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            """
            SELECT id, expires_at, used
            FROM password_resets
            WHERE user_name = ? AND role = ? AND code = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (name, role, code),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid code")
        if int(row["used"]) == 1:
            raise HTTPException(status_code=409, detail="Code already used")
        if str(row["expires_at"]) < now:
            raise HTTPException(status_code=409, detail="Code expired")

        salt = new_salt()
        password_hash = hash_password(new_password, salt)

        conn.execute(
            "UPDATE users SET password_hash = ?, salt_hex = ? WHERE name = ? AND role = ?",
            (password_hash, salt.hex(), name, role),
        )
        conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (int(row["id"]),))


def list_recent_reset_codes(limit: int = 20) -> list[dict]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT user_name, role, code, expires_at, used, created_at
            FROM password_resets
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_request_by_id(request_id: int) -> ServiceRequest:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return ServiceRequest(
        id=int(row["id"]),
        service_name=str(row["service_name"]),
        description=str(row["description"]),
        customer_phone=str(row["customer_phone"]),
        status=row["status"],
        accepted_by=row["accepted_by"],
        created_at=str(row["created_at"]),
    )


def update_status_provider(request_id: int, *, new_status: Status, provider_name: str) -> None:
    provider_name = provider_name.strip()
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT status, accepted_by FROM service_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
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

        if current in ("accepted", "in_progress") and accepted_by != provider_name:
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


app = FastAPI(title=BRAND_NAME)
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


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: Optional[str] = None):
    ctx = template_ctx(request, title="التسجيل", subtitle="إنشاء حساب لطالب الخدمة أو مقدم الخدمة.")
    ctx["error"] = error
    return templates.TemplateResponse("register.html", ctx)


@app.post("/register")
def register_submit(
    request: Request,
    role: Role = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
):
    if role not in ("customer", "provider"):
        return RedirectResponse("/register?error=اختر+نوع+حساب+صحيح", status_code=303)

    if password != password2:
        return RedirectResponse("/register?error=كلمتا+المرور+غير+متطابقتين", status_code=303)

    try:
        create_user(name=name, role=role, password=password)
    except HTTPException as e:
        return RedirectResponse(f"/register?error={str(e.detail).replace(' ', '+')}", status_code=303)

    request.session["user"] = {"role": role, "name": name.strip()}
    return RedirectResponse("/provider" if role == "provider" else "/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: Optional[str] = None):
    ctx = template_ctx(request, title="تسجيل الدخول", subtitle="دخول بكلمة مرور لطالب/مقدم الخدمة، و PIN للأدمن.")
    ctx["error"] = error
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login")
def login_submit(
    request: Request,
    role: Role = Form(...),
    name: str = Form(...),
    password: str = Form(""),
    admin_pin: str = Form(""),
):
    name = name.strip()
    if not name:
        return RedirectResponse("/login?error=الاسم+مطلوب", status_code=303)

    if role == "admin":
        if admin_pin.strip() != ADMIN_PIN:
            return RedirectResponse("/login?error=PIN+غير+صحيح", status_code=303)
        request.session["user"] = {"role": "admin", "name": name}
        return RedirectResponse("/admin", status_code=303)

    if role not in ("customer", "provider"):
        return RedirectResponse("/login?error=دور+غير+صحيح", status_code=303)

    if not password:
        return RedirectResponse("/login?error=كلمة+المرور+مطلوبة", status_code=303)

    if not authenticate_user(name=name, role=role, password=password):
        return RedirectResponse("/login?error=بيانات+دخول+غير+صحيحة", status_code=303)

    request.session["user"] = {"role": role, "name": name}
    return RedirectResponse("/provider" if role == "provider" else "/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/forgot", response_class=HTMLResponse)
def forgot_page(request: Request, error: Optional[str] = None):
    ctx = template_ctx(request, title="نسيت كلمة المرور", subtitle="إنشاء كود Reset عبر الأدمن.")
    ctx["error"] = error
    return templates.TemplateResponse("forgot.html", ctx)


@app.post("/forgot")
def forgot_submit(request: Request, role: Role = Form(...), name: str = Form(...)):
    try:
        create_reset_code(name=name, role=role)
    except HTTPException as e:
        return RedirectResponse(f"/forgot?error={str(e.detail).replace(' ', '+')}", status_code=303)
    return RedirectResponse("/login?error=تم+إنشاء+كود+Reset.+تواصل+مع+الأدمن", status_code=303)


@app.get("/reset", response_class=HTMLResponse)
def reset_page(request: Request, error: Optional[str] = None):
    ctx = template_ctx(request, title="تغيير كلمة المرور", subtitle="استخدم كود Reset من الأدمن.")
    ctx["error"] = error
    return templates.TemplateResponse("reset.html", ctx)


@app.post("/reset")
def reset_submit(
    request: Request,
    role: Role = Form(...),
    name: str = Form(...),
    code: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
):
    if password != password2:
        return RedirectResponse("/reset?error=كلمتا+المرور+غير+متطابقتين", status_code=303)

    try:
        reset_password_with_code(name=name, role=role, code=code, new_password=password)
    except HTTPException as e:
        return RedirectResponse(f"/reset?error={str(e.detail).replace(' ', '+')}", status_code=303)

    return RedirectResponse("/login?error=تم+تغيير+كلمة+المرور.+سجل+دخول", status_code=303)


@app.get("/", response_class=HTMLResponse)
def customer_home(request: Request):
    services = list_active_services()
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 10").fetchall()
    reqs = [ServiceRequest(
        id=int(r["id"]),
        service_name=str(r["service_name"]),
        description=str(r["description"]),
        customer_phone=str(r["customer_phone"]),
        status=r["status"],
        accepted_by=r["accepted_by"],
        created_at=str(r["created_at"]),
    ) for r in rows]

    ctx = template_ctx(request, title="واجهة طالب الخدمة", subtitle="أنشئ طلبك بسهولة واختر الخدمة المناسبة.")
    ctx["services"] = services
    ctx["requests"] = reqs
    return templates.TemplateResponse("customer.html", ctx)


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

    created_at = utc_now()
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO service_requests (service_name, description, customer_phone, status, created_at)
            VALUES (?, ?, ?, 'new', ?)
            """,
            (service_name, description.strip(), customer_phone.strip(), created_at),
        )
    return RedirectResponse("/", status_code=303)


@app.get("/provider", response_class=HTMLResponse)
def provider_dashboard(request: Request):
    require_role(request, "provider")
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 50").fetchall()
    reqs = [ServiceRequest(
        id=int(r["id"]),
        service_name=str(r["service_name"]),
        description=str(r["description"]),
        customer_phone=str(r["customer_phone"]),
        status=r["status"],
        accepted_by=r["accepted_by"],
        created_at=str(r["created_at"]),
    ) for r in rows]

    ctx = template_ctx(request, title="واجهة مقدم الخدمة", subtitle="تابع الطلبات وقم بقبول/تحديث الطلبات.")
    ctx["requests"] = reqs
    ctx["status_filter"] = ""
    return templates.TemplateResponse("provider.html", ctx)


@app.get("/requests/{request_id}", response_class=HTMLResponse)
def request_details(request: Request, request_id: int):
    r = get_request_by_id(request_id)
    ctx = template_ctx(request, title="تفاصيل الطلب", subtitle="عرض تفاصيل الطلب والتحكم في حالته.")
    ctx["r"] = r
    return templates.TemplateResponse("details.html", ctx)


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
def admin_dashboard(request: Request):
    require_role(request, "admin")
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 200").fetchall()
    reqs = [ServiceRequest(
        id=int(r["id"]),
        service_name=str(r["service_name"]),
        description=str(r["description"]),
        customer_phone=str(r["customer_phone"]),
        status=r["status"],
        accepted_by=r["accepted_by"],
        created_at=str(r["created_at"]),
    ) for r in rows]

    ctx = template_ctx(request, title="لوحة الأدمن", subtitle="إدارة الطلبات والخدمات وتعيين مقدمي الخدمة.")
    ctx["requests"] = reqs
    ctx["providers"] = list_active_providers()
    ctx["services"] = list_active_services()
    ctx["reset_codes"] = list_recent_reset_codes()
    return templates.TemplateResponse("admin.html", ctx)


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
        raise HTTPException(status_code=400, detail="Provider not registered")
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