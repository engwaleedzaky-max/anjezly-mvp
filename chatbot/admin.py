# file: admin.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from config import ADMIN_PIN, BRAND_AR, PROVIDERS_XLSX, REQUESTS_XLSX

router = APIRouter()


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

    req_exists = REQUESTS_XLSX.exists()
    prov_exists = PROVIDERS_XLSX.exists()

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{BRAND_AR} | لوحة الأدمن</title></head>
<body style="font-family:system-ui,Arial; padding:24px;">
<h2>لوحة الأدمن</h2>
<p><a href="/">رجوع للشات</a></p>

<h3>طلبات طالبي الخدمة</h3>
<p>الحالة: {"✅ موجود" if req_exists else "❌ لا يوجد بعد"}</p>
{"<a href='/admin/download/requests'>⬇️ تحميل requests.xlsx</a>" if req_exists else ""}

<hr style="margin:18px 0;"/>

<h3>بيانات مقدمي الخدمة</h3>
<p>الحالة: {"✅ موجود" if prov_exists else "❌ لا يوجد بعد"}</p>
{"<a href='/admin/download/providers'>⬇️ تحميل providers.xlsx</a>" if prov_exists else ""}

</body></html>"""


@router.get("/admin/download/{which}")
def admin_download(request: Request, which: str) -> Response:
    if request.session.get("admin_ok") is not True:
        return RedirectResponse("/admin", status_code=303)

    if which == "requests":
        if not REQUESTS_XLSX.exists():
            return RedirectResponse("/admin", status_code=303)
        return FileResponse(str(REQUESTS_XLSX), filename="requests.xlsx")

    if which == "providers":
        if not PROVIDERS_XLSX.exists():
            return RedirectResponse("/admin", status_code=303)
        return FileResponse(str(PROVIDERS_XLSX), filename="providers.xlsx")

    return RedirectResponse("/admin", status_code=303)