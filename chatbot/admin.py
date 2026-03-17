# -*- coding: utf-8 -*-
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
import os

from config import ADMIN_PIN, REQUESTS_XLSX, PROVIDERS_XLSX
from storage import (
    neon_enabled,
    init_neon,
    list_last_requests_from_neon,
    list_last_providers_from_neon,
)

router = APIRouter()

def _is_admin(request: Request) -> bool:
    return request.session.get("is_admin") is True

@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, pin: str | None = None):
    # login via /admin?pin=4321 then session stays
    if not _is_admin(request):
        if pin and pin.strip() == ADMIN_PIN:
            request.session["is_admin"] = True
        else:
            return HTMLResponse(
                "<h2>لوحة الأدمن</h2><p>ادخل باللينك: <code>/admin?pin=PIN</code></p>",
                status_code=401,
            )

    neon_ok = init_neon()
    reqs = list_last_requests_from_neon(50)
    provs = list_last_providers_from_neon(50)

    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    rows_req = "\n".join(
        f"<tr><td>{esc(r['created_at'])}</td><td>{esc(r['category'])}</td><td>{esc(r['service'])}</td>"
        f"<td>{esc(r['name'])}</td><td>{esc(r['phone'])}</td><td>{esc(r['address'])}</td><td>{esc(r['details'])}</td></tr>"
        for r in reqs
    ) or "<tr><td colspan='7'>لا توجد بيانات بعد.</td></tr>"

    rows_prov = "\n".join(
        f"<tr><td>{esc(r['created_at'])}</td><td>{esc(r['name'])}</td><td>{esc(r['phone'])}</td>"
        f"<td>{esc(r['profession'])}</td><td>{esc(r['contrib'])}</td><td>{esc(r['home'])}</td></tr>"
        for r in provs
    ) or "<tr><td colspan='6'>لا توجد بيانات بعد.</td></tr>"

    req_exists = os.path.exists(REQUESTS_XLSX)
    prov_exists = os.path.exists(PROVIDERS_XLSX)

    html = f"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>لوحة الأدمن</title>
<style>
  body{{font-family:system-ui,Arial;margin:24px}}
  table{{border-collapse:collapse;width:100%}}
  th,td{{border:1px solid #e5e7eb;padding:8px;text-align:right;vertical-align:top}}
  th{{background:#f3f4f6}}
  .muted{{color:#6b7280}}
  .ok{{color:#16a34a;font-weight:800}}
  .bad{{color:#b00020;font-weight:800}}
  .card{{border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin:12px 0}}
  a{{color:#2563eb}}
</style>
</head><body>
<h1>لوحة الأدمن</h1>

<div class="card">
  <b>حالة Neon:</b>
  {"<span class='ok'>✅ متصل</span>" if neon_ok else "<span class='bad'>❌ غير متصل</span>"}
  <div class="muted">* يتم عرض آخر 50 طلب و آخر 50 تسجيل مقدم خدمة من Neon.</div>
</div>

<div class="card">
  <h2>آخر 50 طلب (Neon)</h2>
  <table>
    <thead><tr>
      <th>التاريخ</th><th>القسم</th><th>الخدمة</th><th>الاسم</th><th>الهاتف</th><th>العنوان</th><th>التفاصيل</th>
    </tr></thead>
    <tbody>{rows_req}</tbody>
  </table>
</div>

<div class="card">
  <h2>آخر 50 تسجيل مقدم خدمة (Neon)</h2>
  <table>
    <thead><tr>
      <th>التاريخ</th><th>الاسم</th><th>الهاتف</th><th>المهنة</th><th>تقدر تضيف</th><th>من البيت</th>
    </tr></thead>
    <tbody>{rows_prov}</tbody>
  </table>
</div>

<div class="card">
  <h2>ملفات Excel (قد تُحذف على Render المجاني)</h2>
  <p>طلبات طالبي الخدمة: {"✅ موجود" if req_exists else "❌ غير موجود"}<br/>
     {f"<a href='/admin/download/requests'>تحميل requests.xlsx</a>" if req_exists else ""}</p>
  <p>بيانات مقدمي الخدمة: {"✅ موجود" if prov_exists else "❌ غير موجود"}<br/>
     {f"<a href='/admin/download/providers'>تحميل providers.xlsx</a>" if prov_exists else ""}</p>
</div>

</body></html>"""
    return HTMLResponse(html)

@router.get("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse("/", status_code=303)

@router.get("/admin/download/requests")
def dl_requests(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not os.path.exists(REQUESTS_XLSX):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(REQUESTS_XLSX, filename="requests.xlsx")

@router.get("/admin/download/providers")
def dl_providers(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not os.path.exists(PROVIDERS_XLSX):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(PROVIDERS_XLSX, filename="providers.xlsx")
