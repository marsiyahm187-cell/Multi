# ==== TELEGRAM X MONITOR BOT (FIXED & COMPLETE) ====

import time
import json
import os
import threading
import requests
import feedparser

# Mengambil variabel dari Railway Environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID") # Ini akan berupa string

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# ================= DATA MANAGEMENT =================

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

users = load_data()

# ================= TELEGRAM FUNCTIONS =================

def send(chat_id, text, markup=None):
    url = f"{API}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        return requests.post(url, data=payload)
    except:
        return None

def edit(chat_id, msg_id, text, markup):
    url = f"{API}/editMessageText"
    payload = {
        "chat_id": str(chat_id),
        "message_id": msg_id,
        "text": text,
        "reply_markup": json.dumps(markup),
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except:
        pass

# ================= UTILS & KEYBOARDS =================

def main_menu():
    # Membuat tombol di bawah keyboard
    return {
        "keyboard": [
            [{"text": "add account"}],
            [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}]
        ],
        "resize_keyboard": True
    }

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

# ================= MONITORING LOGIC =================

def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                for acc, cfg in data.get("accounts", {}).items():
                    # Menggunakan nitter.net (atau ganti ke nitter.cz jika error)
                    url = f"https://nitter.net/{acc}/rss"
                    feed = feedparser.parse(url)
                    
                    if not feed.entries:
                        continue

                    post = feed.entries[0]
                    link = post.link
                    title = post.title.lower()

                    if cfg.get("last") == link:
                        continue

                    cfg["last"] = link

                    # Cek tipe postingan
                    if "posting" in cfg["mode"] and "retweeted" not in title and "replying to" not in title:
                        send(chat_id, f"📢 *POST BARU @{acc}*\n\n{link}")
                    elif "reply" in cfg["mode"] and "replying to" in title:
                        send(chat_id, f"💬 *REPLY BARU @{acc}*\n\n{link}")
                    elif "repost" in cfg["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 *REPOST @{acc}*\n\n{link}")
            
            save_data()
        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(120)

# ================= MAIN BOT LOOP =================

def bot_loop():
    offset = None
    print("Bot berjalan...")

    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20})
            updates = r.json()

            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1

                # 1. Handle Klik Tombol (Inline)
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
                        edit(chat_id, msg_id, f"Pilih mode untuk @{u.get('temp')}:", mode_keyboard(u["modes"]))

                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None
                            save_data()
                            send(chat_id, f"✅ Berhasil! @{acc} sekarang dipantau.")

                # 2. Handle Pesan Teks
                if "message" not in upd: continue
                msg = upd["message"]
                chat_id = str(msg["chat"]["id"])
                text = msg.get("text", "")

                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                if text == "/start":
                    send(chat_id, "🤖 *BOT MONITOR X*\n\nGunakan menu di bawah:", main_menu())

                elif text == "/id":
                    send(chat_id, f"ID Telegram Anda: `{chat_id}`\n\nMasukkan ID ini di Railway sebagai `OWNER_CHAT_ID`.")

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
                    acc_list = u.get("accounts", {})
                    if not acc_list:
                        send(chat_id, "Belum ada akun dipantau.")
                    else:
                        txt = "📋 *AKUN DIPANTAU:*\n\n"
                        for a in acc_list: txt += f"• @{a}\n"
                        send(chat_id, txt)

                elif text == "❌ Remove Account":
                    u["state"] = "remove"
                    send(chat_id, "Ketik username yang ingin dihapus:")

                elif u.get("state") == "remove":
                    acc = text.replace("@", "").strip().lower()
                    if acc in u["accounts"]:
                        del u["accounts"][acc]
                        save_data()
                        send(chat_id, f"❌ @{acc} dihapus.")
                    u["state"] = None

                elif text == "/admin":
                    if chat_id == OWNER_CHAT_ID:
                        send(chat_id, "👑 *WELCOME ADMIN*\n\nBot berjalan normal.")
                    else:
                        send(chat_id, "🚫 Anda bukan admin.")

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    bot_loop()
