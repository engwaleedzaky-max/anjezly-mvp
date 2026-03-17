# file: chatbot_app/models.py
# =========================
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

Role = Literal["customer", "provider"]

Step = Literal[
    "role",
    "main_menu",
    "sub_menu",
    "name",
    "phone",
    "address",
    "details",
    "p_name",
    "p_phone",
    "p_profession",
    "p_contrib",
    "p_home",
]


@dataclass
class ChatState:
    role: Optional[Role] = None
    step: Step = "role"

    # customer
    category_key: str = ""
    category_name: str = ""
    service_key: str = ""
    service_name: str = ""
    name: str = ""
    phone: str = ""
    address: str = ""
    details: str = ""

    # provider
    p_name: str = ""
    p_phone: str = ""
    p_profession: str = ""
    p_contrib: str = ""
    p_home: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChatState":
        st = cls()
        for k in st.__dict__.keys():
            if k in raw:
                setattr(st, k, raw[k])

        if st.role not in (None, "customer", "provider"):
            st.role = None

        valid_steps = {
            "role",
            "main_menu",
            "sub_menu",
            "name",
            "phone",
            "address",
            "details",
            "p_name",
            "p_phone",
            "p_profession",
            "p_contrib",
            "p_home",
        }
        if st.step not in valid_steps:
            st.step = "role"

        return st
