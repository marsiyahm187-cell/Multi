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
        json.dump(users, f, indent=4)

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
        [{"text": "👥 List Semua Member", "callback_data": "adm|all"}],
        [{"text": "⏳ Trial Member", "callback_data": "adm|trial"}, {"text": "💎 VIP Member", "callback_data": "adm|vip"}],
        [{"text": "🔙 Tutup", "callback_data": "close"}]
    ]}

def user_manage_kb(target_id):
    return {"inline_keyboard": [[{"text": "🚀 Upgrade ke VIP", "callback_data": f"upg|{target_id}"}], [{"text": "🔙 Kembali", "callback_data": "adm|all"}]]}

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
                    
                    if not is_owner(cq): continue

                    if data == "close":
                        requests.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
                    
                    elif data.startswith("adm|"):
                        filter_type = data.split("|")[1]
                        txt = f"📂 *DATA {filter_type.upper()} MEMBER*\n\n"
                        buttons = []
                        
                        for uid, d in users.items():
                            is_v = d.get("is_vip", False)
                            days = get_remaining_days(uid)
                            
                            if filter_type == "trial" and (is_v or days <= 0): continue
                            if filter_type == "vip" and not is_v: continue
                            
                            tag = "💎" if is_v else "⏳"
                            buttons.append([{"text": f"{tag} ID: {uid}", "callback_data": f"view|{uid}"}])
                        
                        buttons.append([{"text": "🔙 Kembali", "callback_data": "back_adm"}])
                        edit(chat_id, msg_id, txt + "Pilih user untuk manajemen:", {"inline_keyboard": buttons})

                    elif data.startswith("view|"):
                        t_id = data.split("|")[1]
                        u_data = users.get(t_id, {})
                        info = f"👤 *USER DETAIL*\nID: `{t_id}`\nStatus: {'VIP' if u_data.get('is_vip') else 'Trial'}\nSisa: {get_remaining_days(t_id)} Hari"
                        edit(chat_id, msg_id, info, user_manage_kb(t_id))

                    elif data.startswith("upg|"):
                        t_id = data.split("|")[1]
                        if t_id in users:
                            users[t_id]["is_vip"] = True; save_data()
                            requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": "✅ Sukses Upgrade ke VIP!"})
                            send(t_id, "💎 **SELAMAT!** Akun Anda telah diupgrade menjadi VIP oleh Admin.")
                            edit(chat_id, msg_id, f"✅ User `{t_id}` berhasil menjadi VIP.", admin_kb())

                    elif data == "back_adm":
                        edit(chat_id, msg_id, "👑 *ADMIN DASHBOARD*", admin_kb())
                    continue

                if "message" not in upd: continue
                msg = upd["message"]; chat_id = str(msg["chat"]["id"]); text = msg.get("text", "")
                owner_access = is_owner(msg)

                if not owner_access and not is_member(chat_id, msg):
                    kb = {"inline_keyboard": [[{"text": "📢 Join Channel", "url": CHANNEL_LINK}]]}
                    send(chat_id, "⚠️ **AKSES TERKUNCI**", kb); continue

                if text == "👑 ADMIN DASHBOARD" and owner_access:
                    send(chat_id, "👑 *ADMIN DASHBOARD*", admin_kb())
                
                elif text == "/start":
                    send(chat_id, "🤖 *X-ALLER SYSTEM ONLINE*", main_menu(chat_id, owner_access))

                # (Tambahkan logika add account, list, remove dari versi sebelumnya di sini)
                # ... (Logika add account tetap sama seperti script sebelumnya)

        except: pass
        time.sleep(1)

bot_loop()
