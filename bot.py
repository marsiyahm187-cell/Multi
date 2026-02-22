import time
import feedparser
import requests
import os
import json
import threading

BOT_TOKEN = os.getenv("8367645781:AAEwJi8IRRnwNf1MABWiWHjXgMiU0hv6pE0")

DATA_FILE = "users.json"


# ===== LOAD / SAVE DATA =====
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


# ===== TELEGRAM SEND =====
def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)

    requests.post(url, data=payload)


# ===== UI BUTTON MENU =====
def main_menu(chat_id):
    keyboard = {
        "keyboard": [
            ["➕ Add Account"],
            ["📋 List Accounts"],
            ["❌ Remove Account"]
        ],
        "resize_keyboard": True
    }

    send(chat_id, "🤖 Bot aktif!\nPilih menu:", keyboard)


# ===== TELEGRAM UPDATES =====
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}

    if offset:
        params["offset"] = offset

    r = requests.get(url, params=params)
    return r.json()


# ===== CHECK X POSTS =====
def monitor():
    while True:
        try:
            for chat_id in users:
                for username in users[chat_id]["accounts"]:
                    rss = f"https://nitter.net/{username}/rss"
                    feed = feedparser.parse(rss)

                    if feed.entries:
                        latest = feed.entries[0].link

                        if users[chat_id]["last"].get(username) != latest:
                            users[chat_id]["last"][username] = latest
                            send(chat_id, f"🚨 New Post @{username}\n{latest}")

            save_data(users)

        except Exception as e:
            print("Monitor error:", e)

        time.sleep(60)


# ===== COMMAND LISTENER =====
def bot_loop():
    offset = None

    while True:
        updates = get_updates(offset)

        if updates["result"]:
            for upd in updates["result"]:
                offset = upd["update_id"] + 1

                msg = upd.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id"))
                text = msg.get("text", "")

                if chat_id not in users:
                    users[chat_id] = {
                        "accounts": [],
                        "last": {},
                        "state": None
                    }

                # START
                if text == "/start":
                    main_menu(chat_id)

                # ADD MENU
                elif text == "➕ Add Account":
                    users[chat_id]["state"] = "add"
                    send(chat_id, "Kirim username X tanpa @")

                # REMOVE MENU
                elif text == "❌ Remove Account":
                    users[chat_id]["state"] = "remove"
                    send(chat_id, "Kirim username yang mau dihapus")

                # LIST
                elif text == "📋 List Accounts":
                    accs = users[chat_id]["accounts"]
                    if accs:
                        send(chat_id, "Dipantau:\n" + "\n".join(accs))
                    else:
                        send(chat_id, "Belum ada akun.")

                # ADD USERNAME
                elif users[chat_id]["state"] == "add":
                    username = text.replace("@", "")
                    users[chat_id]["accounts"].append(username)
                    users[chat_id]["state"] = None
                    save_data(users)
                    send(chat_id, f"✅ @{username} ditambahkan")
                    main_menu(chat_id)

                # REMOVE USERNAME
                elif users[chat_id]["state"] == "remove":
                    username = text.replace("@", "")
                    if username in users[chat_id]["accounts"]:
                        users[chat_id]["accounts"].remove(username)
                        send(chat_id, f"❌ @{username} dihapus")
                    else:
                        send(chat_id, "Akun tidak ditemukan.")

                    users[chat_id]["state"] = None
                    save_data(users)
                    main_menu(chat_id)


threading.Thread(target=monitor).start()
bot_loop()
