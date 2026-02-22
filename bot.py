import time, json, os, threading, requests, feedparser, datetime

# ==== DATA IDENTITAS OWNER ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# INSTANCE NITTER (Ditambah agar lebih stabil saat cek cepat)
NITTER_INSTANCES = [
    "https://nitter.net", 
    "https://nitter.cz", 
    "https://nitter.privacydev.net",
    "https://nitter.moomoo.me",
    "https://nitter.it"
]

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

# --- FUNGSI MONITOR (INSTAN) ---
def monitor_account(user_id, screen_name):
    last_id = None
    print(f"🚀 Memulai monitor instan untuk: @{screen_name}")
    
    while True:
        try:
            u = users.get(str(user_id))
            if not u or screen_name not in u.get("accounts", {}): break
            
            # Cek Masa Aktif/VIP
            is_v = u.get("is_vip", False)
            jd = u.get("join_date")
            if not is_v and jd:
                expiry = datetime.datetime.strptime(jd, "%Y-%m-%d") + datetime.timedelta(days=30)
                if datetime.datetime.now() > expiry:
                    print(f"⏳ Masa trial habis untuk {user_id}")
                    break

            # Ambil Data dari Nitter (Rotasi otomatis)
            import random
            base_url = random.choice(NITTER_INSTANCES)
            rss_url = f"{base_url}/{screen_name}/rss"
            
            feed = feedparser.parse(rss_url)
            if feed.entries:
                latest = feed.entries[0]
                post_id = latest.link
                
                if last_id is None:
                    last_id = post_id # Hindari spam saat bot baru nyala
                elif last_id != post_id:
                    last_id = post_id
                    target = u.get("target_channel")
                    if target:
                        msg_text = f"🔔 **NEW POST FROM @{screen_name}**\n\n{latest.title}\n\n🔗 [Lihat Postingan]({latest.link})"
                        requests.post(f"{API}/sendMessage", data={
                            "chat_id": target, 
                            "text": msg_text, 
                            "parse_mode": "Markdown"
                        })
                        print(f"✅ Notif terkirim: @{screen_name}")

        except Exception as e:
            print(f"⚠️ Error Monitor @{screen_name}: {e}")
        
        # Jeda Sangat Singkat (15 detik) untuk simulasi instan tanpa kena blokir
        time.sleep(15)

# --- FUNGSI BOT STANDAR ---
def is_owner(msg):
    u = msg.get("from", msg.get("chat", {}))
    return str(u.get("id", "")) == str(OWNER_CHAT_ID) or u.get("username", "").lower() == OWNER_USERNAME.lower()

def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown"}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def main_menu(user_id, owner_access=False):
    u = users.get(str(user_id), {"is_vip": False})
    status = "💎 VIP" if u.get("is_vip") else "⏳ Trial"
    kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]]
    if owner_access: kb.append([{"text": "👑 ADMIN DASHBOARD"}])
    else: kb.append([{"text": f"👤 Status: {status}"}])
    return {"keyboard": kb, "resize_keyboard": True}

# --- BOT LOOP ---
def bot_loop():
    offset = None
    # Jalankan ulang monitor untuk akun yang sudah ada di database saat bot restart
    for uid, data in users.items():
        for acc in data.get("accounts", {}):
            threading.Thread(target=monitor_account, args=(uid, acc), daemon=True).start()

    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                
                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "is_vip": False})
                
                if text == "/start":
                    send(chat_id, "🤖 **X-ALLER HIGH SPEED SYSTEM**", main_menu(chat_id, is_owner(msg)))
                
                elif text.lower() == "add account":
                    u["state"] = "input"; send(chat_id, "👤 Ketik Username X:")
                
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"added": True}
                    u["state"] = None; save_data()
                    # Langsung jalankan monitor khusus untuk akun baru ini
                    threading.Thread(target=monitor_account, args=(chat_id, acc), daemon=True).start()
                    send(chat_id, f"✅ @{acc} sekarang dipantau secara instan!", main_menu(chat_id, is_owner(msg)))
                
                elif "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                    u["target_channel"] = msg["forward_from_chat"]["id"]
                    u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                    save_data(); send(chat_id, "✅ Channel terhubung!", main_menu(chat_id, is_owner(msg)))

        except: pass
        time.sleep(1)

bot_loop()
