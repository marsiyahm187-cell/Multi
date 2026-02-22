import time, json, os, threading, requests, feedparser, datetime

# ==== DATA IDENTITAS OWNER ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# KONFIGURASI BISNIS
CHANNEL_ID = "@xallertch"
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
    with open(DATA_FILE, "w") as f: json.dump(users, f)

users = load_data()

# --- FUNGSI IDENTIFIKASI ---
def is_owner(msg):
    from_user = msg.get("from", msg.get("chat", {}))
    chat_id = str(from_user.get("id", ""))
    username = from_user.get("username", "").lower() if from_user.get("username") else ""
    # Owner dikenali lewat ID Railway atau Username @njmondeth
    return chat_id == str(OWNER_CHAT_ID) or username == OWNER_USERNAME.lower()

def is_member(user_id, msg=None):
    if msg and is_owner(msg): return True # Owner bebas akses
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
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
    remaining = (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days
    return max(0, remaining)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def delete_msg(chat_id, msg_id):
    return requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

# --- KEYBOARDS ---
def main_menu(user_id, owner_access=False):
    u = users.get(str(user_id), {})
    if owner_access:
        # Menu Khusus Owner
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": "👑 ADMIN DASHBOARD"}]]
    else:
        # Menu Khusus User
        status = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status}"}]]
    return {"keyboard": kb, "resize_keyboard": True}

def mode_keyboard(selected):
    def mark(x): return f"✅ {x}" if x in selected else f"❌ {x}"
    return {"inline_keyboard": [
        [{"text": mark("posting"), "callback_data": "mode|posting"}],
        [{"text": mark("reply"), "callback_data": "mode|reply"}],
        [{"text": mark("repost"), "callback_data": "mode|repost"}],
        [{"text": "🚀 KONFIRMASI", "callback_data": "done"}]
    ]}

# --- MONITORING (PROSES UTAMA) ---
def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                days = get_remaining_days(chat_id)
                target_channel = data.get("target_channel")
                if not target_channel or (days <= 0 and not data.get("is_vip")): continue

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

# --- BOT LOOP (INTERAKSI) ---
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
                    u = users.setdefault(chat_id, {"accounts": {}, "modes": []})

                    if data == "done":
                        acc = u.get("temp_acc")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            save_data(); delete_msg(chat_id, msg_id)
                            send(chat_id, f"✅ @{acc} dipantau!", main_menu(chat_id, is_owner(cq)))
                    elif data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u["modes"]: u["modes"].remove(m)
                        else: u["modes"].append(m)
                        requests.post(f"{API}/editMessageText", data={"chat_id": chat_id, "message_id": msg_id, "text": f"⚙️ *MODE @{u.get('temp_acc')}*", "reply_markup": json.dumps(mode_keyboard(u["modes"])), "parse_mode": "Markdown"})
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                # Proteksi User Umum
                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**\nJoin channel kami terlebih dahulu.", kb); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None})
                if owner_access: u["is_vip"] = True

                # Alur Forward (Syarat User)
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data(); send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else: send(chat_id, "📖 Forward pesan channel Anda ke sini."); continue

                # --- LOGIKA KHUSUS OWNER (@njmondeth) ---
                if text == "👑 ADMIN DASHBOARD" and owner_access:
                    rep = f"📊 *STATISTIK BOT*\nTotal User: {len(users)}\n\n"
                    rep += "Gunakan `/setvip [ID]` untuk aktivasi user."
                    send(chat_id, rep); continue

                if text.startswith("/setvip") and owner_access:
                    t_id = text.split(" ")[1]
                    if t_id in users:
                        users[t_id]["is_vip"] = True; save_data()
                        send(chat_id, f"✅ User `{t_id}` menjadi VIP."); send(t_id, "💎 VIP Aktif!")
                    continue

                # --- LOGIKA UMUM ---
                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                elif text.lower() == "add account":
                    if get_remaining_days(chat_id) <= 0 and not u.get("is_vip"):
                        send(chat_id, f"❌ Trial habis. Hubungi {ADMIN_PEMBELIAN}."); continue
                    u["state"] = "input"; send(chat_id, "👤 Username X (tanpa @):")
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["temp_acc"] = acc; u["modes"] = []; u["state"] = None
                    send(chat_id, f"⚙️ *SETTING @{acc}*", mode_keyboard([]))
                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 *DAFTAR:* \n" + ("\n".join(accs) if accs else "Kosong."))
                elif text.startswith("👤 Status:"):
                    d = get_remaining_days(chat_id)
                    st = "💎 Akun VIP" if u.get("is_vip") else f"⏳ Trial: {d} Hari"
                    send(chat_id, f"📊 *INFO*\nStatus: {st}\nUpgrade VIP: {ADMIN_PEMBELIAN}")

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
