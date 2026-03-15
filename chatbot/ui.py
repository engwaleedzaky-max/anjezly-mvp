# file: chatbot_app/ui.py
# =========================
from __future__ import annotations

from config import CMD_BACK, CMD_RESTART

HTML_TEMPLATE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>__TITLE__</title>
  <style>
    body { font-family: system-ui, Arial; margin: 0; background:#0b1220; color:#fff; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 18px; }
    .header { display:flex; justify-content: space-between; align-items:center; gap:12px; }
    .brand { display:flex; align-items:center; gap:14px; }
    .logo { width:126px; height:126px; border-radius:28px; background: rgba(22,163,74,.12);
            display:flex; align-items:center; justify-content:center; overflow:hidden; }
    .logo svg { width:92px; height:92px; }
    .title { margin:0; font-weight:900; font-size: 30px; line-height: 1.1; }
    .slogan { margin:0; opacity:.85; }
    .card { margin-top:14px; background: #0f1a2e; border:1px solid rgba(255,255,255,.08); border-radius: 16px; padding: 14px; }
    .chat { height: 60vh; overflow:auto; padding: 10px; display:flex; flex-direction:column; gap:10px; }
    .bubble { max-width: 88%; padding: 10px 12px; border-radius: 14px; line-height:1.7; white-space: pre-wrap; }
    .bot { background: rgba(255,255,255,.08); align-self:flex-start; }
    .me { background: rgba(22,163,74,.22); align-self:flex-end; }
    .row { display:flex; gap:10px; margin-top: 12px; flex-wrap: wrap; }
    input { flex:1; min-width: 240px; padding: 12px; border-radius: 14px;
            border:1px solid rgba(255,255,255,.12); background:#0b1220; color:#fff; }
    button { padding: 12px 14px; border-radius: 14px; border:none; color:#fff; font-weight:900; cursor:pointer; }
    button:disabled { opacity:.6; cursor:not-allowed; }
    .btn-send { background:#16A34A; }
    .btn-back { background: rgba(255,255,255,.14); }
    .btn-restart { background: rgba(255,255,255,.10); }
    a { color:#a7f3d0; text-decoration:none; }
    .chips { display:flex; gap:8px; flex-wrap: wrap; margin-top: 10px; }
    .chip { padding: 8px 10px; border-radius: 999px; background: rgba(255,255,255,.08);
            border: 1px solid rgba(255,255,255,.10); cursor:pointer; font-weight:800; }
    .chip:hover { background: rgba(255,255,255,.12); }
    .hide { display:none !important; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div class="brand">
        <div class="logo" aria-label="Logo">
          <!-- Full Shield -->
          <svg viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M64 6c21 16 40 20 54 23v39c0 34-20 52-54 60C30 120 10 102 10 68V29c14-3 33-7 54-23Z"
                  fill="rgba(22,163,74,.20)" stroke="rgba(226,232,240,.92)" stroke-width="5" stroke-linejoin="round"/>
            <path d="M78 20 36 78h30l-6 34 42-60H72l6-32Z" fill="#16A34A"/>
            <circle cx="96" cy="96" r="20" fill="rgba(15,23,42,.92)" stroke="rgba(226,232,240,.85)" stroke-width="3"/>
            <path d="M87 96l7 8 15-17" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div>
          <h1 class="title">__BRAND__</h1>
          <p class="slogan">__SLOGAN__</p>
        </div>
      </div>
      <div><a href="/admin">لوحة الأدمن</a></div>
    </div>

    <div class="card">
      <div id="chat" class="chat">
        <div class="bubble bot">__INITIAL__</div>
      </div>

      <div class="row">
        <input id="msg" placeholder="اكتب رقم/رسالة..." />
        <button id="send" class="btn-send">إرسال</button>
        <button id="back" class="btn-back" title="رجوع">رجوع</button>
        <button id="restart" class="btn-restart" title="بدء من جديد">بدء من جديد</button>
      </div>

      <div id="chips" class="chips">
        <div class="chip" data-text="1">1</div><div class="chip" data-text="2">2</div><div class="chip" data-text="3">3</div>
        <div class="chip" data-text="4">4</div><div class="chip" data-text="5">5</div><div class="chip" data-text="6">6</div>
        <div class="chip" data-text="7">7</div><div class="chip" data-text="8">8</div><div class="chip" data-text="9">9</div>
      </div>
    </div>
  </div>

<script>
  const CMD_BACK = "__CMD_BACK__";
  const CMD_RESTART = "__CMD_RESTART__";

  const chat = document.getElementById("chat");
  const msg = document.getElementById("msg");
  const send = document.getElementById("send");
  const back = document.getElementById("back");
  const restart = document.getElementById("restart");
  const chips = document.getElementById("chips");

  function addBubble(text, who) {
    const div = document.createElement("div");
    div.className = "bubble " + who;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function setChipsVisible(visible) {
    chips.classList.toggle("hide", !visible);
  }

  async function postText(text) {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ text })
    });
    return await res.json();
  }

  async function sendMessage(textOverride=null) {
    const text = (textOverride ?? msg.value).trim();
    if (!text) return;
    msg.value = "";
    addBubble(text, "me");
    send.disabled = true; back.disabled = true; restart.disabled = true;
    try {
      const data = await postText(text);
      addBubble(data.reply, "bot");
      setChipsVisible(!!data.show_chips);
    } catch (e) {
      addBubble("حدث خطأ.", "bot");
    } finally {
      send.disabled = false; back.disabled = false; restart.disabled = false;
      msg.focus();
    }
  }

  async function backStep() {
    send.disabled = true; back.disabled = true; restart.disabled = true;
    try {
      addBubble("رجوع", "me");
      const data = await postText(CMD_BACK);
      addBubble(data.reply, "bot");
      setChipsVisible(!!data.show_chips);
    } catch (e) {
      addBubble("حدث خطأ.", "bot");
    } finally {
      send.disabled = false; back.disabled = false; restart.disabled = false;
      msg.focus();
    }
  }

  async function restartChat() {
    send.disabled = true; back.disabled = true; restart.disabled = true;
    try {
      addBubble("بدء من جديد", "me");
      const data = await postText(CMD_RESTART);
      addBubble(data.reply, "bot");
      setChipsVisible(!!data.show_chips);
    } catch (e) {
      addBubble("حدث خطأ.", "bot");
    } finally {
      send.disabled = false; back.disabled = false; restart.disabled = false;
      msg.focus();
    }
  }

  send.addEventListener("click", () => sendMessage());
  msg.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
  back.addEventListener("click", backStep);
  restart.addEventListener("click", restartChat);

  document.querySelectorAll(".chip").forEach(el => {
    el.addEventListener("click", () => sendMessage(el.dataset.text));
  });

  setChipsVisible(true);
</script>
</body>
</html>
"""


def render_page(*, title: str, brand: str, slogan: str, initial_text: str) -> str:
    return (
        HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__BRAND__", brand)
        .replace("__SLOGAN__", slogan)
        .replace("__INITIAL__", initial_text)
        .replace("__CMD_BACK__", CMD_BACK)
        .replace("__CMD_RESTART__", CMD_RESTART)
    )

