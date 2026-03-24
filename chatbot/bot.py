# file: bot.py
from __future__ import annotations

import re
from typing import Optional, Tuple
from db import insert_request, insert_provider
from config import CMD_BACK, CMD_RESTART
from menus import menu_for_ar
from models import ChatState
from notify import notify_new_provider, notify_new_request
from storage import save_provider_to_excel, save_request_to_excel

MIN_NAME = 2
MIN_ADDRESS = 4
MIN_DETAILS = 1  # أي نص غير فارغ


def normalize_text(s: str) -> str:
    return (s or "").strip()


def validate_phone(s: str) -> Optional[str]:
    s = normalize_text(s)
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits if len(digits) >= 10 else None


def wants_restart(text: str) -> bool:
    t = normalize_text(text)
    return t in {"ابدأ من جديد", "بدء من جديد", "بدء جديد", "بداية جديدة", "#", "restart", "start over"}


def should_show_chips(step: str) -> bool:
    return step in {"role", "main_menu", "sub_menu"}


def prompt_role() -> str:
    return "اختر نوع المستخدم بكتابة رقم:\n(1) طالب خدمة\n(2) مقدم خدمة\n"


def prompt_main_menu() -> str:
    main, _ = menu_for_ar()
    lines = ["اختر القسم بكتابة رقم:"]
    for k in [str(i) for i in range(1, 10)] + ["0"]:
        if k in main:
            lines.append(f"({k}) {main[k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)


def prompt_sub_menu(category_key: str) -> str:
    _, sub = menu_for_ar()
    services = sub.get(category_key, {})
    lines = ["اختر الخدمة بكتابة رقم:"]
    for k in [str(i) for i in range(1, 10)] + ["0"]:
        if k in services:
            lines.append(f"({k}) {services[k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)


def choose_role(text: str) -> Optional[str]:
    t = normalize_text(text)
    return "customer" if t == "1" else "provider" if t == "2" else None


def choose_category(text: str) -> Optional[str]:
    t = normalize_text(text)
    main, _ = menu_for_ar()
    return t if t in main else None


def choose_service(category_key: str, text: str) -> Optional[str]:
    t = normalize_text(text)
    _, sub = menu_for_ar()
    return t if t in sub.get(category_key, {}) else None


def _parse_cat_service_one_line(text: str) -> Optional[tuple[str, str]]:
    t = normalize_text(text)
    if not t:
        return None
    parts = re.split(r"\s*[/\-:]\s*", t, maxsplit=1)
    if len(parts) != 2:
        return None
    cat = normalize_text(parts[0])
    svc = normalize_text(parts[1])
    if len(cat) < 2 or len(svc) < 2:
        return None
    return cat, svc


def prompt_for_step(state: ChatState, *, brand: str, slogan: str) -> str:
    if state.step == "role" or not state.role:
        return f"{brand}\n{slogan}\n\n{prompt_role()}"

    if state.role == "customer":
        if state.step == "main_menu":
            return prompt_main_menu()
        if state.step == "sub_menu":
            return prompt_sub_menu(state.category_key or "")

        if state.step == "custom_cat_service":
            return "اكتب: اسم القسم / اسم الخدمة (مثال: خدمات قانونية / استشارة عقد)\n(أو اكتب اسم الخدمة فقط)"

        if state.step == "custom_service":
            return "اكتب اسم الخدمة المطلوبة (أخرى):"

        if state.step == "name":
            return "اكتب اسمك:"
        if state.step == "phone":
            return "اكتب رقم الهاتف (10 أرقام على الأقل):"
        if state.step == "address":
            return "اكتب العنوان / المنطقة:"
        if state.step == "details":
            svc = state.service_name or "الخدمة"
            return f"اكتب تفاصيل الطلب: ({svc})"

    if state.role == "provider":
        if state.step == "p_name":
            return (
                "احجز موقعك مع فريق عمل أنجزلي.\n"
                "سجل اسمك ورقمك ومهنتك.\n\n"
                "اكتب اسمك:"
            )
        if state.step == "p_phone":
            return "اكتب رقم الموبايل (10 أرقام على الأقل):"
        if state.step == "p_profession":
            return "ما مهنتك/تخصصك؟"
        if state.step == "p_contrib":
            return "تقدر تضيف ايه للفريق؟"
        if state.step == "p_home":
            return "تعرف تصنع ايه من بيتك؟"

    return f"{brand}\n{slogan}\n\n{prompt_role()}"


# ---------- FIX: small history snapshots (cookie safe) ----------
HIST_MAX = 10


def _snapshot(st: ChatState) -> dict:
    # snapshot خفيف جداً لتفادي تضخم الكوكي
    return {
        "role": st.role,
        "step": st.step,
        "category_key": st.category_key,
        "category_name": st.category_name,
        "service_key": st.service_key,
        "service_name": st.service_name,
        "name": st.name,
        "phone": st.phone,
        # لا نخزن address/details/p_* في history لأنها تكبر
    }


def _state_from_snapshot(s: dict) -> ChatState:
    st = ChatState()
    for k, v in s.items():
        if hasattr(st, k):
            setattr(st, k, v)
    return st


def bot_reply(request_session: dict, user_text: str, *, brand: str, slogan: str) -> Tuple[str, bool]:
    text = normalize_text(user_text)

    raw_state = request_session.get("chat_state")
    state = ChatState.from_dict(raw_state) if isinstance(raw_state, dict) else ChatState()

    def set_state(st: ChatState) -> None:
        request_session["chat_state"] = st.to_dict()

    def clear_chat() -> None:
        request_session.pop("chat_state", None)

    def restart_to_role() -> Tuple[str, bool]:
        clear_chat()
        st = ChatState(role=None, step="role")
        set_state(st)
        return prompt_for_step(st, brand=brand, slogan=slogan), True

    if not state.step:
        state.step = "role"

    # ================= ROLE =================
    if state.step == "role":
        chosen = choose_role(text)
        if not chosen:
            return prompt_for_step(state, brand=brand, slogan=slogan), True

        state.role = chosen
        state.step = "main_menu" if chosen == "customer" else "p_name"
        set_state(state)
        return prompt_for_step(state, brand=brand, slogan=slogan), True

    # ================= CUSTOMER =================
    if state.role == "customer":

        if state.step == "main_menu":
            cat_key = choose_category(text)
            if not cat_key:
                return prompt_main_menu(), True

            main, _ = menu_for_ar()
            state.category_key = cat_key
            state.category_name = main.get(cat_key, "أخرى")
            state.step = "sub_menu"
            set_state(state)
            return prompt_sub_menu(cat_key), True

        if state.step == "sub_menu":
            svc_key = choose_service(state.category_key or "", text)
            if not svc_key:
                return prompt_sub_menu(state.category_key or ""), True

            _, sub = menu_for_ar()
            state.service_key = svc_key
            state.service_name = sub.get(state.category_key or "", {}).get(svc_key, "أخرى")
            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جداً.", False
            state.name = text
            state.step = "phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الهاتف غير صحيح.", False
            state.phone = phone
            state.step = "address"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "address":
            state.address = text
            state.step = "details"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "details":
            state.details = text

            insert_request({
                "category_name": state.category_name,
                "service_name": state.service_name,
                "customer_name": state.name,
                "customer_phone": state.phone,
                "address": state.address,
                "details": state.details,
                "source": "web_chat"
            })

            save_request_to_excel(state)
            notify_new_request(state)

            msg = "✅ تم حفظ طلبك بنجاح.\n\n"
            next_msg, _ = restart_to_role()
            return msg + next_msg, True

    # ================= PROVIDER =================
    if state.role == "provider":

        if state.step == "p_name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جداً.", False
            state.p_name = text
            state.step = "p_phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الموبايل غير صحيح.", False
            state.p_phone = phone
            state.step = "p_profession"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_profession":
            state.p_profession = text
            state.step = "p_contrib"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_contrib":
            state.p_contrib = text
            state.step = "p_home"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_home":
            state.p_home = text

            insert_provider({
                "provider_name": state.p_name,
                "provider_phone": state.p_phone,
                "profession": state.p_profession,
                "contrib": state.p_contrib,
                "home_make": state.p_home,
                "source": "web_chat"
            })

            save_provider_to_excel(state)
            notify_new_provider(state)

            msg = "✅ تم تسجيل بياناتك كمقدم خدمة.\n\n"
            next_msg, _ = restart_to_role()
            return msg + next_msg, True

    return restart_to_role()