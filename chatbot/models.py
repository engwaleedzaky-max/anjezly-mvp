# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Literal

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
    "done",
]

@dataclass
class ChatState:
    role: Optional[Role] = None
    step: str = "role"

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ChatState":
        st = ChatState()
        for k,v in d.items():
            if hasattr(st, k):
                setattr(st, k, v)
        return st
