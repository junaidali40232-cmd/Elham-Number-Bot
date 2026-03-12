import os
import re
import json
import asyncio
import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =================== CONFIG ===================
BOT_TOKEN = "8778065589:AAFIYpfFIg3a5Zz2F2lsahWAuABOiCa1m6U"  # apna token
ADMIN_ID = 7860744037                                          # apna admin ID
ADMINS = [7860744037]

# Default API URLs - ab teen hain
DEFAULT_API_URLS = [
    "https://whatjunaid-production.up.railway.app/api/?type=sms",
    "https://time-panel-production.up.railway.app/api/junaid?type=sms",  # aapki di hui API
    "https://mis-panel-production.up.railway.app/api/junaid?type=sms"
]

SEEN_FILE = "seen_otps.json"
INTRO_FILE = "introduced_apis.json"  # introduced APIs ko save karne ke liye nayi file

# =================== STORAGE ===================
numbers_db = {}
groups_db = {}
api_configs_db = {}
channels_db = {}
user_state = {}
user_watch = {}
seen_otps = set()
introduced_apis = set()      # jin APIs ka introduction ho chuka hai
otp_counter = 0
db_id_counter = {"numbers": 0, "groups": 0, "apis": 0, "channels": 0}
save_counter = 0

# =================== COUNTRY & FLAG MAPS ===================
COUNTRY_DETECT = {
    "Zimbabwe": {"name": "Zimbabwe", "code": "ZW", "flag": "🇿🇼"},
    "Venezuela": {"name": "Venezuela", "code": "VE", "flag": "🇻🇪"},
    "India": {"name": "India", "code": "IN", "flag": "🇮🇳"},
    "Russia": {"name": "Russia", "code": "RU", "flag": "🇷🇺"},
    "Kazakhstan": {"name": "Kazakhstan", "code": "KZ", "flag": "🇰🇿"},
    "Kyrgyzstan": {"name": "Kyrgyzstan", "code": "KG", "flag": "🇰🇬"},
    "USA": {"name": "USA", "code": "US", "flag": "🇺🇸"},
    "UK": {"name": "UK", "code": "GB", "flag": "🇬🇧"},
    "Pakistan": {"name": "Pakistan", "code": "PK", "flag": "🇵🇰"},
    "Brazil": {"name": "Brazil", "code": "BR", "flag": "🇧🇷"},
    "Nigeria": {"name": "Nigeria", "code": "NG", "flag": "🇳🇬"},
    "Kenya": {"name": "Kenya", "code": "KE", "flag": "🇰🇪"},
    "Indonesia": {"name": "Indonesia", "code": "ID", "flag": "🇮🇩"},
    "Philippines": {"name": "Philippines", "code": "PH", "flag": "🇵🇭"},
    "Mexico": {"name": "Mexico", "code": "MX", "flag": "🇲🇽"},
    "Colombia": {"name": "Colombia", "code": "CO", "flag": "🇨🇴"},
    "Bangladesh": {"name": "Bangladesh", "code": "BD", "flag": "🇧🇩"},
    "Turkey": {"name": "Turkey", "code": "TR", "flag": "🇹🇷"},
    "Egypt": {"name": "Egypt", "code": "EG", "flag": "🇪🇬"},
    "China": {"name": "China", "code": "CN", "flag": "🇨🇳"},
    "Guinea": {"name": "Guinea", "code": "GN", "flag": "🇬🇳"},
    "Ghana": {"name": "Ghana", "code": "GH", "flag": "🇬🇭"},
    "Tanzania": {"name": "Tanzania", "code": "TZ", "flag": "🇹🇿"},
    "Uganda": {"name": "Uganda", "code": "UG", "flag": "🇺🇬"},
    "Mozambique": {"name": "Mozambique", "code": "MZ", "flag": "🇲🇿"},
    "Zambia": {"name": "Zambia", "code": "ZM", "flag": "🇿🇲"},
    "Cambodia": {"name": "Cambodia", "code": "KH", "flag": "🇰🇭"},
    "Vietnam": {"name": "Vietnam", "code": "VN", "flag": "🇻🇳"},
    "Thailand": {"name": "Thailand", "code": "TH", "flag": "🇹🇭"},
    "Nepal": {"name": "Nepal", "code": "NP", "flag": "🇳🇵"},
    "Afghanistan": {"name": "Afghanistan", "code": "AF", "flag": "🇦🇫"},
    "Iraq": {"name": "Iraq", "code": "IQ", "flag": "🇮🇶"},
    "Iran": {"name": "Iran", "code": "IR", "flag": "🇮🇷"},
    "UAE": {"name": "UAE", "code": "AE", "flag": "🇦🇪"},
    "Argentina": {"name": "Argentina", "code": "AR", "flag": "🇦🇷"},
    "Peru": {"name": "Peru", "code": "PE", "flag": "🇵🇪"},
    "Chile": {"name": "Chile", "code": "CL", "flag": "🇨🇱"},
    "Ukraine": {"name": "Ukraine", "code": "UA", "flag": "🇺🇦"},
    "Germany": {"name": "Germany", "code": "DE", "flag": "🇩🇪"},
    "France": {"name": "France", "code": "FR", "flag": "🇫🇷"},
    "Italy": {"name": "Italy", "code": "IT", "flag": "🇮🇹"},
    "Spain": {"name": "Spain", "code": "ES", "flag": "🇪🇸"},
    "Canada": {"name": "Canada", "code": "CA", "flag": "🇨🇦"},
    "Australia": {"name": "Australia", "code": "AU", "flag": "🇦🇺"},
    "Japan": {"name": "Japan", "code": "JP", "flag": "🇯🇵"},
    "SouthAfrica": {"name": "South Africa", "code": "ZA", "flag": "🇿🇦"},
    "Malaysia": {"name": "Malaysia", "code": "MY", "flag": "🇲🇾"},
    "Singapore": {"name": "Singapore", "code": "SG", "flag": "🇸🇬"},
    "Morocco": {"name": "Morocco", "code": "MA", "flag": "🇲🇦"},
}
FLAG_MAP = {k: v["flag"] for k, v in COUNTRY_DETECT.items()}

