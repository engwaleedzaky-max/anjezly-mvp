# -*- coding: utf-8 -*-
from __future__ import annotations
from config import BRAND_AR, SLOGAN_AR

def render_chat_page(initial_bot_message: str) -> str:
    # UI: dark, RTL, with loading message support
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{BRAND_AR}</title>
<style>
  :root{{
    --bg:#0b1220;
    --panel:#0f1a2e;
    --bubble:#1b2a44;
    --mine:#0f3a2e;
    --text:#e5e7eb;
    --muted:#9ca3af;
    --accent:#16a34a;
    --border:rgba(255,255,255,.08);
  }}
  body{{margin:0;background:linear-gradient(180deg,#070b14,var(--bg));color:var(--text);font-family:system-ui,Segoe UI,Tahoma,Arial;}}
  .wrap{{max-width:1200px;margin:0 auto;padding:24px;}}
  .top{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;}}
  .brand{{text-align:right}}
  .brand h1{{margin:0;font-size:42px;letter-spacing:.4px}}
  .brand p{{margin:4px 0 0;color:var(--muted);font-weight:600}}
  .logo{{width:120px;height:120px;border-radius:24px;background:radial-gradient(circle at 30% 30%, rgba(22,163,74,.25), rgba(15,23,42,.0) 60%), rgba(12,24,18,.55);
        display:flex;align-items:center;justify-content:center;border:1px solid var(--border);}}
  .logo svg{{width:110px;height:110px;}}
  .panel{{margin-top:18px;background:rgba(15,26,46,.72);border:1px solid var(--border);border-radius:18px;padding:18px;min-height:560px;position:relative;}}
  .chat{{display:flex;gap:18px;}}
  .messages{{flex:1;min-height:480px;}}
  .bubble{{max-width:560px;padding:14px 16px;border-radius:16px;margin:10px 0;white-space:pre-wrap;line-height:1.65}}
  .bot{{background:var(--bubble);margin-left:auto}}
  .me{{background:var(--mine);margin-right:auto}}
  .inputbar{{display:flex;gap:10px;align-items:center;margin-top:12px}}
  input{{flex:1;background:#0a1220;border:1px solid rgba(59,130,246,.45);color:var(--text);padding:14px 14px;border-radius:14px;outline:none}}
  button{{border:none;border-radius:12px;padding:12px 16px;font-weight:800;cursor:pointer}}
  .send{{background:var(--accent);color:white}}
  .back{{background:#374151;color:white}}
  .restart{{background:#374151;color:white}}
  .chips{{display:flex;gap:10px;justify-content:flex-end;margin-top:10px;flex-wrap:wrap}}
  .chip{{width:38px;height:38px;border-radius:999px;background:rgba(255,255,255,.06);display:flex;align-items:center;justify-content:center;border:1px solid var(--border);font-weight:800}}
  .footer{{position:absolute;left:14px;bottom:12px;color:rgba(255,255,255,.35);font-size:12px;text-align:left;}}
  .spinner{{display:none;color:var(--muted);font-size:13px;margin-top:6px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <h1>{BRAND_AR}</h1>
      <p>{SLOGAN_AR}</p>
    </div>
    <div class="logo" title="Anjezly">
      <!-- Option A: shield+bolt+check (scaled to fill) -->
      <svg viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="16" y="16" width="224" height="224" rx="48" fill="#0E2A24" opacity="0.95"/>
        <path d="M128 44c22 18 48 22 74 24v64c0 52-30 92-74 108-44-16-74-56-74-108V68c26-2 52-6 74-24z"
              stroke="#E5E7EB" stroke-width="10" stroke-linejoin="round" opacity="0.92"/>
        <path d="M134 72L92 144h38l-10 60 44-76h-36l6-56z" fill="#16A34A"/>
        <circle cx="182" cy="170" r="28" fill="#111827" opacity="0.85"/>
        <path d="M170 170l8 8 18-20" stroke="#E5E7EB" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
  </div>

  <div class="panel">
    <div class="chat">
      <div class="messages" id="messages">
        <div class="bubble bot" id="firstBot">{initial_bot_message}</div>
      </div>
    </div>

    <div class="inputbar">
      <button class="restart" id="restartBtn">بدء من جديد</button>
      <button class="back" id="backBtn">رجوع</button>
      <button class="send" id="sendBtn">إرسال</button>
      <input id="text" placeholder="اكتب رقم/رسالة..." autocomplete="off" />
    </div>
    <div class="spinner" id="spinner">⏳ انتظر قليلًا...</div>

    <div class="chips" id="chips"></div>

    <div class="footer">© 2026 م/ وليد زكي<br/>جميع الحقوق محفوظة.</div>
  </div>
</div>

<script>
const messages = document.getElementById("messages");
const input = document.getElementById("text");
const sendBtn = document.getElementById("sendBtn");
const backBtn = document.getElementById("backBtn");
const restartBtn = document.getElementById("restartBtn");
const chips = document.getElementById("chips");
const spinner = document.getElementById("spinner");

function addBubble(text, who) {{
  const div = document.createElement("div");
  div.className = "bubble " + who;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}}

function setChips(show) {{
  chips.innerHTML = "";
  if (!show) return;
  // 1..9 plus 0
  const nums = ["1","2","3","4","5","6","7","8","9","0"];
  nums.forEach(n => {{
    const c = document.createElement("div");
    c.className = "chip";
    c.textContent = n;
    c.onclick = () => {{
      input.value = n;
      input.focus();
    }};
    chips.appendChild(c);
  }});
}}

async function send(text) {{
  const payload = {{ text }};
  spinner.style.display = "block";
  sendBtn.disabled = true;
  backBtn.disabled = true;
  restartBtn.disabled = true;
  try {{
    const res = await fetch("/api/message", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(payload)
    }});
    const data = await res.json();
    addBubble(data.reply, "bot");
    setChips(!!data.show_chips);
  }} catch(e) {{
    addBubble("حدث خطأ.", "bot");
  }} finally {{
    spinner.style.display = "none";
    sendBtn.disabled = false;
    backBtn.disabled = false;
    restartBtn.disabled = false;
  }}
}}

sendBtn.onclick = () => {{
  const t = input.value.trim();
  if (!t) return;
  addBubble(t, "me");
  input.value = "";
  send(t);
}};

input.addEventListener("keydown", (e) => {{
  if (e.key === "Enter") sendBtn.click();
}});

backBtn.onclick = () => {{
  addBubble("رجوع", "me");
  send("رجوع");
}};
restartBtn.onclick = () => {{
  addBubble("بدء من جديد", "me");
  send("بدء من جديد");
}};

// initial chips: role step has choices
setChips(true);
</script>
</body>
</html>"""
