import time
import feedparser
import requests
import os
import json
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # chat id kamu sendiri

DATA_FILE = "users.json"


# LOAD DATA
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


# SEND TELEGRAM
def send(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)

    requests.post(url, data=payload)


# MENU UTAMA
def menu(chat_id):
    keyboard = {
        "keyboard": [
            ["➕ Add Account"],
            ["📋 List Accounts"],
            ["❌ Remove Account"]
        ],
        "resize_keyboard": True
    }

    send(chat_id, "Pilih menu:", keyboard)


# PILIH FITUR MONITOR
def monitor_option(chat_id, username):
    keyboard = {
        "keyboard": [
            ["Posting"],
            ["Reply/Komen"],
            ["Repost"],
            ["✅ Selesai"]
        ],
        "resize_keyboard": True
    }

    users[chat_id]["temp_user"] = username
    users[chat_id]["state"] = "choose"
    save_data(users)

    send(chat_id, f"Pilih yang ingin dipantau @{username}", keyboard)


# MONITOR X POSTS
def monitor():
    while True:
        try:
            for chat_id in users:
                for acc, config in users[chat_id].get("accounts", {}).items():

                    rss = f"https://nitter.net/{acc}/rss"
                    feed = feedparser.parse(rss)

                    if not feed.entries:
                        continue

                    latest = feed.entries[0]
                    link = latest.link
                    title = latest.title.lower()

                    last = config.get("last")

                    if last == link:
                        continue

                    config["last"] = link

                    # FILTER
                    if "posting" in config["mode"]:
                        send(chat_id, f"📢 Post @{acc}\n{link}")

                    if "reply" in config["mode"] and "replying to" in title:
                        send(chat_id, f"💬 Reply @{acc}\n{link}")

                    if "repost" in config["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 Repost @{acc}\n{link}")

            save_data(users)

        except Exception as e:
            print("Monitor error:", e)

        time.sleep(90)


# TELEGRAM LISTENER
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

            # USER BARU → notif owner
            if chat_id not in users:
                users[chat_id] = {"accounts": {}, "state": None}
                save_data(users)

                send(
                    OWNER_CHAT_ID,
                    f"👤 User baru pakai bot:\nID: {chat_id}"
                )

            # START
            if text == "/start":
                menu(chat_id)

            # ADD ACCOUNT
            elif text == "➕ Add Account":
                users[chat_id]["state"] = "add"
                send(chat_id, "Masukkan username X tanpa @")

            elif users[chat_id]["state"] == "add":
                username = text.replace("@", "")
                monitor_option(chat_id, username)

            # PILIH MODE
            elif users[chat_id]["state"] == "choose":

                if text == "✅ Selesai":
                    u = users[chat_id]["temp_user"]

                    users[chat_id]["accounts"][u] = {
                        "mode": users[chat_id].get("modes", []),
                        "last": None
                    }

                    users[chat_id]["modes"] = []
                    users[chat_id]["state"] = None
                    save_data(users)

                    send(chat_id, f"✅ @{u} ditambahkan")
                    menu(chat_id)

                else:
                    mode_map = {
                        "Posting": "posting",
                        "Reply/Komen": "reply",
                        "Repost": "repost"
                    }

                    users[chat_id].setdefault("modes", [])
                    users[chat_id]["modes"].append(mode_map[text])

                    send(chat_id, f"{text} dipilih")

            # LIST
            elif text == "📋 List Accounts":
                accs = users[chat_id]["accounts"]
                send(chat_id, str(accs) if accs else "Kosong")

            # REMOVE
            elif text == "❌ Remove Account":
                users[chat_id]["state"] = "remove"
                send(chat_id, "Username mana dihapus?")

            elif users[chat_id]["state"] == "remove":
                username = text.replace("@", "")
                users[chat_id]["accounts"].pop(username, None)
                users[chat_id]["state"] = None
                save_data(users)

                send(chat_id, "Dihapus")
                menu(chat_id)

        time.sleep(3)


threading.Thread(target=monitor).start()
bot_loop()