def get_flag(country):
    return FLAG_MAP.get(country, "🌍")

def is_admin(user_id):
    return user_id in ADMINS

# =================== PERSISTENCE ===================
def load_seen_otps():
    global seen_otps
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, 'r') as f:
                data = json.load(f)
                seen_otps = set(data)
            logger.info(f"Loaded {len(seen_otps)} seen OTPs")
    except Exception as e:
        logger.error(f"Failed to load seen OTPs: {e}")

def save_seen_otps():
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(list(seen_otps), f)
    except Exception as e:
        logger.error(f"Failed to save seen OTPs: {e}")

def load_introduced_apis():
    global introduced_apis
    try:
        if os.path.exists(INTRO_FILE):
            with open(INTRO_FILE, 'r') as f:
                data = json.load(f)
                introduced_apis = set(data)
            logger.info(f"Loaded {len(introduced_apis)} introduced APIs")
    except Exception as e:
        logger.error(f"Failed to load introduced APIs: {e}")

def save_introduced_apis():
    try:
        with open(INTRO_FILE, 'w') as f:
            json.dump(list(introduced_apis), f)
    except Exception as e:
        logger.error(f"Failed to save introduced APIs: {e}")

# =================== STORAGE FUNCTIONS ===================
def get_number_stats():
    stats = {}
    for n in numbers_db.values():
        if n["status"] == "available":
            stats[n["country"]] = stats.get(n["country"], 0) + 1
    return [{"country": c, "count": cnt} for c, cnt in stats.items()]

def get_number_by_country(country):
    for n in numbers_db.values():
        if n["country"] == country and n["status"] == "available":
            return n
    return None

def bulk_create_numbers(country, phones):
    count = 0
    for phone in phones:
        db_id_counter["numbers"] += 1
        nid = db_id_counter["numbers"]
        numbers_db[nid] = {"id": nid, "country": country, "phone": phone.strip(), "status": "available", "assigned_to": None}
        count += 1
    return count

def delete_numbers_by_country(country):
    to_del = [k for k, v in numbers_db.items() if v["country"] == country]
    for k in to_del:
        del numbers_db[k]

def mark_number_assigned(nid, session_key):
    if nid in numbers_db:
        numbers_db[nid]["status"] = "assigned"
        numbers_db[nid]["assigned_to"] = session_key

def get_groups():
    return list(groups_db.values())

def get_active_groups():
    return [g for g in groups_db.values() if g.get("active", True)]

def add_group(group_id, title):
    db_id_counter["groups"] += 1
    gid = db_id_counter["groups"]
    groups_db[gid] = {"id": gid, "group_id": group_id, "title": title, "active": True}
    return groups_db[gid]

def remove_group(gid):
    groups_db.pop(gid, None)

def toggle_group(gid, active):
    if gid in groups_db:
        groups_db[gid]["active"] = active

def get_api_configs():
    return list(api_configs_db.values())

def add_api_config(name, url):
    db_id_counter["apis"] += 1
    aid = db_id_counter["apis"]
    api_configs_db[aid] = {"id": aid, "name": name, "url": url, "active": True}
    return api_configs_db[aid]

def remove_api_config(aid):
    api_configs_db.pop(aid, None)

def toggle_api_config(aid, active):
    if aid in api_configs_db:
        api_configs_db[aid]["active"] = active

def get_channels():
    return list(channels_db.values())

def get_active_channels():
    return [c for c in channels_db.values() if c.get("active", True)]

