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

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)

users = load_data()

# --- FUNGSI IDENTIFIKASI ---
def is_owner(msg):
    u = msg.get("from", msg.get("chat", {}))
    cid = str(u.get("id", ""))
    un = u.get("username", "").lower() if u.get("username") else ""
    return cid == str(OWNER_CHAT_ID) or un == OWNER_USERNAME.lower()

def is_member(user_id, msg=None):
    # Owner @njmondeth selalu dianggap member agar tidak stuck
    if msg and is_owner(msg): return True
    try:
        url = f"{API}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("ok"):
            status = r.get("result", {}).get("status", "")
            # Member, Administrator, dan Creator diizinkan
            return status in ["creator", "administrator", "member"]
        return False
    except: return True

def get_remaining_days(user_id):
    u = users.get(str(user_id))
    if not u or not u.get("join_date"): return 0
    if u.get("is_vip"): return 999 
    jd = datetime.datetime.strptime(u["join_date"], "%Y-%m-%d")
    rem = (jd + datetime.timedelta(days=30) - datetime.datetime.now()).days
    return max(0, rem)

# --- FUNGSI DASAR ---
def send(chat_id, text, markup=None):
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"{API}/sendMessage", data=payload)

def edit(chat_id, msg_id, text, markup):
    payload = {"chat_id": str(chat_id), "message_id": msg_id, "text": text, "reply_markup": json.dumps(markup), "parse_mode": "Markdown"}
    return requests.post(f"{API}/editMessageText", data=payload)

# --- KEYBOARDS ---
def main_menu(user_id, owner_access=False):
    u = users.setdefault(str(user_id), {"is_vip": False})
    if owner_access:
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": "👑 ADMIN DASHBOARD"}]]
    else:
        status = "💎 VIP" if u.get("is_vip") else f"⏳ Trial: {get_remaining_days(user_id)} Hari"
        kb = [[{"text": "add account"}], [{"text": "📋 List Accounts"}, {"text": "❌ Remove Account"}], [{"text": f"👤 Status: {status}"}]]
    return {"keyboard": kb, "resize_keyboard": True}

def admin_kb():
    return {"inline_keyboard": [
        [{"text": "👥 Semua Member", "callback_data": "adm|all"}],
        [{"text": "⏳ Trial", "callback_data": "adm|trial"}, {"text": "💎 VIP", "callback_data": "adm|vip"}],
        [{"text": "🔙 Tutup", "callback_data": "close"}]
    ]}

# --- BOT LOOP ---
def bot_loop():
    offset = None
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                # CALLBACK HANDLER (ADMIN DASHBOARD UI)
                if "callback_query" in upd:
                    cq = upd["callback_query"]; chat_id = str(cq["message"]["chat"]["id"])
                    msg_id = cq["message"]["message_id"]; data = cq["data"]
                    
                    if not is_owner(cq):
                        # Pengecekan status untuk user biasa (tombol Cek Status)
                        if data == "check_sub":
                            if is_member(chat_id, cq):
                                requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                                send(chat_id, "✅ **AKSES DIBUKA!**", main_menu(chat_id, False))
                            else:
                                requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": "❌ Anda belum bergabung!", "show_alert": True})
                        continue

                    # Logika Admin Dashboard
                    if data == "close": requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                    elif data.startswith("adm|"):
                        m_type = data.split("|")[1]
                        btn = []
                        for uid, d in users.items():
                            is_v = d.get("is_vip", False)
                            days = get_remaining_days(uid)
                            if m_type == "trial" and (is_v or days <= 0): continue
                            if m_type == "vip" and not is_v: continue
                            tag = "💎" if is_v else "⏳"
                            btn.append([{"text": f"{tag} ID: {uid}", "callback_data": f"view|{uid}"}])
                        btn.append([{"text": "🔙 Kembali", "callback_data": "back_adm"}])
                        edit(chat_id, msg_id, f"📂 *DAFTAR {m_type.upper()}*", {"inline_keyboard": btn})
                    elif data.startswith("view|"):
                        t_id = data.split("|")[1]
                        info = f"👤 *DETAIL USER*\nID: `{t_id}`\nStatus: VIP" if users[t_id].get("is_vip") else f"👤 *DETAIL USER*\nID: `{t_id}`\nStatus: Trial ({get_remaining_days(t_id)} hari)"
                        kb = {"inline_keyboard": [[{"text": "🚀 UPGRADE VIP", "callback_data": f"upg|{t_id}"}], [{"text": "🔙 Kembali", "callback_data": "adm|all"}]]}
                        edit(chat_id, msg_id, info, kb)
                    elif data.startswith("upg|"):
                        t_id = data.split("|")[1]
                        users[t_id]["is_vip"] = True; save_data()
                        send(t_id, "💎 **SELAMAT!** Admin telah mengaktifkan status VIP Anda."); edit(chat_id, msg_id, f"✅ ID `{t_id}` sukses jadi VIP!", admin_kb())
                    elif data == "back_adm": edit(chat_id, msg_id, "👑 *ADMIN DASHBOARD*", admin_kb())
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                # Force Subscribe Check
                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Join Channel", "url": CHANNEL_LINK}], [{"text": "🔄 Cek Status", "callback_data": "check_sub"}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**\nSilakan bergabung ke channel untuk mulai memantau.", kb); continue

                u = users.setdefault(chat_id, {"accounts": {}, "target_channel": None, "is_vip": False})
                if owner_access: u["is_vip"] = True

                # Step 1: Forward Channel
                if not u.get("target_channel"):
                    if "forward_from_chat" in msg and msg["forward_from_chat"]["type"] == "channel":
                        u["target_channel"] = msg["forward_from_chat"]["id"]
                        u["join_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        save_data(); send(chat_id, "✅ **TERHUBUNG!**", main_menu(chat_id, owner_access))
                    else: send(chat_id, "📖 Forward pesan channel pribadi Anda ke sini."); continue

                # --- LOGIKA DASHBOARD ---
                if text == "👑 ADMIN DASHBOARD" and owner_access:
                    send(chat_id, "👑 *ADMIN DASHBOARD*", admin_kb())
                elif text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))
                
                # Tambahkan logika add/list/remove di sini (tetap sama)
                elif text.lower() == "add account":
                    u["state"] = "input"; send(chat_id, "👤 Username X (tanpa @):")
                elif u.get("state") == "input":
                    acc = text.replace("@", "").strip().lower()
                    u["accounts"][acc] = {"last": None}; u["state"] = None; save_data()
                    send(chat_id, f"✅ @{acc} dipantau.", main_menu(chat_id, owner_access))
        except: pass
        time.sleep(1)

bot_loop()
