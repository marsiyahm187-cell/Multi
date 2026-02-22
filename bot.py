import time, json, os, threading, requests, feedparser

# Variabel Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# Konfigurasi Channel
CHANNEL_ID = "@xallertch"
CHANNEL_LINK = "https://t.me/xallertch"

# Nitter Mirror (Paling Stabil)
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

# --- FUNGSI MEMBER ---
def is_member(user_id):
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=5).json()
        status = r.get("result", {}).get("status", "")
        return status in ["creator", "administrator", "member"]
    except: return True

def send_lock_msg(chat_id):
    kb = {"inline_keyboard": [[{"text": "📢 Gabung Channel", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
    send(chat_id, "⚠️ **AKSES TERKUNCI**\n\nSilakan bergabung ke channel kami untuk mengaktifkan bot.", kb)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    requests.post(f"{API}/editMessageText", data=payload)

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
    return {"keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]], "resize_keyboard": True}

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
                    answer_callback(cq["id"])
                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": []})
                    
                    if data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u.get("modes", []): u["modes"].remove(m)
                        else: u.setdefault("modes", []).append(m)
                        edit(chat_id, msg_id, f"⚙️ *MODE @{u.get('temp')}*", mode_keyboard(u["modes"]))
                    elif data.startswith("del|"):
                        acc = data.split("|")[1]
                        if acc in u["accounts"]:
                            del u["accounts"][acc]; save_data()
                            edit(chat_id, msg_id, f"🗑️ @{acc} dihapus.", None)
                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            send(chat_id, f"✅ @{acc} berhasil dipantau!", main_menu())
                    elif data == "cancel":
                        u["state"] = None
                        edit(chat_id, msg_id, "❌ *DIBATALKAN*", None)
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                
                if not is_member(chat_id) and chat_id != str(OWNER_CHAT_ID):
                    send_lock_msg(chat_id); continue

                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                # --- FIX UTAMA: JIKA TEKS ADALAH PERINTAH MENU, RESET STATE ---
                if text in ["add account", "📋 List Accounts", "❌ Remove Account", "/start", "/admin"]:
                    u["state"] = None

                if text == "/start": send(chat_id, "🤖 *X-ALLER SYSTEM*", main_menu())
                elif text == "/id": send(chat_id, f"ID: `{chat_id}`")
                elif text == "/admin" and chat_id == str(OWNER_CHAT_ID):
                    rep = f"👑 *ADMIN*\nUsers: {len(users)}\n"
                    for uid, ud in users.items():
                        rep += f"👤 `{uid}`: {list(ud.get('accounts', {}).keys())}\n"
                    send(chat_id, rep)

                elif text.lower() == "add account":
                    u["state"] = "add"
                    send(chat_id, "👤 *MASUKKAN USERNAME*\n\nKetik username X (tanpa @):")
                
                elif u["state"] == "add":
                    # Bot hanya mengecek jika state benar-benar 'add'
                    username = text.replace("@", "").strip().lower()
                    status = send(chat_id, f"🔍 Mengecek @{username}...")
                    if is_valid_x(username):
                        u["temp"] = username; u["modes"] = []; u["state"] = "choose"
                        edit(chat_id, status.json()['result']['message_id'], f"✅ Ditemukan!\nPilih mode:", mode_keyboard([]))
                    else:
                        edit(chat_id, status.json()['result']['message_id'], f"❌ @{username} tidak ditemukan.", None)
                        u["state"] = None # Reset state agar tidak loop mengecek
                
                elif text == "📋 List Accounts":
                    accs = u.get("accounts", {})
                    txt = "📋 *DAFTAR PANTAUAN:*\n\n" + ("\n".join([f"🔹 @{a}" for a in accs]) if accs else "Kosong.")
                    send(chat_id, txt)
                elif text == "❌ Remove Account":
                    accs = list(u.get("accounts", {}).keys())
                    if not accs: send(chat_id, "📭 Kosong.")
                    else: send(chat_id, "🗑️ Pilih akun yang ingin dihapus:", remove_keyboard(accs))

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
