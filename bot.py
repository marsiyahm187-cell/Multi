import time, json, os, threading, requests, feedparser, datetime

# ==== DATA IDENTITAS OWNER ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

ADMIN_PEMBELIAN = "@Allertnow"
NITTER_INSTANCES = ["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)

users = load_data()

# --- FUNGSI IDENTIFIKASI ---
def is_owner(msg):
    u = msg.get("from", msg.get("chat", {}))
    cid = str(u.get("id", ""))
    un = u.get("username", "").lower() if u.get("username") else ""
    return cid == str(OWNER_CHAT_ID) or un == OWNER_USERNAME.lower()

def get_remaining_days(user_id):
    u = users.get(str(user_id))
    if not u or not u.get("join_date"): return 30
    if u.get("is_vip"): return 999 
    jd = datetime.datetime.strptime(u["join_date"], "%Y-%m-%d")
    rem = (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days
    return max(0, rem)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def delete_msg(chat_id, msg_id):
    return requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

# --- KEYBOARDS ---
def main_menu(user_id, owner_access=False):
    u = users.setdefault(str(user_id), {"is_vip": False})
    if owner_access:
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": "👑 ADMIN DASHBOARD"}]]
    else:
        status = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status}"}]]
    return {"keyboard": kb, "resize_keyboard": True}

def admin_kb():
    return {"inline_keyboard": [
        [{"text": "👥 Semua Member", "callback_data": "adm|all"}],
        [{"text": "⏳ Trial", "callback_data": "adm|trial"}, {"text": "💎 VIP", "callback_data": "adm|vip"}],
        [{"text": "🔙 Tutup", "callback_data": "close"}]
    ]}

# --- BOT LOOP ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    
                    if not is_owner(cq): continue

                    if data == "close": requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                    elif data.startswith("adm|"):
                        m_type = data.split("|")[1]
                        btn = []
                        for uid, d in users.items():
                            is_v = d.get("is_vip", False)
                            days = get_remaining_days(uid)
                            if m_type == "trial" and (is_v or days <= 0): continue
                            if m_type == "vip" and not is_v: continue
                            tag = "💎" if is_v else "⏳"
                            btn.append([{"text": f"{tag} ID: {uid}", "callback_data": f"view|{uid}"}])
                        btn.append([{"text": "🔙 Kembali", "callback_data": "back_adm"}])
                        requests.post(f"{API}/editMessageText", data={"chat_id": chat_id, "message_id": msg_id, "text": f"📂 *DAFTAR {m_type.upper()}*", "reply_markup": json.dumps({"inline_keyboard": btn}), "parse_mode": "Markdown"})
                    elif data.startswith("view|"):
                        t_id = data.split("|")[1]
                        is_v = users[t_id].get("is_vip", False)
                        info = f"👤 *DETAIL USER*\nID: `{t_id}`\nStatus: {'VIP' if is_v else 'Trial'}"
                        kb = {"inline_keyboard": [[{"text": "🚀 UPGRADE VIP", "callback_data": f"upg|{t_id}"}], [{"text": "🔙 Kembali", "callback_data": "adm|all"}]]}
                        requests.post(f"{API}/editMessageText", data={"chat_id": chat_id, "message_id": msg_id, "text": info, "reply_markup": json.dumps(kb), "parse_mode": "Markdown"})
                    elif data.startswith("upg|"):
                        t_id = data.split("|")[1]
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 **VIP AKTIF!**"); requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": "✅ Sukses!"})
                    elif data == "back_adm": 
                        requests.post(f"{API}/editMessageText", data={"chat_id": chat_id, "message_id": msg_id, "text": "👑 *ADMIN DASHBOARD*", "reply_markup": json.dumps(admin_kb()), "parse_mode": "Markdown"})
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # Alur Forward Channel (Wajib untuk User agar bot tahu kemana harus kirim notif)
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data(); send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else:
                        send(chat_id, "📖 **AKTIVASI**\nForward satu pesan dari channel pribadi Anda ke sini."); continue

                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER ONLINE*", main_menu(chat_id, owner_access))
                elif text == "👑 ADMIN DASHBOARD" and owner_access:
                    send(chat_id, "👑 *ADMIN DASHBOARD*", admin_kb())
                elif text.lower() == "add account":
                    u["state"] = "input"; send(chat_id, "👤 Username X:")
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id, owner_access))
        except: pass
        time.sleep(1)

threading.Thread(target=bot_loop).start()
