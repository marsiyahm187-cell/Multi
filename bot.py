import time, json, os, threading, requests, feedparser, datetime

# ==== DATA IDENTITAS OWNER ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = "njmondeth" 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "users.json"

# KONFIGURASI BISNIS
CHANNEL_ID = "@xallertch"
CHANNEL_LINK = "https://t.me/xallertch"
ADMIN_PEMBELIAN = "@Allertnow"

# INSTANCE NITTER
NITTER_INSTANCES = ["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=4) # Indent agar file json lebih rapi

users = load_data()

# --- FUNGSI IDENTIFIKASI ---
def is_owner(msg):
    u = msg.get("from", msg.get("chat", {}))
    cid = str(u.get("id", ""))
    un = u.get("username", "").lower() if u.get("username") else ""
    return cid == str(OWNER_CHAT_ID) or un == OWNER_USERNAME.lower()

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

def get_remaining_days(user_id):
    u = users.get(str(user_id))
    if not u or not u.get("join_date"): return 0
    # Jika VIP, kembalikan angka tinggi agar tidak dianggap habis
    if u.get("is_vip") is True: return 999 
    
    jd = datetime.datetime.strptime(u["join_date"], "%Y-%m-%d")
    rem = (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days
    return max(0, rem)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def main_menu(user_id, owner_access=False):
    u = users.setdefault(str(user_id), {"is_vip": False})
    if owner_access:
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": "👑 ADMIN DASHBOARD"}]]
    else:
        status = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status}"}]]
    return {"keyboard": kb, "resize_keyboard": True}

def mode_keyboard(selected):
    def mark(x): return f"✅ {x}" if x in selected else f"❌ {x}"
    return {"inline_keyboard": [
        [{"text": mark("posting"), "callback_data": "mode|posting"}],
        [{"text": mark("reply"), "callback_data": "mode|reply"}],
        [{"text": mark("repost"), "callback_data": "mode|repost"}],
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
                
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    u = users.setdefault(chat_id, {"accounts": {}, "modes": []})

                    if data == "done":
                        acc = u.get("temp_acc")
                        if acc:
                            u["accounts"][acc] = {"mode": u["modes"], "last": None}
                            u.pop("temp_acc", None); save_data()
                            requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                            send(chat_id, f"✅ @{acc} dipantau!", main_menu(chat_id, is_owner(cq)))
                    elif data.startswith("mode|"):
                        m = data.split("|")[1]
                        if m in u["modes"]: u["modes"].remove(m)
                        else: u["modes"].append(m)
                        requests.post(f"{API}/editMessageText", data={"chat_id": chat_id, "message_id": msg_id, "text": f"⚙️ *MODE @{u.get('temp_acc')}*", "reply_markup": json.dumps(mode_keyboard(u["modes"])), "parse_mode": "Markdown"})
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                # Force Subscribe
                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Join Channel", "url": CHANNEL_LINK}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**", kb); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # Step 1: Forward Channel
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data()
                        send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else: send(chat_id, "📖 Forward pesan channel pribadi ke sini."); continue

                # PERINTAH OWNER: /setvip [ID]
                if text.startswith("/setvip") and owner_access:
                    parts = text.split(" ")
                    if len(parts) > 1:
                        target_id = parts[1].strip()
                        if target_id in users:
                            users[target_id]["is_vip"] = True
                            save_data()
                            send(chat_id, f"✅ Berhasil mengaktifkan VIP untuk ID: `{target_id}`")
                            send(target_id, "💎 **VIP ANDA TELAH AKTIF!**\nSekarang Anda memiliki akses penuh tanpa batas masa trial.", main_menu(target_id, False))
                        else:
                            send(chat_id, f"❌ ID `{target_id}` tidak ditemukan dalam database.")
                    continue

                if text == "👑 ADMIN DASHBOARD" and owner_access:
                    msg_admin = f"📊 *STATISTIK ADMIN*\nTotal User: {len(users)}\n\n"
                    msg_admin += "Untuk memberi VIP, ketik:\n`/setvip ID_USER`"
                    send(chat_id, msg_admin)
                
                elif text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                
                elif text.lower() == "add account":
                    if get_remaining_days(chat_id) <= 0 and not u.get("is_vip"):
                        send(chat_id, f"❌ Masa Trial habis. Silakan hubungi {ADMIN_PEMBELIAN} untuk aktivasi VIP."); continue
                    u["state"] = "input"; send(chat_id, "👤 Username X (tanpa @):")
                
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["temp_acc"] = acc; u["modes"] = []; u["state"] = None
                    send(chat_id, f"⚙️ *MODE @{acc}*", mode_keyboard([]))

                elif text == "📋 List Accounts":
                    accs = list(u["accounts"].keys())
                    send(chat_id, "📋 *DAFTAR:*\n" + ("\n".join(accs) if accs else "Kosong."))

                elif text == "❌ Remove Account":
                    u["state"] = "remove"; send(chat_id, "Ketik username yang ingin dihapus:")
                
                elif u.get("state") == "remove":
                    acc = text.replace("@", "").strip().lower()
                    if acc in u["accounts"]:
                        del u["accounts"][acc]; save_data()
                        send(chat_id, f"🗑️ @{acc} dihapus.", main_menu(chat_id, owner_access))
                    u["state"] = None

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

bot_loop()
