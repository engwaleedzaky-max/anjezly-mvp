# file: bot.py
from __future__ import annotations

from typing import Optional, Tuple

from config import CMD_BACK, CMD_RESTART, MIN_ADDRESS, MIN_NAME
from menus import menu_ar
from models import ChatState
from notify import notify_new_provider, notify_new_request
from storage import save_provider_to_excel, save_request_to_excel

TXT: dict[str, str] = {
    "brand": "أنجزلي",
    "slogan": "اطلبها، وإحنا ننجزها",
    "invalid_choice": "اختيار غير صحيح. اكتب رقم صحيح من القائمة.",
    "role_title": "اختر نوع المستخدم بكتابة رقم:",
    "role_customer": "1) طالب خدمة",
    "role_provider": "2) مقدم خدمة",
    "enter_name": "اكتب الاسم:",
    "enter_phone": "اكتب رقم الهاتف:",
    "enter_address": "اكتب العنوان / المنطقة:",
    "enter_details": "اكتب تفاصيل الطلب:",
    "too_short_name": "الاسم قصير جدًا. اكتب اسمًا صحيحًا.",
    "phone_invalid": "رقم الهاتف غير صحيح. اكتب رقمًا يحتوي أرقام فقط (مثال: 01123456789).",
    "too_short_addr": "العنوان قصير جدًا. اكتب عنوانًا أو منطقة أو شارع.",
    "details_empty": "من فضلك اكتب تفاصيل الطلب (لا تتركه فارغًا).",
    "provider_intro": "احجز موقعك مع فريق عمل أنجزلي.",
    "provider_saved": "✅ تم تسجيل بياناتك كمقدم خدمة بنجاح!",
    "provider_profession": "سجل مهنتك:",
    "provider_contrib": "تقدر تضيف ايه للفريق؟",
    "provider_home": "تعرف تصنع ايه من بيتك؟ (اكتب إجابتك أو اكتب: لا يوجد)",
    "saved_ok": "✅ تم حفظ الطلب بنجاح!",
    "back_msg": "↩️ رجوع خطوة.",
    "restart_msg": "🔄 بدء من جديد.",
}


def normalize_text(s: str) -> str:
    return (s or "").strip()


def validate_phone(s: str) -> Optional[str]:
    digits = "".join(ch for ch in (s or "").strip() if ch.isdigit())
    if 7 <= len(digits) <= 15:
        return digits
    return None


def should_show_chips(step: str) -> bool:
    return step in ("role", "main_menu", "sub_menu")


def prompt_role() -> str:
    return "\n".join([TXT["role_title"], TXT["role_customer"], TXT["role_provider"]])


