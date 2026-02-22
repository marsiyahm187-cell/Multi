# ==== TELEGRAM X MONITOR BOT (ULTIMATE CLEAN VERSION) ====
import time, json, os, threading, requests, feedparser

# Variabel dari Railway - Pastikan BOT_TOKEN dan OWNER_CHAT_ID sudah benar
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# Konfigurasi Channel Wajib Join
CHANNEL_ID = "@xallertch"
CHANNEL_LINK = "https://t.me/xallertch"

# Daftar Mirror Nitter untuk stabilitas pengecekan
NITTER_INSTANCES = [
    "https://nitter.net", 
    "https://nitter.cz", 
    "https://nitter.privacydev.net",
    "https://nitter.moomoo.me"
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f: json.dump(users, f)

users = load_data()

# --- FUNGSI KEANGGOTAAN (FORCE SUBSCRIBE) ---
def is_member(user_id):
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=5).json()
        status = r.get("result", {}).get("status", "")
        return status in ["creator", "administrator", "member"]
    except: return True

def send_lock_msg(chat_id):
    kb = {
        "inline_keyboard": [
            [{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}],
            [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]
        ]
    }
    send(chat_id, "⚠️ **AKSES TERKUNCI**\n\nSilakan bergabung ke channel kami untuk mengaktifkan bot.", kb)

# --- FUNGSI DASAR & PEMBERSIH ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    requests.post(f"{API}/editMessageText", data=payload)

def delete_msg(chat_id, msg_id):
    # Menghapus pesan (Pesan bot atau pesan user di grup/privat)
    requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

def answer_callback(callback_id, text=None):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text})

def is_valid_x(username):
    for base_url in NITTER_INSTANCES:
        try:
            r = requests.get(f"{base_url}/{username}/rss", timeout=5)
            if r.status_code == 200: return True
        except: continue
    return False

# --- KEYBOARDS ---
def main_menu():
    return {
        "keyboard": [
            [{"text": "add account"}],
            [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]
        ],
        "resize_keyboard": True
    }

def mode_keyboard(selected):
    def mark(x): return f"✅ {x}" if x in selected else f"❌ {x}"
    return {"inline_keyboard": [
        [{"text": mark("posting"), "callback_data": "mode|posting"}],
        [{"text": mark("reply"), "callback_data": "mode|reply"}],
        [{"text": mark("repost"), "callback_data": "mode|repost"}],
        [{"text": "🚀 KONFIRMASI", "callback_data": "done"}]
    ]}

def remove_keyboard(accounts):
    buttons = [[{"text": f"🔴 HAPUS @{acc}", "callback_data": f"del|{acc}"}] for acc in accounts]
    buttons.append([{"text": "🔙 BATAL", "callback_data": "cancel"}])
    return {"inline_keyboard": buttons}

# --- MONITORING LOOP ---
def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                for acc, cfg in data.get("accounts", {}).items():
                    for base_url in NITTER_INSTANCES:
                        feed = feedparser.parse(f"{base_url}/{acc}/rss")
                        if feed.entries:
                            post = feed.entries[0]
                            if cfg.get("last") != post.link:
                                cfg["last"] = post.link
                                title = post.title.lower()
                                if "posting" in cfg["mode"] and "retweeted" not in title and "replying to" not in title:
                                    send(chat_id, f"📢 *POST BARU @{acc}*\n\n{post.link}")
                                elif "reply" in cfg["mode"] and "replying to" in title:
                                    send(chat_id, f"💬 *REPLY BARU @{acc}*\n\n{post.link}")
                                elif "repost" in cfg["mode"] and "retweeted" in title:
                                    send(chat_id, f"🔁 *REPOST @{acc}*\n\n{post.link}")
                            break
            save_data()
        except: pass
        time.sleep(120)

