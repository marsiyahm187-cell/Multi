import time, json, os, threading, requests, feedparser, datetime

# ==== KONFIGURASI ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

CHANNEL_ID = "@xallertch"
CHANNEL_LINK = "https://t.me/xallertch"
ADMIN_PEMBELIAN = "@Allertnow"

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

# --- FUNGSI VALIDASI ---
def is_owner(msg):
    # Mendukung pengecekan dari objek message maupun callback_query
    from_user = msg.get("from", msg.get("chat", {}))
    chat_id = str(from_user.get("id", ""))
    username = from_user.get("username", "").lower() if from_user.get("username") else ""
    return chat_id == str(OWNER_CHAT_ID) or username == OWNER_USERNAME.lower()

def is_member(user_id, msg=None):
    if msg and is_owner(msg): return True
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("ok"):
            status = r.get("result", {}).get("status", "")
            return status in ["creator", "administrator", "member"]
        return False
    except: return True

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    return requests.post(f"{API}/editMessageText", data=payload)

def delete_msg(chat_id, msg_id):
    return requests.post(f"{API}/deleteMessage", data={"chat_id": str(chat_id), "message_id": msg_id})

def answer_callback(callback_id, text=None, alert=False):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text, "show_alert": alert})

# --- KEYBOARDS ---
def main_menu(user_id, owner_access=False):
    u = users.get(str(user_id), {})
    if owner_access: status_text = "👑 MASTER OWNER"
    else:
        join_date = u.get("join_date")
        days = 30
        if join_date:
            jd = datetime.datetime.strptime(join_date, "%Y-%m-%d")
            days = max(0, (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days)
        status_text = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {days} Hari"
    
    return {
        "keyboard": [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status_text}"}]],
        "resize_keyboard": True
    }

def mode_keyboard(selected):
    def mark(x): return f"✅ {x}" if x in selected else f"❌ {x}"
    return {"inline_keyboard": [
        [{"text": mark("posting"), "callback_data": f"mode|posting"}],
        [{"text": mark("reply"), "callback_data": f"mode|reply"}],
        [{"text": mark("repost"), "callback_data": f"mode|repost"}],
        [{"text": "🚀 KONFIRMASI", "callback_data": "done"}]
    ]}

# --- BOT LOOP ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                # CALLBACK HANDLER (MENU & KONFIRMASI)
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    answer_callback(cq["id"])
                    
                    u = users.setdefault(chat_id, {"accounts": {}, "modes": []})

                    if data == "check_sub":
                        if is_member(chat_id, cq):
                            delete_msg(chat_id, msg_id)
                            send(chat_id, "🤖 **X-ALLER SYSTEM READY**", main_menu(chat_id, is_owner(cq)))
                        else: answer_callback(cq["id"], "❌ Belum join @xallertch!", alert=True)
                    
                    elif data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u.get("modes", []): u["modes"].remove(m)
                        else: u.setdefault("modes", []).append(m)
                        edit(chat_id, msg_id, f"⚙️ *SETTING @{u.get('temp_acc')}*", mode_keyboard(u["modes"]))
                    
                    elif data == "done":
                        acc = u.get("temp_acc")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u["state"] = None; save_data()
                            delete_msg(chat_id, msg_id) # MENGHAPUS MENU MERAH (NOMOR 1)
                            send(chat_id, f"✅ @{acc} berhasil dipantau!", main_menu(chat_id, is_owner(cq)))
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Join", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**", kb); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None})
                if owner_access: u["is_vip"] = True

                # REGISTRASI CHANNEL
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else: send(chat_id, "📖 Forward pesan channel ke sini."); continue

                # MENU AKUN
                if text.lower() == "add account":
                    u["state"] = "input_acc"; send(chat_id, "👤 Ketik username X (tanpa @):")
                elif u.get("state") == "input_acc":
                    acc = text.replace("@", "").strip().lower()
                    u["temp_acc"] = acc; u["modes"] = []; u["state"] = "choose_mode"
                    send(chat_id, f"⚙️ *SETTING @{acc}*", mode_keyboard([]))
                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 **DAFTAR:**\n" + ("\n".join(accs) if accs else "Kosong."))
                elif text == "❌ Remove Account":
                    # Menambahkan kembali logika hapus sederhana agar tidak error
                    u["state"] = "remove_acc"; send(chat_id, "Ketik username yang ingin dihapus:")
                elif u.get("state") == "remove_acc":
                    acc = text.replace("@", "").strip().lower()
                    if acc in u["accounts"]:
                        del u["accounts"][acc]; save_data()
                        send(chat_id, f"🗑️ @{acc} dihapus.", main_menu(chat_id, owner_access))
                    u["state"] = None
                elif text == "/start": send(chat_id, "🤖 *X-ALLER SYSTEM*", main_menu(chat_id, owner_access))

        except: pass
        time.sleep(1)

bot_loop()
