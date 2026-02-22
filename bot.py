import time, json, os, threading, requests, feedparser, datetime

# ==== DATA IDENTITAS OWNER ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# ==== CONFIG CHANNEL (SUDAH MENGGUNAKAN ID ANGKA) ====
CHANNEL_INTERNAL_ID = "-1003593205049" 
CHANNEL_LINK = "https://t.me/xallertch"
ADMIN_PEMBELIAN = "@Allertnow"

# INSTANCE NITTER
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

def is_member(user_id, msg=None):
    # Owner selalu lolos pengecekan
    if msg and is_owner(msg): return True
    try:
        url = f"{API}/getChatMember"
        # Verifikasi menggunakan ID Internal agar instan dan akurat
        params = {"chat_id": CHANNEL_INTERNAL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("ok"):
            status = r.get("result", {}).get("status", "")
            return status in ["creator", "administrator", "member"]
        return False
    except: return True

def get_remaining_days(user_id):
    u = users.get(str(user_id))
    if not u or not u.get("join_date"): return 0
    if u.get("is_vip"): return 999 
    jd = datetime.datetime.strptime(u["join_date"], "%Y-%m-%d")
    rem = (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days
    return max(0, rem)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def main_menu(user_id, owner_access=False):
    u = users.setdefault(str(user_id), {"is_vip": False})
    if owner_access:
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": "👑 ADMIN DASHBOARD"}]]
    else:
        st_text = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {st_text}"}]]
    return {"keyboard": kb, "resize_keyboard": True}

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
                    
                    if data == "check_sub":
                        if is_member(chat_id, cq):
                            requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                            send(chat_id, "✅ **AKSES DIBUKA!**", main_menu(chat_id, is_owner(cq)))
                        else:
                            requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": "❌ Kamu belum join!", "show_alert": True})
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Join Channel", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**\nSilakan bergabung ke channel kami untuk mulai menggunakan bot.", kb)
                    continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # Alur Forward Channel
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else:
                        send(chat_id, "📖 **AKTIVASI**\nForward satu pesan dari channel pribadi kamu ke sini (pastikan bot sudah jadi admin di channel tersebut).")
                    continue

                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                elif text == "👑 ADMIN DASHBOARD" and owner_access:
                    send(chat_id, f"👑 *ADMIN DASHBOARD*\nTotal User: {len(users)}\n\nKetik `/setvip [ID]` untuk aktivasi user.")
                elif text.startswith("/setvip") and owner_access:
                    t_id = text.split(" ")[1]
                    if t_id in users:
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 **VIP AKTIF!**"); send(chat_id, f"✅ `{t_id}` sukses VIP.")
                elif text.lower() == "add account":
                    if get_remaining_days(chat_id) <= 0 and not u.get("is_vip"):
                        send(chat_id, f"❌ Trial habis. Hubungi {ADMIN_PEMBELIAN}."); continue
                    u["state"] = "input"; send(chat_id, "👤 Username X (tanpa @):")
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id, owner_access))
                elif text == "📋 List Accounts":
                    acc_list = list(u["accounts"].keys())
                    send(chat_id, "📋 *DAFTAR:* \n" + ("\n".join(acc_list) if acc_list else "Kosong."))
        except: pass
        time.sleep(1)

threading.Thread(target=bot_loop).start()
