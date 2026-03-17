# file: admin.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from config import ADMIN_PIN, BRAND_AR, PROVIDERS_XLSX, REQUESTS_XLSX
from db import db_enabled, last_requests_db

router = APIRouter()


def _esc(s: object) -> str:
    t = "" if s is None else str(s)
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _trunc(s: object, n: int = 80) -> str:
    t = "" if s is None else str(s)
    return (t[: n - 1] + "…") if len(t) > n else t


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

    rows = last_requests_db(50) if db_enabled() else []
    db_status = "✅ متصل" if db_enabled() else "❌ غير متصل (DATABASE_URL غير مضبوط)"

    if not rows:
        table_html = "<p>لا توجد طلبات على Neon بعد (أو Neon غير متصل).</p>"
    else:
        headers = ["التاريخ", "القسم", "الخدمة", "الاسم", "الهاتف", "العنوان", "التفاصيل"]
        th = "".join(
            f"<th style='padding:10px;border-bottom:1px solid #eee;background:#f8fafc;text-align:right;'>{h}</th>"
            for h in headers
        )
        tr_list = []
        for r in rows:
            tr_list.append(
                "<tr>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(r['created_at'])}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(r['category_name'])}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(r['service_name'])}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(r['name'])}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(r['phone'])}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(_trunc(r['address'], 60))}</td>"
                + f"<td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top;'>{_esc(_trunc(r['details'], 70))}</td>"
                + "</tr>"
            )

        table_html = f"""
        <div style="overflow:auto;border:1px solid #eee;border-radius:12px;">
          <table style="border-collapse:collapse;width:100%;min-width:1000px;">
            <thead><tr>{th}</tr></thead>
            <tbody>{''.join(tr_list)}</tbody>
          </table>
        </div>
        <p style="color:#6b7280;font-size:12px;">* عرض آخر 50 طلب من Neon (الأحدث أولاً). العنوان/التفاصيل قد تُعرض مختصرة.</p>
        """

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{BRAND_AR} | لوحة الأدمن</title></head>
<body style="font-family:system-ui,Arial; padding:24px;">
<h2>لوحة الأدمن</h2>
<p><a href="/">رجوع للشات</a></p>

<h3>حالة Neon</h3>
<p>{db_status}</p>

<hr style="margin:18px 0;"/>

<h3>آخر 50 طلب (Neon)</h3>
{table_html}

<hr style="margin:18px 0;"/>

<h3>ملفات Excel (قد تُحذف على Render المجاني)</h3>
<p>طلبات طالبي الخدمة: {"✅ موجود" if req_exists else "❌ لا يوجد بعد"}</p>
{"<a href='/admin/download/requests'>⬇️ تحميل requests.xlsx</a>" if req_exists else ""}
<p style="margin-top:10px;">بيانات مقدمي الخدمة: {"✅ موجود" if prov_exists else "❌ لا يوجد بعد"}</p>
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