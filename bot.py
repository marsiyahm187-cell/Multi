==== TELEGRAM rahasia X MONITOR BOT (FINAL VERSION) ====

import time import json import os import threading import requests
import feedparser

BOT_TOKEN = os.getenv(“BOT_TOKEN”) 
OWNER_CHAT_ID =str(os.getenv(“OWNER_CHAT_ID”))

API = f”https://api.telegram.org/bot{BOT_TOKEN}” DATA_FILE =“users.json”

================= DATA =================

def load_data(): try: with open(DATA_FILE, “r”) as f: return
json.load(f) except: return {}

def save_data(): with open(DATA_FILE, “w”) as f: json.dump(users, f)

users = load_data()

================= TELEGRAM =================

def send(chat_id, text, markup=None): data = {“chat_id”: chat_id,
“text”: text} if markup: data[“reply_markup”] = json.dumps(markup)
requests.post(f”{API}/sendMessage”, data=data)

def edit(chat_id, msg_id, text, markup):
requests.post(f”{API}/editMessageText”, data={ “chat_id”: chat_id,
“message_id”: msg_id, “text”: text, “reply_markup”: json.dumps(markup)
})

================= VALIDASI USERNAME X =================

def check_x(username): try: username = username.strip().lower() r =
requests.get( f”https://nitter.net/{username}“, headers={”User-Agent”:
“Mozilla/5.0”}, timeout=10 ) if r.status_code != 200: return False page
= r.text.lower() return “tweets” in page and “profile” in page except:
return False

================= INLINE MODE SELECT =================

def mode_keyboard(selected): def mark(x): return f”☑ {x}” if x in
selected else f”☐ {x}”

    return {
        "inline_keyboard": [
            [{"text": mark("posting"), "callback_data": "mode|posting"}],
            [{"text": mark("reply"), "callback_data": "mode|reply"}],
            [{"text": mark("repost"), "callback_data": "mode|repost"}],
            [{"text": "✅ Selesai", "callback_data": "done"}]
        ]
    }

================= LIST ACCOUNT PAGINATION =================

def show_account_page(chat_id): u = users[chat_id] accounts =
list(u[“accounts”].items()) per_page = 3

    page = u.get("page", 0)
    start = page * per_page
    end = start + per_page
    subset = accounts[start:end]

    total_pages = max(1, (len(accounts)-1)//per_page + 1)

    mode_icon = {
        "posting": "📢",
        "reply": "💬",
        "repost": "🔁"
    }

    text = "✨ AKUN DIPANTAU\n\n"

    for username, cfg in subset:
        text += f"👤 @{username}\n"
        for m in cfg["mode"]:
            text += f"   {mode_icon.get(m)} {m.capitalize()}\n"
        text += "\n"

    text += f"📄 Page {page+1}/{total_pages}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⬅️", "callback_data": "prev_page"},
                {"text": "➡️", "callback_data": "next_page"}
            ]
        ]
    }

    send(chat_id, text, keyboard)

================= MONITOR X =================

def monitor(): while True: try: for chat_id, data in users.items(): for
acc, cfg in data.get(“accounts”, {}).items():

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

                    if "reply" in cfg["mode"] and "replying to" in title:
                        send(chat_id, f"💬 REPLY @{acc}\n{link}")

                    if "repost" in cfg["mode"] and "retweeted" in title:
                        send(chat_id, f"🔁 REPOST @{acc}\n{link}")

            save_data()

        except Exception as e:
            print("Monitor error:", e)

        time.sleep(90)

================= BOT LOOP =================

