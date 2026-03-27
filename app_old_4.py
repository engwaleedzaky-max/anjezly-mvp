# file: app.py
"""
Service Marketplace MVP (Step 3) - Simple Login + Admin
- Roles: customer/provider/admin (simple session login, no password)
- Customer creates requests
- Provider accepts and updates only own orders
- Admin sees ALL orders and can manage them (status change / delete)

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

Role = Literal["customer", "provider", "admin"]
Status = Literal["new", "accepted", "in_progress", "completed", "canceled"]


class SessionUser(TypedDict):
    role: Role
    name: str


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
  </style>
</head>
<body>
  <div class="row" style="justify-content: space-between; align-items: center;">
    <h2 style="margin:0;">{{ title }}</h2>
    <div class="row" style="align-items:center;">
      <a href="/" class="badge">واجهة العميل</a>
      <a href="/provider" class="badge">واجهة المزوّد</a>
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
  <h3 style="margin-top:0;">تسجيل دخول بسيط</h3>
  <p class="muted">بدون كلمة مرور (للتعلم فقط). اختر الدور واكتب اسمك.</p>
  {% if error %}
    <div class="card" style="border-color:#b00020;">
      <b>خطأ:</b> {{ error }}
    </div>
  {% endif %}
  <form method="post" action="/login">
    <div style="margin-bottom:12px;">
      <label>الدور</label>
      <select name="role" required>
        <option value="customer">عميل</option>
        <option value="provider">مزوّد</option>
        <option value="admin">مدير (Admin)</option>
      </select>
    </div>
    <div style="margin-bottom:12px;">
      <label>الاسم</label>
      <input name="name" placeholder="مثال: أحمد" required />
    </div>
    <button class="btn btn-primary" type="submit">دخول</button>
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
        <p class="muted">لتجربة إنشاء الطلب كعميل: سجل دخول بدور <b>customer</b>.</p>
        <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
      </div>
    {% else %}
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
            <div><b>#{{ r.id }}</b> — {{ r.service_type }}</div>
            <span class="badge">الحالة: {{ r.status }}</span>
          </div>
          <div class="muted">تاريخ: {{ r.created_at }}</div>
          <p>{{ r.description }}</p>
          <div class="row" style="justify-content: space-between; align-items:center;">
            <div class="muted">هاتف العميل: {{ r.customer_phone }}</div>
            <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>
          </div>
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
{% if not user or user.role != 'provider' %}
  <div class="card">
    <h3 style="margin-top:0;">لوحة المزوّد</h3>
    <p class="muted">يجب تسجيل الدخول بدور <b>provider</b> لعرض لوحة المزوّد.</p>
    <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
  </div>
{% else %}
  <div class="card">
    <h3 style="margin-top:0;">لوحة المزوّد</h3>
    <p class="muted">أنت مزوّد: <b>{{ user.name }}</b>. يمكنك قبول طلبات جديدة وتحديث طلباتك فقط.</p>

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
        <div class="row" style="justify-content: space-between; align-items:center;">
          <div class="muted">هاتف العميل: {{ r.customer_phone }}</div>
          <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>
        </div>
        {% if r.accepted_by %}
          <div class="muted">قُبل بواسطة: {{ r.accepted_by }}</div>
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
    <div><b>طلب #{{ r.id }}</b> — {{ r.service_type }}</div>
    <span class="badge">الحالة: {{ r.status }}</span>
  </div>

  <div class="muted">تاريخ: {{ r.created_at }}</div>
  <p style="margin-bottom: 0;"><b>الوصف</b></p>
  <p>{{ r.description }}</p>

  <p style="margin-bottom: 0;"><b>هاتف العميل</b></p>
  <p class="muted">{{ r.customer_phone }}</p>

  {% if r.accepted_by %}
    <p style="margin-bottom: 0;"><b>المزوّد</b></p>
    <p class="muted">{{ r.accepted_by }}</p>
  {% endif %}
</div>

<div class="card">
  <h3 style="margin-top:0;">تحديث الحالة</h3>

  {% if not user or user.role != 'provider' %}
    <p class="muted">يجب تسجيل الدخول كمزوّد لتحديث الحالة.</p>
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
    <a class="badge" href="/provider">لوحة المزوّد</a>
    <a class="badge" href="/">واجهة العميل</a>
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
    <p class="muted">يجب تسجيل الدخول بدور <b>admin</b> لعرض لوحة الأدمن.</p>
    <a class="badge" href="/login">اذهب لتسجيل الدخول</a>
  </div>
{% else %}
  <div class="card">
    <h3 style="margin-top:0;">لوحة الأدمن</h3>
    <p class="muted">عرض جميع الطلبات + التحكم فيها.</p>

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
            <th>المزوّد</th>
            <th>الهاتف</th>
            <th>تاريخ</th>
            <th>تحكم</th>
          </tr>
        </thead>
        <tbody>
          {% for r in requests %}
          <tr>
            <td><b>{{ r.id }}</b></td>
            <td>{{ r.service_type }}</td>
            <td><span class="badge">{{ r.status }}</span></td>
            <td class="muted">{{ r.accepted_by or '-' }}</td>
            <td class="muted">{{ r.customer_phone }}</td>
            <td class="muted">{{ r.created_at }}</td>
            <td>
              <div class="row" style="gap:8px;">
                <a class="badge" href="/requests/{{ r.id }}">تفاصيل</a>

                <form method="post" action="/admin/requests/{{ r.id }}/status" style="min-width: 220px;">
                  <select name="new_status" required>
                    <option value="new">new</option>
                    <option value="accepted">accepted</option>
                    <option value="in_progress">in_progress</option>
                    <option value="completed">completed</option>
                    <option value="canceled">canceled</option>
                  </select>
                  <button class="btn btn-primary" type="submit" style="margin-top:6px;">تغيير الحالة</button>
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


def get_request_by_id(request_id: int) -> ServiceRequest:
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT * FROM service_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return row_to_request(row)


def update_status_provider(
    request_id: int,
    *,
    new_status: Status,
    provider_name: str,
) -> None:
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

        if current in ("accepted", "in_progress"):
            if accepted_by != provider_name:
                raise HTTPException(status_code=403, detail="Not your order")

        conn.execute(
            "UPDATE service_requests SET status = ?, accepted_by = ? WHERE id = ?",
            (new_status, accepted_by, request_id),
        )


def update_status_admin(
    request_id: int,
    *,
    new_status: Status,
    admin_note: Optional[str] = None,
) -> None:
    _ = admin_note
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT id FROM service_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")

        conn.execute(
            "UPDATE service_requests SET status = ? WHERE id = ?",
            (new_status, request_id),
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
            "subtitle": "دخول بسيط باستخدام Session.",
            "user": get_session_user(request),
            "error": error,
        },
    )


@app.post("/login")
def login_submit(
    request: Request,
    role: Role = Form(...),
    name: str = Form(...),
):
    name = name.strip()
    if not name:
        return RedirectResponse("/login?error=الاسم+مطلوب", status_code=303)

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
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 10").fetchall()
    reqs = [row_to_request(r) for r in rows]
    return templates.TemplateResponse(
        "customer.html",
        {
            "request": request,
            "title": "تطبيق خدمات (نسخة بسيطة)",
            "subtitle": "عميل ينشئ طلب خدمة (بدون دفع/خرائط).",
            "requests": reqs,
            "user": get_session_user(request),
        },
    )


@app.post("/requests")
def create_request(
    request: Request,
    service_type: str = Form(...),
    description: str = Form(...),
    customer_phone: str = Form(...),
):
    require_role(request, "customer")
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
    status: Optional[str] = None,
):
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
            "title": "لوحة المزوّد",
            "subtitle": "قائمة الطلبات + قبول الطلبات الجديدة.",
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
            "subtitle": "عرض تفاصيل الطلب.",
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
def set_status(
    request: Request,
    request_id: int,
    new_status: Status = Form(...),
):
    user = require_role(request, "provider")
    update_status_provider(request_id, new_status=new_status, provider_name=user["name"])
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    status: Optional[str] = None,
):
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
            "subtitle": "عرض كل الطلبات والتحكم فيها.",
            "requests": reqs,
            "status_filter": status_filter,
            "user": user,
        },
    )


@app.post("/admin/requests/{request_id}/status")
def admin_set_status(
    request: Request,
    request_id: int,
    new_status: Status = Form(...),
):
    require_role(request, "admin")
    update_status_admin(request_id, new_status=new_status)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/requests/{request_id}/delete")
def admin_delete_request(
    request: Request,
    request_id: int,
):
    require_role(request, "admin")
    delete_request_admin(request_id)
    return RedirectResponse("/admin", status_code=303)