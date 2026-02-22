# ==== TELEGRAM X MONITOR BOT (SUPER STABLE) ====
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
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown"}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    requests.post(f"{API}/editMessageText", data=payload)

def main_menu():
    return {"keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]], "resize_keyboard": True}

def mode_keyboard(selected):
    def mark(x): return f"☑ {x}" if x in selected else f"☐ {x}"
    return {"inline_keyboard": [[{"text": mark("posting"), "callback_data": "mode|posting"}], [{"text": mark("reply"), "callback_data": "mode|reply"}], [{"text": mark("repost"), "callback_data": "mode|repost"}], [{"text": "✅ Selesai", "callback_data": "done"}]]}

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
                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": []})
                    data = cq["data"]
                    if data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u["modes"]: u["modes"].remove(m)
                        else: u["modes"].append(m)
                        edit(chat_id, cq["message"]["message_id"], f"Pilih mode untuk @{u.get('temp')}:", mode_keyboard(u["modes"]))
                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            send(chat_id, f"✅ @{acc} berhasil ditambahkan!", main_menu())
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                # Jika menekan tombol menu saat sedang dalam 'state' tertentu, batalkan state tersebut
                if text in ["add account", "📋 List Accounts", "❌ Remove Account", "/start"]:
                    u["state"] = None

                if text == "/start":
                    send(chat_id, "🤖 *BOT MONITOR X AKTIF*", main_menu())
                elif text == "/id":
                    send(chat_id, f"ID Anda: `{chat_id}`")
                elif text.lower() == "add account":
                    u["state"] = "add"
                    send(chat_id, "Masukkan username X (tanpa @):")
                elif u["state"] == "add":
                    u["temp"] = text.replace("@", "").strip().lower()
                    u["modes"] = []; u["state"] = "choose"
                    send(chat_id, f"Pilih mode untuk @{u['temp']}:", mode_keyboard([]))
                elif text == "📋 List Accounts":
                    accs = u.get("accounts", {})
                    txt = "📋 *DAFTAR PANTAU:*\n\n" + ("\n".join([f"• @{a}" for a in accs]) if accs else "Kosong.")
                    send(chat_id, txt)
                elif text == "❌ Remove Account":
                    u["state"] = "remove"
                    send(chat_id, "Ketik username yang ingin dihapus:")
                elif u["state"] == "remove":
                    if text in u["accounts"]:
                        del u["accounts"][text]; save_data()
                        send(chat_id, f"❌ @{text} dihapus.")
                    u["state"] = None
        except: pass
        time.sleep(1)

threading.Thread(target=monitor, daemon=True).start()
bot_loop()
