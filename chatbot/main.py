# -*- coding: utf-8 -*-
from __future__ import annotations
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from config import BRAND_AR, SLOGAN_AR, SESSION_SECRET
from models import ChatState
from bot import bot_reply, prompt_for_step, should_show_chips
from admin import router as admin_router
from storage import init_neon

app = FastAPI(title=BRAND_AR)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET if SESSION_SECRET else secrets.token_urlsafe(32),
    same_site="lax",
)

app.include_router(admin_router)

@app.on_event("startup")
def _startup() -> None:
    # Best effort: create Neon tables if DATABASE_URL provided
    init_neon()

@app.get("/", response_class=HTMLResponse)
def chat_page(request: Request):
    raw_state = request.session.get("chat_state")
    state = ChatState.from_dict(raw_state) if isinstance(raw_state, dict) else ChatState(role=None, step="role")
    initial = prompt_for_step(state, brand=BRAND_AR, slogan=SLOGAN_AR)
    from ui import render_chat_page
    return HTMLResponse(render_chat_page(initial))

@app.post("/api/message")
async def api_message(request: Request):
    data = await request.json()
    text = (data.get("text") or "").strip()
    reply, show_chips = bot_reply(request.session, text, brand=BRAND_AR, slogan=SLOGAN_AR)
    return JSONResponse({"reply": reply, "show_chips": bool(show_chips)})
