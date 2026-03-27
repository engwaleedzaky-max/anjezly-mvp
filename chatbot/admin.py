from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from config import ADMIN_PIN, BRAND_AR
from db import fetch_last_providers, fetch_last_requests

router = APIRouter()


def _e(value: object) -> str:
    return escape("" if value is None else str(value))


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, pin: Optional[str] = None) -> str:
    ok = request.session.get("admin_ok") is True

    if pin and pin.strip() == ADMIN_PIN:
        request.session["admin_ok"] = True
        ok = True

    if not ok:
        return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_e(BRAND_AR)} | لوحة الأدمن</title>
</head>
<body style="font-family:system-ui,Arial; padding:24px;">
<h2>لوحة الأدمن</h2>
<p>ادخل الرقم السري (PIN)</p>
<form method="get" action="/admin">
  <input name="pin" placeholder="PIN" style="padding:10px; width:240px;"/>
  <button type="submit" style="padding:10px;">دخول</button>
</form>
</body>
</html>"""

    requests_data = fetch_last_requests(50)
    providers_data = fetch_last_providers(50)

    req_rows = ""
    for r in requests_data:
        req_rows += f"""
        <tr>
            <td>{_e(r.get('created_at'))}</td>
            <td>{_e(r.get('category_name'))}</td>
            <td>{_e(r.get('service_name'))}</td>
            <td>{_e(r.get('customer_name'))}</td>
            <td>{_e(r.get('customer_phone'))}</td>
        </tr>
        """

    prov_rows = ""
    for p in providers_data:
        prov_rows += f"""
        <tr>
            <td>{_e(p.get('created_at'))}</td>
            <td>{_e(p.get('provider_name'))}</td>
            <td>{_e(p.get('provider_phone'))}</td>
            <td>{_e(p.get('profession'))}</td>
        </tr>
        """

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_e(BRAND_AR)} | لوحة الأدمن</title>
</head>
<body style="font-family:system-ui,Arial; padding:24px; background:#0b1220; color:white;">

<h2>لوحة الأدمن</h2>
<p><a href="/" style="color:#22c55e;">رجوع للشات</a></p>

<hr>

<h3>📌 آخر 50 طلب</h3>
<p>إجمالي المعروض: {len(requests_data)}</p>

<table border="1" cellpadding="6" cellspacing="0" style="width:100%; background:white; color:black;">
<tr style="background:#e5e7eb;">
<th>التاريخ</th>
<th>القسم</th>
<th>الخدمة</th>
<th>الاسم</th>
<th>الهاتف</th>
</tr>
{req_rows}
</table>

<hr style="margin:30px 0;">

<h3>🧰 آخر 50 مقدم خدمة</h3>
<p>إجمالي المعروض: {len(providers_data)}</p>

<table border="1" cellpadding="6" cellspacing="0" style="width:100%; background:white; color:black;">
<tr style="background:#e5e7eb;">
<th>التاريخ</th>
<th>الاسم</th>
<th>الهاتف</th>
<th>المهنة</th>
</tr>
{prov_rows}
</table>

</body>
</html>"""