# --- BOT INTERACTION ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                # Handling Klik Tombol (Inline)
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]
                    data = cq["data"]
                    
                    if data == "check_sub":
                        if is_member(chat_id):
                            answer_callback(cq["id"], "Akses dibuka!")
                            edit(chat_id, msg_id, "✅ **AKSES DIBUKA**", None)
                            send(chat_id, "Selamat datang!", main_menu())
                        else: answer_callback(cq["id"], "Belum join!")
                        continue

                    answer_callback(cq["id"])
                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": [], "to_delete": []})
                    
                    if data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u.get("modes", []): u["modes"].remove(m)
                        else: u.setdefault("modes", []).append(m)
                        edit(chat_id, msg_id, f"⚙️ *MODE @{u.get('temp')}*", mode_keyboard(u["modes"]))
                    
                    elif data.startswith("del|"):
                        acc = data.split("|")[1]
                        if acc in u["accounts"]:
                            del u["accounts"][acc]; save_data()
                            edit(chat_id, msg_id, f"🗑️ *BERHASIL DIHAPUS*\n\nAkun @{acc} telah dihapus.", None)
                    
                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            
                            # LOGIKA PEMBERSIHAN TOTAL SETELAH KONFIRMASI
                            # 1. Hapus semua pesan sampah yang tercatat
                            for m_id in u.get("to_delete", []):
                                delete_msg(chat_id, m_id)
                            # 2. Hapus menu pemilihan mode itu sendiri
                            delete_msg(chat_id, msg_id)
                            u["to_delete"] = []
                            
                            # 3. Kirim notif sukses dengan main_menu() agar tombol tidak hilang
                            temp = send(chat_id, f"✅ @{acc} berhasil dipantau!", main_menu())
                            
                            # 4. Hapus notif sukses setelah 3 detik
                            time.sleep(3)
                            delete_msg(chat_id, temp.json()['result']['message_id'])
                    
                    elif data == "cancel":
                        u["state"] = None
                        for m_id in u.get("to_delete", []): delete_msg(chat_id, m_id)
                        delete_msg(chat_id, msg_id)
                        u["to_delete"] = []
                    continue

                # Handling Pesan Teks
                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                
                # Proteksi Channel (Owner dikecualikan)
                if not is_member(chat_id) and chat_id != str(OWNER_CHAT_ID):
                    send_lock_msg(chat_id); continue

                u = users.setdefault(chat_id, {"accounts": {}, "state": None, "to_delete": []})

                if text == "/start": 
                    send(chat_id, "🤖 *X-ALLER SYSTEM*", main_menu())
                elif text == "/id": 
                    send(chat_id, f"ID: `{chat_id}`")
                elif text == "/admin" and chat_id == str(OWNER_CHAT_ID):
                    rep = f"👑 *ADMIN DASHBOARD*\n\nUsers: {len(users)}\n"
                    for uid, ud in users.items():
                        rep += f"👤 `{uid}`: {list(ud.get('accounts', {}).keys())}\n"
                    send(chat_id, rep)

                # FITUR ADD ACCOUNT
                elif text.lower() == "add account":
                    force_reply = {"force_reply": True, "selective": True}
                    resp = send(chat_id, "👤 *MASUKKAN USERNAME*\n\nBalas dengan username X (tanpa @):", force_reply)
                    u.setdefault("to_delete", []).append(resp.json()['result']['message_id'])
                    # Juga catat pesan 'add account' milik user untuk dihapus nanti
                    u["to_delete"].append(msg["message_id"])
                
                elif "reply_to_message" in msg:
                    orig_text = msg["reply_to_message"].get("text", "")
                    if "MASUKKAN USERNAME" in orig_text:
                        username = text.replace("@", "").strip().lower()
                        # Catat pesan ketikan username user untuk dihapus nanti
                        u["to_delete"].append(msg["message_id"])

                        status = send(chat_id, f"🔍 Mengecek @{username}...")
                        if is_valid_x(username):
                            u["temp"] = username; u["modes"] = []; u["state"] = "choose"
                            edit(chat_id, status.json()['result']['message_id'], f"✅ Ditemukan!\nPilih mode:", mode_keyboard([]))
                        else:
                            edit(chat_id, status.json()['result']['message_id'], f"❌ @{username} tidak ditemukan.", None)
                            time.sleep(2)
                            delete_msg(chat_id, status.json()['result']['message_id'])
                
                elif text == "📋 List Accounts":
                    accs = u.get("accounts", {})
                    txt = "📋 *DAFTAR PANTAUAN:*\n\n" + ("\n".join([f"🔹 @{a}" for a in accs]) if accs else "Kosong.")
                    send(chat_id, txt)
                elif text == "❌ Remove Account":
                    accs = list(u.get("accounts", {}).keys())
                    if not accs: send(chat_id, "📭 Kosong.")
                    else: send(chat_id, "🗑️ Pilih akun:", remove_keyboard(accs))

        except: pass
        time.sleep(1)

# Menjalankan monitor di thread terpisah
threading.Thread(target=monitor, daemon=True).start()
bot_loop()
