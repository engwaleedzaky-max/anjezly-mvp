# file: bot.py
from __future__ import annotations

from typing import Optional, Tuple

from config import CMD_BACK, CMD_RESTART
from menus import menu_for_ar
from models import ChatState
from notify import notify_new_provider, notify_new_request
from storage import save_provider_to_excel, save_request_to_excel

MIN_NAME = 2
MIN_ADDRESS = 4
MIN_DETAILS = 3  # نسمح بنص قصير بالعربي


def normalize_text(s: str) -> str:
    return (s or "").strip()


def validate_phone(s: str) -> Optional[str]:
    s = normalize_text(s)
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 10:
        return None
    return digits


def wants_restart(text: str) -> bool:
    t = normalize_text(text)
    return t in {"ابدأ من جديد", "بدء من جديد", "بدء جديد", "بداية جديدة", "#", "restart", "start over"}


def should_show_chips(step: str) -> bool:
    return step in {"role", "main_menu", "sub_menu"}


def prompt_role() -> str:
    return (
        "اختر نوع المستخدم بكتابة رقم:\n"
        "(1) طالب خدمة\n"
        "(2) مقدم خدمة\n"
    )


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
    if t == "1":
        return "customer"
    if t == "2":
        return "provider"
    return None


def choose_category(text: str) -> Optional[str]:
    t = normalize_text(text)
    main, _ = menu_for_ar()
    return t if t in main else None


def choose_service(category_key: str, text: str) -> Optional[str]:
    t = normalize_text(text)
    _, sub = menu_for_ar()
    services = sub.get(category_key, {})
    return t if t in services else None


def prompt_for_step(state: ChatState, *, brand: str, slogan: str) -> str:
    """
    IMPORTANT:
    main.py calls this with (brand=..., slogan=...).
    Keep this signature in sync with main.py. :contentReference[oaicite:2]{index=2}
    """
    # شاشة البداية
    if state.step == "role" or not state.role:
        return f"{brand}\n{slogan}\n\n{prompt_role()}"

    # طالب خدمة
    if state.role == "customer":
        if state.step == "main_menu":
            return prompt_main_menu()
        if state.step == "sub_menu":
            return prompt_sub_menu(state.category_key or "")

        if state.step == "custom_category":
            return "اكتب اسم القسم (أخرى):"
        if state.step == "custom_service":
            return "اكتب اسم الخدمة المطلوبة (أخرى):"

        if state.step == "name":
            return "اكتب اسمك:"
        if state.step == "phone":
            return "اكتب رقم الهاتف:"
        if state.step == "address":
            return "اكتب العنوان / المنطقة:"
        if state.step == "details":
            svc = state.service_name or "الخدمة"
            return f"اكتب تفاصيل الطلب: ({svc})"

    # مقدم خدمة
    if state.role == "provider":
        if state.step == "p_name":
            return (
                "احجز موقعك مع فريق عمل أنجزلي.\n"
                "سجل اسمك ورقمك ومهنتك.\n\n"
                "اكتب اسمك:"
            )
        if state.step == "p_phone":
            return "اكتب رقم الموبايل:"
        if state.step == "p_profession":
            return "ما مهنتك/تخصصك؟"
        if state.step == "p_contrib":
            return "تقدر تضيف ايه للفريق؟"
        if state.step == "p_home":
            return "تعرف تصنع ايه من بيتك؟"

    return f"{brand}\n{slogan}\n\n{prompt_role()}"


def bot_reply(request_session: dict, user_text: str, *, brand: str, slogan: str) -> Tuple[str, bool]:
    text = normalize_text(user_text)

    raw_state = request_session.get("chat_state")
    state = ChatState.from_dict(raw_state) if isinstance(raw_state, dict) else ChatState()

    raw_hist = request_session.get("chat_history")
    history = [x for x in raw_hist if isinstance(x, dict)] if isinstance(raw_hist, list) else []

    def set_state(st: ChatState) -> None:
        request_session["chat_state"] = st.to_dict()

    def set_history(hist: list[dict]) -> None:
        request_session["chat_history"] = hist[-40:]

    def clear_chat() -> None:
        request_session.pop("chat_state", None)
        request_session.pop("chat_history", None)

    def push_history(st: ChatState) -> None:
        history.append(st.to_dict())
        set_history(history)

    def pop_history() -> Optional[ChatState]:
        if not history:
            return None
        last = history.pop()
        set_history(history)
        return ChatState.from_dict(last)

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
                "لا توجد خطوة سابقة.\n\n"
                + prompt_for_step(state, brand=brand, slogan=slogan),
                should_show_chips(state.step),
            )
        set_state(prev)
        return (
            "↩️ رجوع.\n\n" + prompt_for_step(prev, brand=brand, slogan=slogan),
            should_show_chips(prev.step),
        )

    # Commands
    if text == CMD_BACK:
        return back_one_step()
    if text == CMD_RESTART or wants_restart(text):
        return restart_to_role()

    # Init
    if not state.step:
        state.step = "role"
    if not state.role:
        state.step = "role"

    # Step: role
    if state.step == "role":
        chosen = choose_role(text)
        if not chosen:
            msg = "اختيار غير صحيح.\n\n" + prompt_for_step(state, brand=brand, slogan=slogan)
            return msg, True

        push_history(state)
        state.role = chosen
        state.step = "main_menu" if chosen == "customer" else "p_name"
        set_state(state)
        return prompt_for_step(state, brand=brand, slogan=slogan), should_show_chips(state.step)

    # Customer flow
    if state.role == "customer":
        if state.step == "main_menu":
            cat_key = choose_category(text)
            if not cat_key:
                return "اختيار غير صحيح.\n\n" + prompt_main_menu(), True

            push_history(state)
            main, _ = menu_for_ar()
            state.category_key = cat_key
            state.category_name = main.get(cat_key, "أخرى")

            if state.category_name == "أخرى":
                state.step = "custom_category"
                set_state(state)
                return prompt_for_step(state, brand=brand, slogan=slogan), False

            state.step = "sub_menu"
            set_state(state)
            return prompt_sub_menu(cat_key), True

        if state.step == "custom_category":
            if len(text) < 2:
                return "اكتب اسم قسم صحيح.", False
            push_history(state)
            state.category_name = text
            state.category_key = "0"
            state.step = "custom_service"
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

            if state.service_name == "أخرى":
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
            state.service_name = text
            state.service_key = "0"
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
                return "رقم الهاتف غير صحيح.", False
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
            if not text.strip() or len(text) < MIN_DETAILS:
                return "اكتب تفاصيل أكثر قليلاً.", False

            state.details = text
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

    # Provider flow
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
                return "رقم الموبايل غير صحيح.", False
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

            save_provider_to_excel(state)
            notify_new_provider(state)

            confirmation = (
                "✅ تم تسجيل بياناتك كمقدم خدمة.\n\n"
                f"الاسم: {state.p_name}\n"
                f"الموبايل: {state.p_phone}\n"
                f"المهنة: {state.p_profession}\n"
                f"إضافة للفريق: {state.p_contrib}\n"
                f"تصنع من البيت: {state.p_home}\n\n"
            )
            msg, _ = restart_to_role()
            return confirmation + msg, True

        return restart_to_role()

    return restart_to_role()