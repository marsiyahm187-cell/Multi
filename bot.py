# ==== TELEGRAM X MONITOR BOT (FIXED VERSION) ====

import time
import json
import os
import threading
import requests
import feedparser

# Perbaikan tanda kutip dan import
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = str(os.getenv("OWNER_CHAT_ID"))

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# ================= DATA =================

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

# Inisialisasi data
users = load_data()

# ================= TELEGRAM =================

def send(chat_id, text, markup=None):
    url = f"{API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error send: {e}")

def edit(chat_id, msg_id, text, markup):
    url = f"{API}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "reply_markup": json.dumps(markup)
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error edit: {e}")

# ================= VALIDASI USERNAME X =================

def check_x(username):
    try:
        username = username.strip().lower()
        # Menggunakan nitter.cz sebagai alternatif jika nitter.net tumbang
        r = requests.get(
            f"https://nitter.net/{username}", 
            headers={"User-Agent": "Mozilla/5.0"}, 
            timeout=10
        )
        if r.status_code != 200:
            return False
        page = r.text.lower()
        return "tweets" in page
    except:
        return False

# ================= KEYBOARD & UI =================

def mode_keyboard(selected):
    def mark(x):
        return f"☑ {x}" if x in selected else f"☐ {x}"

    return {
        "inline_keyboard": [
            [{"text": mark("posting"), "callback_data": "mode|posting"}],
            [{"text": mark("reply"), "callback_data": "mode|reply"}],
            [{"text": mark("repost"), "callback_data": "mode|repost"}],
            [{"text": "✅ Selesai", "callback_data": "done"}]
        ]
    }

def show_account_page(chat_id):
    if chat_id not in users or not users[chat_id].get("accounts"):
        send(chat_id, "Belum ada akun yang dipantau.")
        return

    u = users[chat_id]
    accounts = list(u["accounts"].items())
    per_page = 3
    page = u.get("page", 0)
    
    total_pages = max(1, (len(accounts)-1)//per_page + 1)
    if page >= total_pages: page = 0
    
    start = page * per_page
    subset = accounts[start:start+per_page]

    mode_icon = {"posting": "📢", "reply": "💬", "repost": "🔁"}
    text = "✨ AKUN DIPANTAU\n\n"

    for username, cfg in subset:
        text += f"👤 @{username}\n"
        for m in cfg.get("mode", []):
            text += f"   {mode_icon.get(m)} {m.capitalize()}\n"
        text += "\n"

    text += f"📄 Page {page+1}/{total_pages}"

    keyboard = {
        "inline_keyboard": [[
            {"text": "⬅️", "callback_data": "prev_page"},
            {"text": "➡️", "callback_data": "next_page"}
        ]]
    }
    send(chat_id, text, keyboard)

# ================= MONITOR X =================

def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                for acc, cfg in data.get("accounts", {}).items():
                    feed = feedparser.parse(f"https://nitter.net/{acc}/rss")
                    if not feed.entries:
                        continue

                    post = feed.entries[0]
                    link = post.link
                    title = post.title.lower()

                    if cfg.get("last") == link:
                        continue

                    cfg["last"] = link

                    if "posting" in cfg["mode"]:
                        send(chat_id, f"📢 POST @{acc}\n{link}")
                    elif "reply" in cfg["mode"] and "replying to" in title:
                        send(chat_id, f"💬 REPLY @{acc}\n{link}")
                    elif "repost" in cfg["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 REPOST @{acc}\n{link}")
            
            save_data()
        except Exception as e:
            print("Monitor error:", e)
        time.sleep(90)

# ================= BOT LOOP =================

def bot_loop():
    offset = None
    print("Bot is running...")

    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset}, timeout=20)
            updates = r.json()

            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1

                # Handle Callback Query
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]
                    data = cq["data"]

                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": []})

                    if data.startswith("mode|"):
                        mode = data.split("|")[1]
                        if mode in u.get("modes", []):
                            u["modes"].remove(mode)
                        else:
                            u.setdefault("modes", []).append(mode)
                        
                        edit(chat_id, msg_id, f"Pilih mode @{u.get('temp')}", mode_keyboard(u["modes"]))

                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None
                            save_data()
                            send(chat_id, f"✅ @{acc} ditambahkan")

                    elif data == "next_page":
                        u["page"] = u.get("page", 0) + 1
                        show_account_page(chat_id)
                    
                    elif data == "prev_page":
                        u["page"] = max(0, u.get("page", 0) - 1)
                        show_account_page(chat_id)

                # Handle Message
                if "message" not in upd: continue
                msg = upd["message"]
                chat_id = str(msg["chat"]["id"])
                text = msg.get("text", "")

                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                if text == "/start":
                    send(chat_id, "🤖 BOT MONITOR X\n\nKetik:\n- add account\n- 📋 List Accounts\n- ❌ Remove Account")

                elif text.lower() == "add account":
                    u["state"] = "add"
                    send(chat_id, "Masukkan username X (tanpa @):")

                elif u.get("state") == "add":
                    username = text.replace("@", "").strip().lower()
                    u["temp"] = username
                    u["modes"] = []
                    u["state"] = "choose"
                    send(chat_id, f"Pilih mode untuk @{username}:", mode_keyboard([]))

                elif text == "📋 List Accounts":
                    u["page"] = 0
                    show_account_page(chat_id)

                elif text == "❌ Remove Account":
                    u["state"] = "remove"
                    send(chat_id, "Kirim username yang ingin dihapus:")

                elif u.get("state") == "remove":
                    acc = text.replace("@", "").strip().lower()
                    if acc in u["accounts"]:
                        del u["accounts"][acc]
                        save_data()
                        send(chat_id, f"❌ @{acc} dihapus")
                    u["state"] = None

        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    bot_loop()
