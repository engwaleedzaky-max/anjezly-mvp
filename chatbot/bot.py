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

    raw_hist = request_session.get("chat_history")
    history = [x for x in raw_hist if isinstance(x, dict)] if isinstance(raw_hist, list) else []

    def set_state(st: ChatState) -> None:
        request_session["chat_state"] = st.to_dict()

    def set_history(hist: list[dict]) -> None:
        request_session["chat_history"] = hist[-HIST_MAX:]

    def clear_chat() -> None:
        request_session.pop("chat_state", None)
        request_session.pop("chat_history", None)

    def push_history(st: ChatState) -> None:
        history.append(_snapshot(st))
        set_history(history)

    def pop_history() -> Optional[ChatState]:
        if not history:
            return None
        last = history.pop()
        set_history(history)
        return _state_from_snapshot(last)

    def restart_to_role() -> Tuple[str, bool]:
        clear_chat()
        st = ChatState(role=None, step="role")
        set_state(st)
        set_history([])
        return prompt_for_step(st, brand=brand, slogan=slogan), True

    def back_one_step() -> Tuple[str, bool]:
        prev = pop_history()
        if not prev:
            return (
                "لا توجد خطوة سابقة.\n\n" + prompt_for_step(state, brand=brand, slogan=slogan),
                should_show_chips(state.step),
            )
        set_state(prev)
        return (
            "↩️ رجوع.\n\n" + prompt_for_step(prev, brand=brand, slogan=slogan),
            should_show_chips(prev.step),
        )

    if text == CMD_BACK:
        return back_one_step()
    if text == CMD_RESTART or wants_restart(text):
        return restart_to_role()

    if not state.step or not state.role:
        state.step = "role"

    # role
    if state.step == "role":
        chosen = choose_role(text)
        if not chosen:
            return "اختيار غير صحيح.\n\n" + prompt_for_step(state, brand=brand, slogan=slogan), True

        push_history(state)
        state.role = chosen
        state.step = "main_menu" if chosen == "customer" else "p_name"
        set_state(state)
        return prompt_for_step(state, brand=brand, slogan=slogan), should_show_chips(state.step)

    # customer
    if state.role == "customer":
        if state.step == "main_menu":
            cat_key = choose_category(text)
            if not cat_key:
                return "اختيار غير صحيح.\n\n" + prompt_main_menu(), True

            push_history(state)
            main, _ = menu_for_ar()
            state.category_key = cat_key
            state.category_name = main.get(cat_key, "أخرى")

            if cat_key == "0":
                state.step = "custom_cat_service"
                set_state(state)
                return prompt_for_step(state, brand=brand, slogan=slogan), False

            state.step = "sub_menu"
            set_state(state)
            return prompt_sub_menu(cat_key), True

        if state.step == "custom_cat_service":
            parsed = _parse_cat_service_one_line(text)
            push_history(state)

            if parsed:
                cat, svc = parsed
                state.category_name = cat
                state.service_name = svc
            else:
                if len(text) < 2:
                    return "اكتب اسم خدمة صحيح أو اكتبها: قسم / خدمة", False
                state.category_name = "أخرى"
                state.service_name = text

            state.category_key = "0"
            state.service_key = "0"
            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "sub_menu":
            svc_key = choose_service(state.category_key or "", text)
            if not svc_key:
                return "اختيار غير صحيح.\n\n" + prompt_sub_menu(state.category_key or ""), True

            push_history(state)
            _, sub = menu_for_ar()
            state.service_key = svc_key
            state.service_name = sub.get(state.category_key or "", {}).get(svc_key, "أخرى")

            if svc_key == "0":
                state.step = "custom_service"
                set_state(state)
                return prompt_for_step(state, brand=brand, slogan=slogan), False

            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "custom_service":
            if len(text) < 2:
                return "اكتب اسم خدمة صحيح.", False
            push_history(state)
            state.service_key = "0"
            state.service_name = text
            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جداً.", False
            push_history(state)
            state.name = text
            state.step = "phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الهاتف غير صحيح (لازم 10 أرقام على الأقل).", False
            push_history(state)
            state.phone = phone
            state.step = "address"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "address":
            if len(text) < MIN_ADDRESS:
                return "العنوان قصير جداً.", False
            push_history(state)
            state.address = text
            state.step = "details"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "details":
            if not text.strip() or len(text.strip()) < MIN_DETAILS:
                return "اكتب أي تفاصيل (حتى لو قصيرة).", False

            state.details = text

            # ✅ حفظ/تنبيه (قد يأخذ وقت - عندك UI انتظار الآن)
            # حفظ في Neon
            insert_request({
                  "category_name": state.category_name,
                  "service_name": state.service_name,
                  "customer_name": state.name,
                  "customer_phone": state.phone,
                  "address": state.address,
                  "details": state.details,
                  "source": "web_chat"
             })

            # حفظ في Excel (اختياري احتياطي)
            save_request_to_excel(state)

            notify_new_request(state)

            confirmation = (
                "✅ تم حفظ طلبك بنجاح.\n\n"
                f"القسم: {state.category_name}\n"
                f"الخدمة: {state.service_name}\n"
                f"الاسم: {state.name}\n"
                f"الهاتف: {state.phone}\n"
                f"العنوان: {state.address}\n"
                f"التفاصيل: {state.details}\n\n"
            )
            msg, _ = restart_to_role()
            return confirmation + msg, True

        return restart_to_role()

    # provider
    if state.role == "provider":
        if state.step == "p_name":
            if len(text) < MIN_NAME:
                return "الاسم قصير جداً.", False
            push_history(state)
            state.p_name = text
            state.step = "p_phone"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_phone":
            phone = validate_phone(text)
            if not phone:
                return "رقم الموبايل غير صحيح (لازم 10 أرقام على الأقل).", False
            push_history(state)
            state.p_phone = phone
            state.step = "p_profession"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_profession":
            if len(text) < 2:
                return "اكتب مهنة/تخصص صحيح.", False
            push_history(state)
            state.p_profession = text
            state.step = "p_contrib"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_contrib":
            if len(text) < 2:
                return "اكتب إجابة واضحة.", False
            push_history(state)
            state.p_contrib = text
            state.step = "p_home"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "p_home":
            if len(text) < 2:
                return "اكتب إجابة واضحة.", False
            state.p_home = text

            # حفظ في Neon
            insert_request({
                 "category_name": state.category_name,
                 "service_name": state.service_name,
                 "customer_name": state.name,
                 "customer_phone": state.phone,
                 "address": state.address,
                 "details": state.details,
                 "source": "web_chat"
            })

           # حفظ في Excel (اختياري احتياطي)
            save_request_to_excel(state)

            notify_new_request(state)

            confirmation = (
                "✅ تم تسجيل بياناتك كمقدم خدمة.\n\n"
                f"الاسم: {state.p_name}\n"
                f"الموبايل: {state.p_phone}\n"
                f"المهنة: {state.p_profession}\n"
                f"إضافة للفريق: {state.p_contrib}\n"
                f"تصنع ايه من البيت: {state.p_home}\n\n"
            )
            msg, _ = restart_to_role()
            return confirmation + msg, True

        return restart_to_role()

    return restart_to_role()
