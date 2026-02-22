# ==== TELEGRAM X MONITOR BOT (CLEAN & CONSISTENT VERSION) ====
import time, json, os, threading, requests, feedparser

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

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

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    requests.post(f"{API}/editMessageText", data=payload)

def delete_msg(chat_id, msg_id):
    requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

def answer_callback(callback_id, text=None):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text})

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

def remove_select_keyboard(accounts, selected):
    # Logika centang untuk penghapusan massal/pilihan
    buttons = []
    for acc in accounts:
        mark = "✅" if acc in selected else "❌"
        buttons.append([{"text": f"{mark} @{acc}", "callback_data": f"rem_sel|{acc}"}])
    buttons.append([{"text": "🗑️ KONFIRMASI HAPUS", "callback_data": "rem_confirm"}])
    buttons.append([{"text": "🔙 BATAL", "callback_data": "cancel"}])
    return {"inline_keyboard": buttons}

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
                    u = users.setdefault(chat_id, {"accounts": {}, "state": None, "modes": [], "rem_queue": []})
                    
                    # LOGIKA ADD ACCOUNT
                    if data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u.get("modes", []): u["modes"].remove(m)
                        else: u.setdefault("modes", []).append(m)
                        edit(chat_id, msg_id, f"⚙️ *MODE @{u.get('temp')}*", mode_keyboard(u["modes"]))
                    
                    elif data == "done":
                        acc = u.get("temp")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            delete_msg(chat_id, msg_id)
                            send(chat_id, f"✅ @{acc} berhasil dipantau!", main_menu())
                    
                    # LOGIKA REMOVE ACCOUNT (PILIHAN CENTANG)
                    elif data.startswith("rem_sel|"):
                        acc = data.split("|")[1]
                        if acc in u.get("rem_queue", []): u["rem_queue"].remove(acc)
                        else: u.setdefault("rem_queue", []).append(acc)
                        edit(chat_id, msg_id, "🗑️ *PILIH AKUN UNTUK DIHAPUS:*", remove_select_keyboard(list(u["accounts"].keys()), u["rem_queue"]))

                    elif data == "rem_confirm":
                        removed = []
                        for acc in u.get("rem_queue", []):
                            if acc in u["accounts"]:
                                del u["accounts"][acc]
                                removed.append(f"@{acc}")
                        
                        if removed:
                            save_data()
                            delete_msg(chat_id, msg_id)
                            send(chat_id, f"🗑️ {', '.join(removed)} berhasil dihapus!", main_menu())
                        else:
                            answer_callback(cq["id"], "Pilih minimal satu akun!")
                        u["rem_queue"] = []

                    elif data == "cancel":
                        u["state"] = None; u["rem_queue"] = []
                        delete_msg(chat_id, msg_id)
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                u = users.setdefault(chat_id, {"accounts": {}, "state": None})

                if text == "/start": send(chat_id, "🤖 *X-ALLER SYSTEM*", main_menu())
                
                elif text.lower() == "add account":
                    u["state"] = "add"
                    send(chat_id, "👤 *MASUKKAN USERNAME*\n\nKetik username X (tanpa @):")
                
                elif u["state"] == "add":
                    if text in ["add account", "📋 List Accounts", "❌ Remove Account"]:
                        u["state"] = None; continue
                    username = text.replace("@", "").strip().lower()
                    u["temp"] = username; u["modes"] = []; u["state"] = "choose"
                    send(chat_id, f"⚙️ *MODE @{username}*", mode_keyboard([]))
                
                elif text == "📋 List Accounts":
                    accs = u.get("accounts", {})
                    send(chat_id, "📋 *DAFTAR PANTAUAN:*\n\n" + ("\n".join([f"🔹 @{a}" for a in accs]) if accs else "Kosong."))

                elif text == "❌ Remove Account":
                    accs = list(u.get("accounts", {}).keys())
                    if not accs:
                        send(chat_id, "📭 Daftar pantau kosong.")
                    else:
                        u["rem_queue"] = []
                        send(chat_id, "🗑️ *PILIH AKUN UNTUK DIHAPUS:*", remove_select_keyboard(accs, []))
        except: pass
        time.sleep(1)

bot_loop()
