import time
import feedparser
import requests
import os
import json
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

DATA_FILE = "users.json"


# ================= LOAD & SAVE =================

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


users = load_data()


# ================= TELEGRAM SEND =================

def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)

    requests.post(url, data=payload)


# ================= VALIDASI USERNAME X =================

def check_x_username(username):
    try:
        rss = f"https://nitter.net/{username}/rss"
        feed = feedparser.parse(rss)
        return bool(feed.entries)
    except:
        return False


# ================= MENU USER =================

def main_menu(chat_id):
    keyboard = {
        "keyboard": [
            ["➕ Add Account"],
            ["📋 List Accounts"],
            ["❌ Remove Account"],
            ["ℹ️ Help", "🚀 Update"]
        ],
        "resize_keyboard": True
    }

    send(chat_id, "🤖 Bot siap digunakan!", keyboard)


# ================= ADMIN MENU =================

def admin_menu(chat_id):
    keyboard = {
        "keyboard": [
            ["📊 Statistik Bot"],
            ["👥 List User"],
            ["📡 List Pantauan"],
            ["📢 Broadcast"],
            ["⬅️ Menu Utama"]
        ],
        "resize_keyboard": True
    }

    send(chat_id, "⚙️ ADMIN DASHBOARD", keyboard)


# ================= MONITOR X =================

def monitor():
    while True:
        try:
            for chat_id, data in users.items():
                for username, config in data.get("accounts", {}).items():

                    rss = f"https://nitter.net/{username}/rss"
                    feed = feedparser.parse(rss)

                    if not feed.entries:
                        continue

                    latest = feed.entries[0]
                    link = latest.link
                    title = latest.title.lower()

                    if config.get("last") == link:
                        continue

                    config["last"] = link

                    if "posting" in config["mode"]:
                        send(chat_id, f"📢 Post @{username}\n{link}")

                    if "reply" in config["mode"] and "replying to" in title:
                        send(chat_id, f"💬 Reply @{username}\n{link}")

                    if "repost" in config["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 Repost @{username}\n{link}")

            save_data(users)

        except Exception as e:
            print("Monitor error:", e)

        time.sleep(90)


# ================= BOT LOOP =================

def bot_loop():
    offset = None

    while True:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        res = requests.get(url, params={"offset": offset}).json()

        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "")

            # USER BARU
            if chat_id not in users:
                users[chat_id] = {"accounts": {}, "state": None}
                save_data(users)

                send(
                    OWNER_CHAT_ID,
                    f"👤 User baru menggunakan bot\nID: {chat_id}"
                )

            # START
            if text == "/start":
                main_menu(chat_id)

            # ADMIN
            elif text == "/admin" and chat_id == OWNER_CHAT_ID:
                admin_menu(chat_id)

            elif text == "⬅️ Menu Utama":
                main_menu(chat_id)

            # ADD ACCOUNT
            elif text == "➕ Add Account":
                users[chat_id]["state"] = "add"
                send(chat_id, "Masukkan username X tanpa @")

            elif users[chat_id]["state"] == "add":
                username = text.replace("@", "").lower().strip()

                if not check_x_username(username):
                    send(chat_id, f"❌ Username @{username} tidak ditemukan.")
                    continue

                users[chat_id]["temp"] = username
                users[chat_id]["modes"] = []
                users[chat_id]["state"] = "choose"

                keyboard = {
                    "keyboard": [
                        ["Posting"],
                        ["Reply/Komen"],
                        ["Repost"],
                        ["✅ Selesai"]
                    ],
                    "resize_keyboard": True
                }

                send(chat_id, f"Pilih mode pantau @{username}", keyboard)

            elif users[chat_id]["state"] == "choose":

                if text == "✅ Selesai":
                    u = users[chat_id]["temp"]

                    users[chat_id]["accounts"][u] = {
                        "mode": users[chat_id]["modes"],
                        "last": None
                    }

                    users[chat_id]["state"] = None
                    save_data(users)

                    send(chat_id, f"✅ @{u} berhasil ditambahkan")
                    main_menu(chat_id)

                else:
                    mapping = {
                        "Posting": "posting",
                        "Reply/Komen": "reply",
                        "Repost": "repost"
                    }

                    if text in mapping:
                        users[chat_id]["modes"].append(mapping[text])
                        send(chat_id, f"{text} dipilih")

            # LIST ACCOUNT
            elif text == "📋 List Accounts":
                accs = users[chat_id]["accounts"]
                if not accs:
                    send(chat_id, "Belum ada akun.")
                else:
                    daftar = "\n".join(
                        [f"@{u} → {v['mode']}" for u, v in accs.items()]
                    )
                    send(chat_id, daftar)

            # REMOVE
            elif text == "❌ Remove Account":
                users[chat_id]["state"] = "remove"
                send(chat_id, "Username mana dihapus?")

            elif users[chat_id]["state"] == "remove":
                username = text.replace("@", "")
                users[chat_id]["accounts"].pop(username, None)
                users[chat_id]["state"] = None
                save_data(users)

                send(chat_id, "Dihapus.")
                main_menu(chat_id)

            # HELP
            elif text == "ℹ️ Help":
                send(chat_id,
                     "Cara pakai:\n"
                     "1️⃣ Add Account\n"
                     "2️⃣ Masukkan username\n"
                     "3️⃣ Pilih mode\n"
                     "4️⃣ Selesai")

            # UPDATE
            elif text == "🚀 Update":
                send(chat_id,
                     "🚀 Update terbaru:\n"
                     "• Monitor posting\n"
                     "• Monitor reply\n"
                     "• Monitor repost\n"
                     "• Dashboard admin")

            # ADMIN FEATURE
            elif text == "📊 Statistik Bot" and chat_id == OWNER_CHAT_ID:
                send(chat_id,
                     f"User: {len(users)}")

            elif text == "👥 List User" and chat_id == OWNER_CHAT_ID:
                send(chat_id, "\n".join(users.keys()))

            elif text == "📡 List Pantauan" and chat_id == OWNER_CHAT_ID:
                data = []
                for uid, d in users.items():
                    for acc in d.get("accounts", {}):
                        data.append(f"{uid} → @{acc}")
                send(chat_id, "\n".join(data) if data else "Kosong")

            elif text == "📢 Broadcast" and chat_id == OWNER_CHAT_ID:
                users[chat_id]["state"] = "broadcast"
                send(chat_id, "Kirim pesan broadcast")

            elif users[chat_id].get("state") == "broadcast":
                for uid in users:
                    send(uid, f"📢 INFO BOT:\n{text}")
                users[chat_id]["state"] = None
                send(chat_id, "Broadcast terkirim")

        time.sleep(3)


threading.Thread(target=monitor).start()
bot_loop()
