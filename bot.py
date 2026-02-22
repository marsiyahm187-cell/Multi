import time, json, os, threading, requests, feedparser, datetime

# Variabel Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
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

# --- MONITORING DENGAN AUTO REMINDER ---
def monitor():
    while True:
        try:
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            for chat_id, data in users.items():
                days = get_remaining_days(chat_id)
                target_channel = data.get("target_channel")
                
                if not target_channel: continue

                # 1. LOGIKA PENGINGAT (REMINDER)
                if not data.get("is_vip") and days in [3, 1] and data.get("last_remind") != current_date:
                    msg_remind = (
                        f"⚠️ *PENGINGAT MASA TRIAL*\n\n"
                        f"Masa trial Anda tersisa *{days} hari*.\n"
                        f"Dapatkan **notifikasi langsung secara akurat** dengan upgrade ke VIP hanya Rp 15.000/bln!\n"
                        f"Hubungi: @Allertnow"
                    )
                    send(chat_id, msg_remind)
                    data["last_remind"] = current_date

                # 2. CEK STATUS EXPIRED
                if days <= 0 and not data.get("is_vip"):
                    if data.get("expired_notified") != True:
                        send(chat_id, "❌ *MASA TRIAL HABIS*\n\nLayanan terhenti. Upgrade VIP sekarang untuk mendapatkan notifikasi tercepat dan akurat via @Allertnow.")
                        data["expired_notified"] = True
                    continue 

                # 3. PROSES MONITORING X
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
def main_menu(user_id):
    u = users[str(user_id)]
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
                
                # Force Subscribe
                if not is_member(chat_id) and chat_id != str(OWNER_CHAT_ID):
                    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**\n\nSilakan bergabung ke channel kami untuk mulai memantau.", kb)
                    continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "join_date": None, "is_vip": False})

                # --- SAMBUTAN & REGISTRASI CHANNEL ---
                if not u["target_channel"]:
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        
                        # PESAN SAMBUTAN KHUSUS (WELCOME MESSAGE)
                        welcome_msg = (
                            "🎊 **SELAMAT! CHANNEL BERHASIL TERHUBUNG** 🎊\n\n"
                            "Bot X-Aller kini siap mengirimkan informasi tercepat langsung ke channel Anda.\n\n"
                            "ℹ️ **Informasi Layanan:**\n"
                            "• Masa Trial: **30 Hari (Aktif)**\n"
                            "• Keunggulan VIP: Notifikasi Tercepat & Akurat\n"
                            "• Biaya Sewa VIP: **Rp 15.000 / Bulan**\n\n"
                            "🚀 **Cara Memulai:**\n"
                            "Gunakan tombol `add account` di bawah untuk menambahkan username X yang ingin dipantau.\n\n"
                            "📩 *Butuh bantuan atau upgrade VIP?* Hubungi: @Allertnow"
                        )
                        send(chat_id, welcome_msg, main_menu(chat_id))
                    else:
                        send(chat_id, "📖 **PANDUAN AKTIVASI**\n\n1. Buat channel pribadi.\n2. Jadikan bot ini Admin di sana.\n3. **Forward** satu pesan dari channel tersebut ke sini.")
                    continue

                # Perintah Admin
                if text.startswith("/setvip") and chat_id == str(OWNER_CHAT_ID):
                    t_id = text.split(" ")[1]
                    if t_id in users:
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 *VIP AKTIF*\n\nLayanan VIP Anda aktif! Nikmati notifikasi tercepat secara akurat.", main_menu(t_id))
                        send(chat_id, f"✅ Sukses mengaktifkan VIP untuk `{t_id}`.")
                    continue

                # Menu Utama
                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id))
                
                elif text.lower() == "add account":
                    if get_remaining_days(chat_id) <= 0 and not u["is_vip"]:
                        send(chat_id, "❌ Trial habis. Upgrade VIP Rp 15.000 untuk notifikasi akurat.")
                    else:
                        u["state"] = "add"; send(chat_id, "👤 Username X (tanpa @):")

                elif u.get("state") == "add":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id))

                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 **DAFTAR:**\n\n" + ("\n".join(accs) if accs else "Kosong."))

                elif text.startswith("👤 Status:"):
                    d = get_remaining_days(chat_id)
                    st = "💎 Akun VIP" if u["is_vip"] else f"⏳ Trial: {d} Hari"
                    msg_v = (
                        f"📊 *INFO LAYANAN*\n\n"
                        f"Status: {st}\n"
                        f"Harga VIP: *Rp 15.000 / Bulan*\n\n"
                        f"🚀 **Kelebihan VIP:**\n"
                        f"• Notifikasi langsung & akurat.\n"
                        f"• Prioritas server tercepat.\n"
                        f"• Pemantauan tanpa batas waktu.\n\n"
                        f"Pembayaran via Dana/Gopay/QRIS hubungi:\n"
                        f"📩 @Allertnow"
                    )
                    send(chat_id, msg_v)

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
