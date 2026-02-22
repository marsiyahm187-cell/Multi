import time, json, os, threading, requests, feedparser, datetime

# ==== KONFIGURASI ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

CHANNEL_ID = "@xallertch" # PASTIKAN USERNAME INI BENAR
CHANNEL_LINK = "https://t.me/xallertch"
ADMIN_PEMBELIAN = "@Allertnow"

NITTER_INSTANCES = ["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f: json.dump(users, f)

users = load_data()

# --- FUNGSI VALIDASI ---
def is_owner(msg):
    if not msg: return False
    # Mengambil data dari objek message atau callback_query
    chat = msg.get("chat", msg.get("from", {}))
    chat_id = str(chat.get("id", ""))
    username = chat.get("username", "").lower()
    return chat_id == str(OWNER_CHAT_ID) or username == OWNER_USERNAME.lower()

def is_member(user_id, msg=None):
    if msg and is_owner(msg): return True # Owner bebas cek
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("ok"):
            status = r.get("result", {}).get("status", "")
            return status in ["creator", "administrator", "member"]
        return False
    except: return True

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def delete_msg(chat_id, msg_id):
    requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

def answer_callback(callback_id, text=None, alert=False):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text, "show_alert": alert})

def send_lock_msg(chat_id):
    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
    send(chat_id, "⚠️ **AKSES TERKUNCI**\n\nSilakan bergabung ke channel kami untuk mulai memantau.", kb)

def main_menu(user_id, owner_access=False):
    u = users.get(str(user_id), {})
    if owner_access: status_text = "👑 MASTER OWNER"
    else:
        join_date = u.get("join_date")
        if not join_date: days = 30
        else:
            jd = datetime.datetime.strptime(join_date, "%Y-%m-%d")
            days = max(0, (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days)
        status_text = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {days} Hari"
    
    return {
        "keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status_text}"}]],
        "resize_keyboard": True
    }

# --- BOT LOOP ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                # Callback untuk tombol Cek Status
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    
                    if data == "check_sub":
                        if is_member(chat_id, cq):
                            answer_callback(cq["id"], "✅ Akses dibuka!")
                            delete_msg(chat_id, msg_id)
                            send(chat_id, "🤖 **X-ALLER SYSTEM READY**", main_menu(chat_id, is_owner(cq)))
                        else:
                            answer_callback(cq["id"], "❌ Anda belum join @xallertch!", alert=True)
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                if not owner_access and not is_member(chat_id, msg):
                    send_lock_msg(chat_id); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "join_date": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # Alur Forward Channel
                if not u["target_channel"]:
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        welcome = (f"🎊 **TERHUBUNG!** 🎊\n\nSewa: Rp 15.000/bln\nHubungi: {ADMIN_PEMBELIAL}")
                        send(chat_id, welcome, main_menu(chat_id, owner_access))
                    else:
                        send(chat_id, "📖 **PANDUAN**\n\nForward satu pesan dari channel pribadi Anda (tempat bot jadi Admin) ke sini.")
                    continue

                if text == "/start": send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                elif text.lower() == "add account":
                    u["state"] = "add"; send(chat_id, "👤 Username X (tanpa @):")
                elif u.get("state") == "add":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id, owner_access))
                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 **DAFTAR:**\n\n" + ("\n".join(accs) if accs else "Kosong."))
                elif text.startswith("👤 Status:"):
                    send(chat_id, f"📊 *INFO*\nOwner: @njmondeth\nVIP: {ADMIN_PEMBELIAN}")

        except: pass
        time.sleep(1)

bot_loop()
