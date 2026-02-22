# ==== TELEGRAM X MONITOR BOT (PROFESSIONAL UI) ====
import time, json, os, threading, requests, feedparser

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f: json.dump(users, f)

users = load_data()

def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown", "disable_web_page_preview": True}
    requests.post(f"{API}/editMessageText", data=payload)

def is_valid_x(username):
    try:
        r = requests.get(f"https://nitter.net/{username}/rss", timeout=10)
        return r.status_code == 200
    except:
        return False

def main_menu():
    return {"keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]], "resize_keyboard": True}

# --- PERBAIKAN VISUAL: WARNA HIJAU & MERAH ---
def mode_keyboard(selected):
    # Menggunakan emoji centang hijau (✅) dan silang merah (❌)
    def mark(x): return f"✅ {x}" if x in selected else f"❌ {x}"
    return {"inline_keyboard": [
        [{"text": mark("posting"), "callback_data": "mode|posting"}],
        [{"text": mark("reply"), "callback_data": "mode|reply"}],
        [{"text": mark("repost"), "callback_data": "mode|repost"}],
        [{"text": "🚀 KONFIRMASI", "callback_data": "done"}]
    ]}

def remove_keyboard(accounts):
    # Menggunakan silang merah untuk tombol hapus
    buttons = [[{"text": f"🔴 HAPUS @{acc}", "callback_data": f"del|{acc}"}] for acc in accounts]
    buttons.append([{"text": "🔙 BATAL", "callback_data": "cancel"}])
    return {"inline_keyboard": buttons}

# --- MONITORING LOOP ---
def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                for acc, cfg in data.get("accounts", {}).items():
                    feed = feedparser.parse(f"https://nitter.net/{acc}/rss")
                    if not feed.entries: continue
                    post = feed.entries[0]
                    if cfg.get("last") == post.link: continue
                    cfg["last"] = post.link
                    title = post.title.lower()
                    if "posting" in cfg["mode"] and "retweeted" not in title and "replying to" not in title:
                        send(chat_id, f"📢 *POST BARU @{acc}*\n\n{post.link}")
                    elif "reply" in cfg["mode"] and "replying to" in title:
                        send(chat_id, f"💬 *REPLY BARU @{acc}*\n\n{post.link}")
                    elif "repost" in cfg["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 *REPOST @{acc}*\n\n{post.link}")
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
                
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]
                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": []})
                    data = cq["data"]
                    
                    if data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u["modes"]: u["modes"].remove(m)
                        else: u.setdefault("modes", []).append(m)
                        edit(chat_id, msg_id, f"⚙️ *PENGATURAN MODE @{u.get('temp')}*\n\nSilakan pilih mode di bawah:", mode_keyboard(u["modes"]))
                    
                    elif data.startswith("del|"):
                        acc = data.split("|")[1]
                        if acc in u["accounts"]:
                            del u["accounts"][acc]; save_data()
                            edit(chat_id, msg_id, f"🗑️ *BERHASIL DIHAPUS*\n\nAkun @{acc} tidak lagi dipantau.", None)
                    
                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            send(chat_id, f"✅ *SUKSES!*\n\nAkun @{acc} telah ditambahkan ke sistem.", main_menu())
                    
                    elif data == "cancel":
                        u["state"] = None
                        edit(chat_id, msg_id, "❌ *DIBATALKAN*", None)
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                if text in ["add account", "📋 List Accounts", "❌ Remove Account", "/start"]:
                    u["state"] = None

                if text == "/start":
                    send(chat_id, "🤖 *X-ALLER MONITOR SYSTEM*\n\nSelamat datang di pusat kendali pemantauan akun X.", main_menu())
                
                elif text.lower() == "add account":
                    u["state"] = "add"
                    send(chat_id, "👤 *INPUT USERNAME*\n\nKetik username X yang ingin dipantau (tanpa @):")
                
                elif u["state"] == "add":
                    username = text.replace("@", "").strip().lower()
                    status_msg = send(chat_id, f"🔍 *VALIDASI*\n\nMengecek status @{username}...")
                    if is_valid_x(username):
                        u["temp"] = username
                        u["modes"] = []; u["state"] = "choose"
                        edit(chat_id, status_msg.json()['result']['message_id'], f"✅ *AKUN AKTIF*\n\nPilih mode pantauan untuk @{username}:", mode_keyboard([]))
                    else:
                        edit(chat_id, status_msg.json()['result']['message_id'], f"⚠️ *ERROR*\n\nUsername @{username} tidak ditemukan atau private.", None)
                        u["state"] = None
                
                elif text == "📋 List Accounts":
                    accs = u.get("accounts", {})
                    txt = "📋 *DAFTAR PANTAUAN ANDA*\n\n" + ("\n".join([f"🔹 @{a}" for a in accs]) if accs else "_Belum ada akun._")
                    send(chat_id, txt)
                
                elif text == "❌ Remove Account":
                    accs = list(u.get("accounts", {}).keys())
                    if not accs:
                        send(chat_id, "📭 *KOSONG*\n\nTidak ada akun dalam daftar.")
                    else:
                        send(chat_id, "🗑️ *HAPUS AKUN*\n\nKlik pada akun yang ingin dihapus:", remove_keyboard(accs))

        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