def bot_loop(): offset = None

    while True:
        updates = requests.get(f"{API}/getUpdates",
                               params={"offset": offset}).json()

        for upd in updates.get("result", []):
            offset = upd["update_id"] + 1

            if "callback_query" in upd:
                cq = upd["callback_query"]
                chat_id = str(cq["message"]["chat"]["id"])
                msg_id = cq["message"]["message_id"]
                data = cq["data"]

                u = users.setdefault(chat_id,
                                     {"accounts": {}, "state": None})

                if data.startswith("mode|"):
                    mode = data.split("|")[1]

                    if mode in u["modes"]:
                        u["modes"].remove(mode)
                    else:
                        u["modes"].append(mode)

                    edit(chat_id, msg_id,
                         f"Pilih mode @{u['temp']}",
                         mode_keyboard(u["modes"]))

                elif data == "done":
                    acc = u["temp"]
                    u["accounts"][acc] = {
                        "mode": u["modes"],
                        "last": None
                    }
                    u["state"] = None
                    save_data()

                    send(chat_id,
                         f"✅ @{acc} ditambahkan\n\n"
                         + "\n".join(f"• {m}" for m in u["modes"]))

                elif data == "next_page":
                    u["page"] = u.get("page", 0) + 1
                    show_account_page(chat_id)

                elif data == "prev_page":
                    if u.get("page", 0) > 0:
                        u["page"] -= 1
                    show_account_page(chat_id)

                elif data == "admin_stats":
                    total_users = len(users)
                    total_accounts = sum(len(v["accounts"])
                                         for v in users.values())
                    send(chat_id,
                         f"📊 BOT STATS\n\n"
                         f"👥 Users: {total_users}\n"
                         f"📡 Accounts: {total_accounts}")

                elif data == "admin_users":
                    send(chat_id,
                         "👥 USER LIST\n\n"
                         + "\n".join(users.keys()))

                elif data == "admin_watch":
                    rows = []
                    for uid, d in users.items():
                        for acc in d["accounts"]:
                            rows.append(f"{uid} → @{acc}")
                    send(chat_id, "\n".join(rows) if rows else "Kosong")

                elif data == "admin_broadcast":
                    u["state"] = "broadcast"
                    send(chat_id, "📢 Ketik pesan broadcast")

            if "message" not in upd:
                continue

            msg = upd["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "")

            if chat_id not in users:
                users[chat_id] = {"accounts": {}, "state": None}
                save_data()
                send(OWNER_CHAT_ID, f"👤 User baru: {chat_id}")

            u = users[chat_id]

            if text == "/start":
                send(chat_id,
                     "🤖 BOT MONITOR X\n\n"
                     "Gunakan:\n"
                     "Add Account\n"
                     "📋 List Accounts\n"
                     "❌ Remove Account")

            elif text.lower() == "add account":
                u["state"] = "add"
                send(chat_id, "Masukkan username X")

            elif u["state"] == "add":
                username = text.replace("@", "").lower()

                if not check_x(username):
                    send(chat_id,
                         f"❌ Username @{username} tidak ditemukan")
                    continue

                u["temp"] = username
                u["modes"] = []
                u["state"] = "choose"

                send(chat_id,
                     f"Pilih mode @{username}",
                     mode_keyboard([]))

            elif text == "📋 List Accounts":
                u["page"] = 0
                show_account_page(chat_id)

            elif text == "❌ Remove Account":
                u["state"] = "remove"
                send(chat_id, "Kirim username yg dihapus")

            elif u["state"] == "remove":
                acc = text.replace("@", "").lower()
                u["accounts"].pop(acc, None)
                u["state"] = None
                save_data()
                send(chat_id, f"❌ @{acc} dihapus")

            elif text == "/admin":
                if chat_id != OWNER_CHAT_ID:
                    send(chat_id, "🚫 Bukan admin.")
                else:
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📊 Statistik",
                              "callback_data": "admin_stats"}],
                            [{"text": "👥 User",
                              "callback_data": "admin_users"}],
                            [{"text": "📡 Pantauan",
                              "callback_data": "admin_watch"}],
                            [{"text": "📢 Broadcast",
                              "callback_data": "admin_broadcast"}]
                        ]
                    }
                    send(chat_id, "👑 ADMIN DASHBOARD", keyboard)

            elif u.get("state") == "broadcast" \
                    and chat_id == OWNER_CHAT_ID:

                for uid in users:
                    send(uid, f"📢 INFO:\n{text}")

                u["state"] = None
                send(chat_id, "✅ Broadcast terkirim")

        time.sleep(3)

threading.Thread(target=monitor).start() bot_loop()