def prompt_main_menu() -> str:
    main, _ = menu_ar()
    lines = ["اختر القسم بكتابة رقم:"]
    for k in sorted(main.keys(), key=int):
        lines.append(f"{k}) {main[k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)


def prompt_sub_menu(cat_key: str) -> str:
    _, sub = menu_ar()
    lines = ["اختر الخدمة بكتابة رقم:"]
    for k in sorted(sub[cat_key].keys(), key=int):
        lines.append(f"{k}) {sub[cat_key][k]}")
    lines.append("\nاستخدم زر (رجوع) أو (بدء من جديد).")
    return "\n".join(lines)


def prompt_for_step(state: ChatState, *, brand: str, slogan: str) -> str:
    if state.step == "role":
        return f"{brand}\n{slogan}\n\n{prompt_role()}"

    if state.role == "customer":
        if state.step == "main_menu":
            return prompt_main_menu()
        if state.step == "sub_menu":
            return prompt_sub_menu(state.category_key)
        if state.step == "name":
            return TXT["enter_name"]
        if state.step == "phone":
            return TXT["enter_phone"]
        if state.step == "address":
            return TXT["enter_address"]
        if state.step == "details":
            return f"{TXT['enter_details']} ({state.service_name})"

    if state.role == "provider":
        if state.step == "p_name":
            return f"{TXT['provider_intro']}\n{TXT['enter_name']}"
        if state.step == "p_phone":
            return TXT["enter_phone"]
        if state.step == "p_profession":
            return TXT["provider_profession"]
        if state.step == "p_contrib":
            return TXT["provider_contrib"]
        if state.step == "p_home":
            return TXT["provider_home"]

    return f"{brand}\n{slogan}\n\n{prompt_role()}"


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

    def set_history(hist: list[dict]) -> None:
        request_session["chat_history"] = hist[-30:]

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
        request_session["chat_state"] = ChatState(role=None, step="role").to_dict()
        request_session["chat_history"] = []
        msg = TXT["restart_msg"] + "\n\n" + prompt_for_step(ChatState(role=None, step="role"), brand=brand, slogan=slogan)
        return msg, True

    def back_one_step() -> Tuple[str, bool]:
        prev = pop_history()
        if not prev:
            cur = ChatState.from_dict(request_session.get("chat_state") or {})
            return "لا توجد خطوة سابقة.\n\n" + prompt_for_step(cur, brand=brand, slogan=slogan), should_show_chips(cur.step)
        set_state(prev)
        return TXT["back_msg"] + "\n\n" + prompt_for_step(prev, brand=brand, slogan=slogan), should_show_chips(prev.step)

    if text == CMD_BACK:
        return back_one_step()
    if text == CMD_RESTART:
        return restart_to_role()

    # role step
    if state.step == "role" or state.role is None:
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
        return TXT["invalid_choice"] + "\n\n" + prompt_for_step(ChatState(role=None, step="role"), brand=brand, slogan=slogan), True

    # customer flow
    if state.role == "customer":
        if state.step == "main_menu":
            main, _ = menu_ar()
            if text not in main:
                return TXT["invalid_choice"] + "\n\n" + prompt_main_menu(), True
            push_history(state)
            state.category_key = text
            state.category_name = main[text]
            state.step = "sub_menu"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), True

        if state.step == "sub_menu":
            _, sub = menu_ar()
            cat = state.category_key
            if cat not in sub or text not in sub[cat]:
                return TXT["invalid_choice"] + "\n\n" + prompt_sub_menu(cat), True
            push_history(state)
            state.service_key = text
            state.service_name = sub[cat][text]
            state.step = "name"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "name":
            if len(text) < MIN_NAME:
                return TXT["too_short_name"], False
            push_history(state)
            state.name = text
            state.step = "phone"
            set_state(state)
            return TXT["enter_phone"], False

        if state.step == "phone":
            phone = validate_phone(text)
            if not phone:
                return TXT["phone_invalid"], False
            push_history(state)
            state.phone = phone
            state.step = "address"
            set_state(state)
            return TXT["enter_address"], False

        if state.step == "address":
            if len(text) < MIN_ADDRESS:
                return TXT["too_short_addr"], False
            push_history(state)
            state.address = text
            state.step = "details"
            set_state(state)
            return prompt_for_step(state, brand=brand, slogan=slogan), False

        if state.step == "details":
            if not text.strip():
                return TXT["details_empty"], False

            state.details = text.strip()
            save_request_to_excel(state)
            notify_new_request(state)  # ✅ إشعار لحظي (Email + Telegram)

            confirmation = (
                f"{TXT['saved_ok']}\n\n"
                f"{state.category_name}\n{state.service_name}\n\n"
                f"{TXT['enter_name']} {state.name}\n"
                f"{TXT['enter_phone']} {state.phone}\n"
                f"{TXT['enter_address']} {state.address}\n"
                f"{TXT['enter_details']} {state.details}\n\n"
            )

            set_state(state)
            restart_msg, _ = restart_to_role()
            return confirmation + restart_msg, True

        return restart_to_role()

    # provider flow
    if state.role == "provider":
        if state.step == "p_name":
            if len(text) < MIN_NAME:
                return TXT["too_short_name"], False
            push_history(state)
            state.p_name = text
            state.step = "p_phone"
            set_state(state)
            return TXT["enter_phone"], False

        if state.step == "p_phone":
            phone = validate_phone(text)
            if not phone:
                return TXT["phone_invalid"], False
            push_history(state)
            state.p_phone = phone
            state.step = "p_profession"
            set_state(state)
            return TXT["provider_profession"], False

        if state.step == "p_profession":
            if len(text) < 2:
                return TXT["provider_profession"], False
            push_history(state)
            state.p_profession = text
            state.step = "p_contrib"
            set_state(state)
            return TXT["provider_contrib"], False

        if state.step == "p_contrib":
            if len(text) < 2:
                return TXT["provider_contrib"], False
            push_history(state)
            state.p_contrib = text
            state.step = "p_home"
            set_state(state)
            return TXT["provider_home"], False

        if state.step == "p_home":
            state.p_home = text.strip() if text.strip() else "لا يوجد"
            save_provider_to_excel(state)
            notify_new_provider(state)  # ✅ إشعار لحظي (Email + Telegram)

            msg = (
                f"{TXT['provider_saved']}\n\n"
                f"{TXT['enter_name']} {state.p_name}\n"
                f"{TXT['enter_phone']} {state.p_phone}\n"
                f"{TXT['provider_profession']} {state.p_profession}\n"
                f"{TXT['provider_contrib']} {state.p_contrib}\n"
                f"{TXT['provider_home']} {state.p_home}\n\n"
            )

            set_state(state)
            restart_msg, _ = restart_to_role()
            return msg + restart_msg, True

        return restart_to_role()

    return restart_to_role()