def add_channel(channel_id, channel_username, title):
    db_id_counter["channels"] += 1
    cid = db_id_counter["channels"]
    channels_db[cid] = {"id": cid, "channel_id": channel_id, "channel_username": channel_username, "title": title, "active": True}
    return channels_db[cid]

def remove_channel(cid):
    channels_db.pop(cid, None)

def toggle_channel(cid, active):
    if cid in channels_db:
        channels_db[cid]["active"] = active

# =================== OTP HELPERS ===================
def detect_country(panel):
    panel_lower = panel.lower()
    for key, value in COUNTRY_DETECT.items():
        if key.lower() in panel_lower:
            return value
    return {"name": "Unknown", "code": "XX", "flag": "🌍"}

def mask_phone_stars(phone):
    digits = re.sub(r'\D', '', phone)
    if len(digits) <= 6:
        return digits
    return f"{digits[:4]}****{digits[-4:]}"

def mask_phone_dots(phone):
    digits = re.sub(r'\D', '', phone)
    if len(digits) <= 4:
        return digits
    return f"{digits[:2]}••{digits[-4:]}"

def get_service_icon(service):
    lower = service.lower()
    icons = {
        "whatsapp": "🟢", "telegram": "📨", "tiktok": "🎵",
        "netflix": "🔴", "microsoft": "🟦", "google": "🔍",
        "facebook": "🔵", "instagram": "📷",
    }
    for k, v in icons.items():
        if k in lower:
            return v
    return "📱"

def get_service_short(service):
    lower = service.lower()
    shorts = {
        "whatsapp": "WA", "telegram": "TG", "tiktok": "TT", "netflix": "NF",
        "microsoft": "MS", "google": "GG", "facebook": "FB", "instagram": "IG",
        "twitter": "TW", "snapchat": "SC", "uber": "UB", "amazon": "AZ",
        "paypal": "PP", "discord": "DC", "signal": "SG", "viber": "VB",
    }
    for k, v in shorts.items():
        if k in lower:
            return v
    return service[:2].upper()

def extract_otp(message):
    patterns = [r'(\d{3}-\d{3})', r'(\d{6})', r'(\d{4,8})']
    for p in patterns:
        m = re.search(p, message)
        if m:
            return m.group(1)
    return None

def make_otp_key(entry):
    msg = str(entry.get("message", ""))[:30]
    return f"{entry['timestamp']}|{entry['phone']}|{msg}"

def build_group_message(otp, counter):
    country = detect_country(otp["panel"])
    masked = mask_phone_stars(otp["phone"])
    otp_code = extract_otp(otp["message"])
    svc_icon = get_service_icon(otp["sender"])
    text = f"{country['flag']} <b>New {country['name']} {otp['sender']} OTP!</b>\n\n"
    text += f"🕐 Time: {otp['timestamp']}\n"
    text += f"{country['flag']} Country: {country['name']}\n"
    text += f"{svc_icon} Service: {otp['sender']}\n"
    text += f"📞 Number: {masked}\n"
    if otp_code:
        text += f"🔑 OTP: {otp_code}\n"
    text += f"\n💬 Full Message:\n<pre>{otp['message']}</pre>\n\n"
    text += f"<b>Powered By Elham</b> 💗"
    return text

def build_admin_message(otp):
    country = detect_country(otp["panel"])
    masked = mask_phone_dots(otp["phone"])
    svc_short = get_service_short(otp["sender"])
    text = f"{country['flag']} {country['code']} | {masked} | {svc_short}\n\n"
    text += f"Access: {otp['phone']}\n"
    text += f"Service: {otp['sender']}\n\n"
    text += f"Message:\n<pre>{otp['message']}</pre>"
    return text

def build_user_message(otp, phone, country_name, flag):
    digits = re.sub(r'\D', '', phone)
    masked = f"{digits[:2]}••{digits[-4:]}" if len(digits) > 4 else digits
    lower = otp["sender"].lower()
    svc = "WA" if "whatsapp" in lower else "TG" if "telegram" in lower else "TT" if "tiktok" in lower else otp["sender"][:2].upper()
    text = f"{flag} {country_name} | {masked} | {svc}\n\n"
    text += f"Access: {phone}\n"
    text += f"Service: {otp['sender']}\n\n"
    text += f"Message:\n<pre>{otp['message']}</pre>"
    return text

GROUP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📱 Channel", url="https://t.me/teach_hack_elham"),
        InlineKeyboardButton("☎️ Number", url="https://t.me/teach_hack_elham"),
    ],
    [
        InlineKeyboardButton("💻 DEVELOPER", url="https://t.me/Elham_cyberi"),
        InlineKeyboardButton("💬Main Chat", url="https://t.me/Elham_virtual_number"),
    ],
])

