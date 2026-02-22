import time, json, os, threading, requests, feedparser, datetime

# Variabel Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID") # Tetap simpan ID angka Anda di sini
OWNER_USERNAME = "njmondeth" # Username Owner Utama
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# Konfigurasi Channel Owner
CHANNEL_ID = "@xallertch"
CHANNEL_LINK = "https://t.me/xallertch"

# Nitter Mirror
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
    # Cek berdasarkan ID angka atau Username
    chat_id = str(msg["chat"]["id"])
    username = msg["chat"].get("username", "").lower()
    return chat_id == str(OWNER_CHAT_ID) or username == OWNER_USERNAME.lower()

def is_member(user_id):
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=5).json()
        status = r.get("result", {}).get("status", "")
        return status in ["creator", "administrator", "member"]
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

# --- MONITORING (TRIAL & VIP CHECK) ---
def monitor():
    while True:
        try:
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            for chat_id, data in users.items():
                days = get_remaining_days(chat_id)
                target_channel = data.get("target_channel")
                if not target_channel: continue

                # Reminder & Expired Check (Khusus non-VIP & non-Owner)
                if not data.get("is_vip") and days in [3, 1] and data.get("last_remind") != current_date:
                    send(chat_id, f"⚠️ *TRIAL REMINDER*\nSisa {days} hari. Upgrade VIP via @Allertnow untuk notifikasi akurat!")
                    data["last_remind"] = current_date

                if days <= 0 and not data.get("is_vip"):
                    continue 

                # Monitoring X
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

# --- FUNGSI TAMPILAN ---
def main_menu(user_id, is_owner_user=False):
    u = users[str(user_id)]
    if is_owner_user:
        status = "👑 MASTER OWNER"
    else:
        status = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
    
    return {
        "keyboard": [
            [{"text": "add account"}],
            [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}],
            [{"text": f"👤 Status: {status}"}]
        ],
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
                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                
                owner_access = is_owner(msg)

                # 1. Force Subscribe (Owner Bebas)
                if not owner_access and not is_member(chat_id):
                    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**\nBergabunglah ke channel kami untuk mulai memantau.", kb)
                    continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "join_date": None, "is_vip": False})
                if owner_access: u["is_vip"] = True # Owner otomatis VIP

                # 2. Registrasi Channel (Owner Bebas pendaftaran jika sudah punya target)
                if not u["target_channel"]:
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        send(chat_id, "✅ **TERHUBUNG!**\nSistem X-Aller siap digunakan.", main_menu(chat_id, owner_access))
                    else:
                        send(chat_id, "📖 **AKTIVASI**\nForward satu pesan dari channel pribadi Anda ke sini.")
                    continue

                # 3. Perintah Admin
                if text.startswith("/setvip") and owner_access:
                    t_id = text.split(" ")[1]
                    if t_id in users:
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 *VIP AKTIF*\nNikmati notifikasi akurat selamanya!", main_menu(t_id))
                        send(chat_id, f"✅ Sukses aktivasi VIP: `{t_id}`")
                    continue

                if text == "/admin" and owner_access:
                    rep = f"👑 *ADMIN DASHBOARD*\nUsers: {len(users)}\n"
                    for uid, ud in users.items():
                        rep += f"👤 `{uid}`: {list(ud.get('accounts', {}).keys())}\n"
                    send(chat_id, rep)

                # 4. Menu Utama
                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                
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
                    if owner_access:
                        send(chat_id, "👑 **STATUS: MASTER OWNER**\nAnda memiliki akses penuh ke seluruh sistem.")
                    else:
                        d = get_remaining_days(chat_id)
                        st = "💎 Akun VIP" if u["is_vip"] else f"⏳ Trial: {d} Hari"
                        send(chat_id, f"📊 *INFO*\nStatus: {st}\nUpgrade VIP (Rp 15.000) hubungi: @Allertnow")

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
