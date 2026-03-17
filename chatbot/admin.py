# file: admin.py
from __future__ import annotations

import html
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from config import ADMIN_PIN, BRAND_AR, PROVIDERS_XLSX, REQUESTS_XLSX
from db import db_enabled, fetch_last_providers, fetch_last_requests
from storage import export_providers_xlsx, export_requests_xlsx

router = APIRouter()


def _esc(x: object) -> str:
    return html.escape("" if x is None else str(x))


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, pin: Optional[str] = None) -> str:
    ok = request.session.get("admin_ok") is True

    if pin and pin.strip() == ADMIN_PIN:
        request.session["admin_ok"] = True
        ok = True

    if not ok:
        return f"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{BRAND_AR} | لوحة الأدمن</title></head>
<body style="font-family:system-ui,Arial; padding:24px;">
<h2>لوحة الأدمن</h2>
<p>ادخل الرقم السري (PIN)</p>
<form method="get" action="/admin">
  <input name="pin" placeholder="PIN" style="padding:10px; width:240px;"/>
  <button type="submit" style="padding:10px;">دخول</button>
</form>
</body></html>"""

    # مصدر البيانات: Neon لو متاح
    neon = db_enabled()
    reqs = fetch_last_requests(50) if neon else []
    provs = fetch_last_providers(50) if neon else []

    req_exists = REQUESTS_XLSX.exists()
    prov_exists = PROVIDERS_XLSX.exists()

    def render_requests() -> str:
        if neon and not reqs:
            return "<p>لا توجد طلبات بعد.</p>"
        if not neon:
            return "<p>Neon غير مُفعل. أضف DATABASE_URL.</p>"

        rows = []
        for r in reqs:
            rows.append(
                "<tr>"
                f"<td>{_esc(r.get('created_at'))}</td>"
                f"<td>{_esc(r.get('category_name'))}</td>"
                f"<td>{_esc(r.get('service_name'))}</td>"
                f"<td>{_esc(r.get('customer_name'))}</td>"
                f"<td>{_esc(r.get('customer_phone'))}</td>"
                f"<td>{_esc(r.get('address'))}</td>"
                f"<td>{_esc(r.get('details'))}</td>"
                "</tr>"
            )
        return (
            "<table border='1' cellpadding='8' style='border-collapse:collapse; width:100%;'>"
            "<thead><tr>"
            "<th>التاريخ</th><th>القسم</th><th>الخدمة</th><th>الاسم</th><th>الهاتف</th><th>العنوان</th><th>التفاصيل</th>"
            "</tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    def render_providers() -> str:
        if neon and not provs:
            return "<p>لا يوجد مقدمو خدمة بعد.</p>"
        if not neon:
            return "<p>Neon غير مُفعل. أضف DATABASE_URL.</p>"

        rows = []
        for r in provs:
            rows.append(
                "<tr>"
                f"<td>{_esc(r.get('created_at'))}</td>"
                f"<td>{_esc(r.get('provider_name'))}</td>"
                f"<td>{_esc(r.get('provider_phone'))}</td>"
                f"<td>{_esc(r.get('profession'))}</td>"
                f"<td>{_esc(r.get('contrib'))}</td>"
                f"<td>{_esc(r.get('home_make'))}</td>"
                "</tr>"
            )
        return (
            "<table border='1' cellpadding='8' style='border-collapse:collapse; width:100%;'>"
            "<thead><tr>"
            "<th>التاريخ</th><th>الاسم</th><th>الهاتف</th><th>المهنة</th><th>ماذا تضيف</th><th>تصنع ايه من البيت</th>"
            "</tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{BRAND_AR} | لوحة الأدمن</title></head>
<body style="font-family:system-ui,Arial; padding:24px;">
<h2>لوحة الأدمن</h2>
<p><a href="/">رجوع للشات</a></p>

<p>Neon: {"✅ متصل" if neon else "❌ غير مُفعل (ضع DATABASE_URL)"} </p>

<h3>طلبات طالبي الخدمة (آخر 50)</h3>
<p>Excel محلي: {"✅ موجود" if req_exists else "❌ غير موجود"}</p>
<p>
  <a href='/admin/download/requests'>⬇️ تحميل requests.xlsx</a>
</p>
{render_requests()}

<hr style="margin:22px 0;"/>

<h3>بيانات مقدمي الخدمة (آخر 50)</h3>
<p>Excel محلي: {"✅ موجود" if prov_exists else "❌ غير موجود"}</p>
<p>
  <a href='/admin/download/providers'>⬇️ تحميل providers.xlsx</a>
</p>
{render_providers()}

</body></html>"""


@router.get("/admin/download/{which}")
def admin_download(request: Request, which: str) -> Response:
    if request.session.get("admin_ok") is not True:
        return RedirectResponse("/admin", status_code=303)

    # لو الملف موجود محليًا نزله
    if which == "requests" and REQUESTS_XLSX.exists():
        return FileResponse(str(REQUESTS_XLSX), filename="requests.xlsx")

    if which == "providers" and PROVIDERS_XLSX.exists():
        return FileResponse(str(PROVIDERS_XLSX), filename="providers.xlsx")

    # لو مش موجود على Render: ولد ملف Excel من Neon
    tmp = Path("/tmp")
    if which == "requests":
        out = tmp / "requests.xlsx"
        export_requests_xlsx(out, limit=50)
        return FileResponse(str(out), filename="requests.xlsx")

    if which == "providers":
        out = tmp / "providers.xlsx"
        export_providers_xlsx(out, limit=50)
        return FileResponse(str(out), filename="providers.xlsx")

    return RedirectResponse("/admin", status_code=303)