# =================== OTP POLLER (2-OLD-OTP LIMIT) ===================
async def fetch_otps_from_url(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            entries = []
            for row in data.get("aaData", []):
                if isinstance(row, list) and len(row) >= 5 and isinstance(row[0], str) and isinstance(row[4], str):
                    entries.append({
                        "timestamp": row[0],
                        "panel": str(row[1]),
                        "phone": str(row[2]),
                        "sender": str(row[3]),
                        "message": str(row[4]),
                    })
            # Sort by timestamp (oldest first) to avoid forwarding newest old OTPs
            entries.sort(key=lambda x: x['timestamp'])
            return entries
    except Exception:
        return []

async def otp_poller(bot_instance: Bot):
    global otp_counter, save_counter
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                urls = DEFAULT_API_URLS.copy()
                for cfg in api_configs_db.values():
                    if cfg.get("active") and cfg["url"] not in urls:
                        urls.append(cfg["url"])

                for url in urls:
                    otps = await fetch_otps_from_url(session, url)
                    if not otps:
                        continue

                    if url not in introduced_apis:
                        logger.info(f"New API: {url} with {len(otps)} OTPs. Forwarding first 2.")
                        for i, otp in enumerate(otps):
                            key = make_otp_key(otp)
                            if key in seen_otps:
                                continue
                            seen_otps.add(key)
                            save_counter += 1
                            if i < 2:  # sirf 2 purane OTPs forward karo
                                otp_counter += 1
                                group_text = build_group_message(otp, otp_counter)
                                for group in get_active_groups():
                                    try:
                                        await bot_instance.send_message(
                                            chat_id=group["group_id"], text=group_text,
                                            parse_mode=ParseMode.HTML, reply_markup=GROUP_KEYBOARD
                                        )
                                    except Exception as e:
                                        logger.error(f"Group send error: {e}")
                                admin_text = build_admin_message(otp)
                                try:
                                    await bot_instance.send_message(
                                        chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML
                                    )
                                except Exception as e:
                                    logger.error(f"Admin send error: {e}")
                                normalized = re.sub(r'\D', '', otp["phone"])
                                for watch_phone, watch_info in list(user_watch.items()):
                                    watch_digits = re.sub(r'\D', '', watch_phone)
                                    if normalized == watch_digits or normalized.endswith(watch_digits) or watch_digits.endswith(normalized):
                                        user_text = build_user_message(otp, watch_info["phone"], watch_info["country"], watch_info["flag"])
                                        try:
                                            await bot_instance.send_message(
                                                chat_id=watch_info["user_id"], text=user_text, parse_mode=ParseMode.HTML
                                            )
                                        except Exception as e:
                                            logger.error(f"User send error: {e}")
                                        del user_watch[watch_phone]
                                        break
                            if save_counter >= 100:
                                save_seen_otps()
                                save_counter = 0
                        introduced_apis.add(url)
                        save_introduced_apis()  # introduced APIs ko save karo
                    else:
                        for otp in otps:
                            key = make_otp_key(otp)
                            if key in seen_otps:
                                continue
                            seen_otps.add(key)
                            save_counter += 1
                            otp_counter += 1
                            group_text = build_group_message(otp, otp_counter)
                            for group in get_active_groups():
                                try:
                                    await bot_instance.send_message(
                                        chat_id=group["group_id"], text=group_text,
                                        parse_mode=ParseMode.HTML, reply_markup=GROUP_KEYBOARD
                                    )
                                except Exception as e:
                                    logger.error(f"Group send error: {e}")
                            admin_text = build_admin_message(otp)
                            try:
                                await bot_instance.send_message(
                                    chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                logger.error(f"Admin send error: {e}")
                            normalized = re.sub(r'\D', '', otp["phone"])
                            for watch_phone, watch_info in list(user_watch.items()):
                                watch_digits = re.sub(r'\D', '', watch_phone)
                                if normalized == watch_digits or normalized.endswith(watch_digits) or watch_digits.endswith(normalized):
                                    user_text = build_user_message(otp, watch_info["phone"], watch_info["country"], watch_info["flag"])
                                    try:
                                        await bot_instance.send_message(
                                            chat_id=watch_info["user_id"], text=user_text, parse_mode=ParseMode.HTML
                                        )
                                    except Exception as e:
                                        logger.error(f"User send error: {e}")
                                    del user_watch[watch_phone]
                                    break
                            if save_counter >= 100:
                                save_seen_otps()
                                save_counter = 0

                if len(seen_otps) > 5000:
                    excess = list(seen_otps)[:len(seen_otps) - 2000]
                    for k in excess:
                        seen_otps.discard(k)
                    save_seen_otps()

            except Exception as e:
                logger.error(f"Poller error: {e}")

            await asyncio.sleep(1.5)

# =================== FORCE JOIN ===================
async def che
