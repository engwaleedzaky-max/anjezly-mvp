# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Tuple, Optional

from models import ChatState
from menus import CATEGORIES_AR, SERVICES_AR, category_name, service_name
from utils import (
    CMD_BACK,
    CMD_RESTART,
    MIN_NAME,
    MIN_ADDRESS,
    MIN_DETAILS,
    normalize_text,
    validate_phone,
    wants_restart,
)
from storage import save_request_to_excel, save_provider_to_excel, save_request_to_neon, save_provider_to_neon
from notify import notify_new_request, notify_new_provider

# -------- Prompts --------

def prompt_role() -> str:
    return (
        "اختر نوع المستخدم بكتابة رقم:\n"
        "(1) طالب خدمة\n"
        "(2) مقدم خدمة\n\n"
        "استخدم زر (رجوع) أو (بدء من جديد)."
    )

def prompt_main_menu() -> str:
    lines = ["اختر القسم بكتابة رقم:"]
    for k in sorted(CATEGORIES_AR.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        lines.append(f"({k}) {CATEGORIES_AR[k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)

def prompt_sub_menu(cat_key: str) -> str:
    lines = ["اختر الخدمة بكتابة رقم:"]
    services = SERVICES_AR.get(cat_key, {"0": "أخرى"})
    for k in sorted(services.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        lines.append(f"({k}) {services[k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)

def prompt_provider_intro() -> str:
    return (
        "احجز موقعك مع فريق عمل أنجزلي.\n"
        "سجّل اسمك ورقمك ومهنتك.\n"
        "تقدر تضيف ايه للفريق؟\n"
        "تعرف تصنع ايه من بيتك؟\n\n"
    )

def prompt_for_step(state: ChatState, *, brand: str, slogan: str) -> str:
    # Header always
    header = f"{brand}\n{slogan}\n\n"
    if state.step == "role":
        return header + prompt_role()

    if state.step == "main_menu":
        return header + prompt_main_menu()

    if state.step == "sub_menu":
        return header + prompt_sub_menu(state.category_key)

    if state.step == "name":
        return header + "اكتب اسمك:"

    if state.step == "phone":
        return header + "اكتب رقم الهاتف (10 أرقام على الأقل):"

    if state.step == "address":
        return header + "اكتب العنوان / المنطقة:"

    if state.step == "details":
        return header + f"اكتب تفاصيل الطلب: ({state.service_name})"

    # provider flow
    if state.step == "p_name":
        return header + prompt_provider_intro() + "اكتب اسمك:"
    if state.step == "p_phone":
        return header + "اكتب رقم الهاتف (10 أرقام على الأقل):"
    if state.step == "p_profession":
        return header + "اكتب مهنتك:"
    if state.step == "p_contrib":
        return header + "تقدر تضيف ايه للفريق؟"
    if state.step == "p_home":
        return header + "تعرف تصنع ايه من بيتك؟"

    return header + prompt_role()

def should_show_chips(step: str) -> bool:
    # show number chips only for menu steps
    return step in {"role", "main_menu", "sub_menu"}

# -------- Bot core --------

def bot_reply(
    request_session: dict,
    user_text: str,
    *,
    brand: str,
    slogan: str,
) -> Tuple[str, bool]:
    text = normalize_text(user_text)

    raw_state = request_session.get("chat_state")
    state = ChatState.from_dict(raw_state) if isinstance(raw_state, dict) else ChatState()

    raw_hist = request_session.get("chat_history")
    history = [x for x in raw_hist if isinstance(x, dict)] if isinstance(raw_hist, list) else []

    def set_state(st: ChatState) -> None:
        request_session["chat_state"] = st.to_dict()

    def set_history(h: list[dict]) -> None:
        request_session["chat_history"] = h[-50:]

    def push_history(st: ChatState) -> None:
        history.append(st.to_dict())
        set_history(history)

    def pop_history() -> Optional[ChatState]:
        if not history:
            return None
        last = history.pop()
        set_history(history)
        return ChatState.from_dict(last)

    def restart() -> Tuple[str, bool]:
        request_session.pop("chat_state", None)
        request_session.pop("chat_history", None)
        st = ChatState(role=None, step="role")
        set_state(st)
        set_history([])
        return prompt_for_step(st, brand=brand, slogan=slogan), True

    def back_one_step() -> Tuple[str, bool]:
        prev = pop_history()
        if not prev:
            return "لا توجد خطوة سابقة.\n\n" + prompt_for_step(state, brand=brand, slogan=slogan), should_show_chips(state.step)
        set_state(prev)
        return "↩️ رجوع.\n\n" + prompt_for_step(prev, brand=brand, slogan=slogan), should_show_chips(prev.step)

    if text == CMD_BACK:
        return back_one_step()
    if text == CMD_RESTART or wants_restart(text):
        return restart()

    # -------- Step: role --------
    if state.step == "role":
        if text == "1":
            push_history(state)
            state.role = "customer"
            state.step = "main_menu"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), True
        if text == "2":
            push_history(state)
            state.role = "provider"
            state.step = "p_name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        return "اختيار غير صحيح.\n\n" + prompt_for_step(state, brand=brand, slogan=slogan), True

    # -------- Customer flow --------
    if state.role == "customer":
        if state.step == "main_menu":
            if text not in CATEGORIES_AR:
                return "اختيار غير صحيح.\n\n" + prompt_main_menu(), True
            push_history(state)
            state.category_key = text
            state.category_name = category_name(text)
            state.step = "sub_menu"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), True

        if state.step == "sub_menu":
            services = SERVICES_AR.get(state.category_key, {"0": "أخرى"})
            if text not in services:
                return "اختيار غير صحيح.\n\n" + prompt_sub_menu(state.category_key), True
            push_history(state)
            state.service_key = text
            state.service_name = service_name(state.category_key, text)
            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جدًا. اكتب اسمًا صحيحًا.", False
            push_history(state)
            state.name = text
            state.step = "phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الهاتف غير صحيح. اكتب 10 أرقام على الأقل.", False
            push_history(state)
            state.phone = phone
            state.step = "address"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "address":
            if len(text) < MIN_ADDRESS:
                return "العنوان قصير جدًا. اكتب العنوان/المنطقة.", False
            push_history(state)
            state.address = text
            state.step = "details"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "details":
            if not text.strip() or len(text.strip()) < MIN_DETAILS:
                return "اكتب تفاصيل أكثر (سطر واحد على الأقل).", False

            state.details = text.strip()

            # Save to Excel + Neon (best effort)
            save_request_to_excel(state)
            save_request_to_neon(state)

            # Notify (Telegram)
            notify_new_request(state)

            confirmation = (
                "✅ تم استلام طلبك بنجاح.\n\n"
                f"القسم: {state.category_name}\n"
                f"الخدمة: {state.service_name}\n"
                f"الاسم: {state.name}\n"
                f"الهاتف: {state.phone}\n"
                f"العنوان: {state.address}\n"
                f"التفاصيل: {state.details}\n\n"
            )
            msg, _ = restart()
            return confirmation + msg, True

        # fallback
        return restart()

    # -------- Provider flow --------
    if state.role == "provider":
        if state.step == "p_name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جدًا. اكتب اسمًا صحيحًا.", False
            push_history(state)
            state.p_name = text
            state.step = "p_phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الهاتف غير صحيح. اكتب 10 أرقام على الأقل.", False
            push_history(state)
            state.p_phone = phone
            state.step = "p_profession"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_profession":
            if len(text) < 2:
                return "اكتب مهنتك بشكل أوضح.", False
            push_history(state)
            state.p_profession = text
            state.step = "p_contrib"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_contrib":
            if len(text) < 2:
                return "اكتب إجابة مختصرة.", False
            push_history(state)
            state.p_contrib = text
            state.step = "p_home"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_home":
            if len(text) < 2:
                return "اكتب إجابة مختصرة.", False

            state.p_home = text

            save_provider_to_excel(state)
            save_provider_to_neon(state)
            notify_new_provider(state)

            confirmation = (
                "✅ تم تسجيل بياناتك كمقدم خدمة بنجاح.\n\n"
                f"الاسم: {state.p_name}\n"
                f"الهاتف: {state.p_phone}\n"
                f"المهنة: {state.p_profession}\n"
                f"تقدر تضيف: {state.p_contrib}\n"
                f"من البيت: {state.p_home}\n\n"
            )
            msg, _ = restart()
            return confirmation + msg, True

        return restart()

    return restart()
