import time, json, os, threading, requests, feedparser, datetime

# ==== KONFIGURASI UTAMA ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID") # ID Angka dari Railway
OWNER_USERNAME = "njmondeth"               # Username Anda
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

CHANNEL_ID = "@xallertch"
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
    chat_id = str(msg["chat"]["id"])
    username = msg["chat"].get("username", "").lower()
    return chat_id == str(OWNER_CHAT_ID) or username == OWNER_USERNAME.lower()

def is_member(user_id):
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=5).json()
        if r.get("ok"):
            status = r.get("result", {}).get("status", "")
            return status in ["creator", "administrator", "member"]
        return False
    except: return True

def get_remaining_days(user_id):
    u = users.get(str(user_id))
    if not u or not u.get("join_date"): return 0
    if u.get("is_vip"): return 999 
    join_date = datetime.datetime.strptime(u["join_date"], "%Y-%m-%d")
    expiry_date = join_date + datetime.timedelta(days=30)
    remaining = (expiry_date - datetime.datetime.now()).days
    return max(0, remaining)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    requests.post(f"{API}/editMessageText", data=payload)

def delete_msg(chat_id, msg_id):
    requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

def answer_callback(callback_id, text=None, alert=False):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text, "show_alert": alert})

def send_lock_msg(chat_id):
    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
    send(chat_id, "⚠️ **AKSES TERKUNCI**\n\nSilakan bergabung ke channel kami untuk mulai memantau.", kb)

# --- KEYBOARDS ---
def main_menu(user_id, owner_access=False):
    u = users.get(str(user_id), {})
    if owner_access: status_text = "👑 MASTER OWNER"
    else: status_text = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
    
    return {
        "keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status_text}"}]],
        "resize_keyboard": True
    }

# --- MONITORING LOOP ---
def monitor():
    while True:
        try:
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            for chat_id, data in users.items():
                days = get_remaining_days(chat_id)
                target_channel = data.get("target_channel")
                if not target_channel: continue

                if not data.get("is_vip") and days in [3, 1] and data.get("last_remind") != current_date:
                    send(chat_id, f"⚠️ *PENGINGAT*\nSisa {days} hari! Dapatkan notifikasi akurat dengan upgrade VIP via {ADMIN_PEMBELIAN}.")
                    data["last_remind"] = current_date

                if days <= 0 and not data.get("is_vip"): continue 

                for acc, cfg in data.get("accounts", {}).items():
                    for base_url in NITTER_INSTANCES:
                        feed = feedparser.parse(f"{base_url}/{acc}/rss")
                        if feed.entries:
                            post = feed.entries[0]
                            if cfg.get("last") != post.link:
                                cfg["last"] = post.link
                                send(target_channel, f"🔔 *UPDATE @{acc}*\n\n{post.link}")
                            break
            save_data()
        except: pass
        time.sleep(120)

# --- BOT LOOP ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                # CALLBACK HANDLER
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    
                    if data == "check_sub":
                        if is_member(chat_id):
                            answer_callback(cq["id"], "✅ Akses dibuka!")
                            delete_msg(chat_id, msg_id)
                            send(chat_id, "🤖 **X-ALLER SYSTEM READY**", main_menu(chat_id, is_owner(cq["message"])))
                        else:
                            answer_callback(cq["id"], "❌ Anda belum join @xallertch!", alert=True)
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                if not owner_access and not is_member(chat_id):
                    send_lock_msg(chat_id); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "join_date": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # REGISTRASI CHANNEL
                if not u["target_channel"]:
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        welcome = (f"🎊 **TERHUBUNG!** 🎊\n\nTrial 30 Hari Aktif.\n🚀 **Kelebihan VIP:** Notifikasi akurat & cepat.\n💰 Sewa: Rp 15.000/bln\nHubungi: {ADMIN_PEMBELIAN}")
                        send(chat_id, welcome, main_menu(chat_id, owner_access))
                    else:
                        send(chat_id, "📖 **PANDUAN**\n\nJadikan bot Admin di channel pribadi Anda, lalu **Forward** satu pesan dari channel tersebut ke sini.")
                    continue

                # COMMANDS
                if text == "/start": send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                elif text.startswith("/setvip") and owner_access:
                    t_id = text.split(" ")[1]
                    if t_id in users:
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 *VIP AKTIF!* Terimakasih telah berlangganan.", main_menu(t_id))
                        send(chat_id, f"✅ Sukses set VIP: `{t_id}`")
                elif text.lower() == "add account":
                    if get_remaining_days(chat_id) <= 0 and not u["is_vip"]:
                        send(chat_id, f"❌ Trial habis. Hubungi {ADMIN_PEMBELIAN} untuk VIP.")
                    else:
                        u["state"] = "add"; send(chat_id, "👤 Username X (tanpa @):")
                elif u.get("state") == "add":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id, owner_access))
                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 **DAFTAR:**\n\n" + ("\n".join(accs) if accs else "Kosong."))
                elif text.startswith("👤 Status:"):
                    d = get_remaining_days(chat_id)
                    st = "👑 MASTER OWNER" if owner_access else ("💎 Akun VIP" if u["is_vip"] else f"⏳ Trial: {d} Hari")
                    send(chat_id, f"📊 *INFO*\nStatus: {st}\nVIP (Rp 15.000/bln): {ADMIN_PEMBELIAN}\n\nFitur VIP: Notifikasi akurat & real-time.")

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
