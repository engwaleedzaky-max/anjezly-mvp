# file: main.py
from __future__ import annotations

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from admin import router as admin_router
from bot import bot_reply, prompt_for_step
from config import BRAND_AR, SESSION_SECRET, SLOGAN_AR
from db import init_db
from models import ChatState
from ui import render_page

app = FastAPI(title=BRAND_AR)  # ✅ لازم قبل أي @app.*
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
app.include_router(admin_router)


@app.head("/")
def healthcheck_head() -> Response:
    return Response(status_code=200)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def chat_page(request: Request) -> str:
    if not isinstance(request.session.get("chat_state"), dict):
        st = ChatState(role=None, step="role")
        request.session["chat_state"] = st.to_dict()
        request.session["chat_history"] = []

    state = ChatState.from_dict(request.session["chat_state"])
    initial = prompt_for_step(state, BRAND_AR, SLOGAN_AR)

    admin_ok = request.session.get("admin_ok") is True
    return render_page(
        title=BRAND_AR,
        brand=BRAND_AR,
        slogan=SLOGAN_AR,
        initial_text=initial,
        admin_ok=admin_ok,
    )


@app.post("/api/message")
def api_message(request: Request, text: str = Form(...)) -> JSONResponse:
    reply, show_chips = bot_reply(
        request.session,
        text,
        brand=BRAND_AR,
        slogan=SLOGAN_AR,
    )
    return JSONResponse({"reply": reply, "show_chips": show_chips})