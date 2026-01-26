import os
import json

from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WS_URL = os.getenv("WS_URL")
API_SECRET = os.getenv("API_SECRET")
TG_LOG_TOKEN = os.getenv("TG_LOG_TOKEN")

CONFIG_FILE = BASE_DIR / "data" / "config.json"
ECONOMY_CONFIG_FILE = BASE_DIR / "data" / "economy_config.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

cfg = load_json(CONFIG_FILE)
ECO_CFG = load_json(ECONOMY_CONFIG_FILE)

def get_cfg(path, default=0):
    keys = path.split(".")
    data = cfg
    try:
        for k in keys:
            data = data[k]
        return data
    except (KeyError, TypeError):
        return default

TARGET_GUILD_ID = get_cfg("guild_ids.target_guild_id")
OWNER_ID = get_cfg("guild_ids.owner_id")
BOT_ID = get_cfg("guild_ids.bot_id")

ROLE_MUTE = get_cfg("roles.mute_role_id")
ROLE_BAN = get_cfg("roles.ban_role_id")
TICKET_SUPPORT_ROLES = get_cfg("roles.ticket_support_ids", [])
ADMIN_ROLE_IDS = get_cfg("roles.admin_role_ids", [])

TICKET_CATEGORY_SERVER_ID = get_cfg("categories.ticket_server_id")
TICKET_CATEGORY_TECH_ID = get_cfg("categories.ticket_tech_id")
TICKET_LOG_CHANNEL_ID = get_cfg("channels.ticket_log_id")
TG_LOG_CHAT_ID = get_cfg("channels.tg_log_chat_id")
ADMIN_CHANNELS_LIST = get_cfg("channels.admin_channel_ids", [])

LOG_PUNISH = get_cfg("logs.punish_channel_id")

ECONOMY_NEWS_CHANNEL_ID = ECO_CFG["channels"].get("economy_news_id", 0)
LOG_ECONOMY = ECO_CFG["channels"].get("log_economy_id", 0)

WEDDING_PRICE = ECO_CFG["global"].get("wedding_price", 50000)
DIVORCE_PRICE = ECO_CFG["global"].get("divorce_price", 25000)
MAX_UPGRADE_LEVEL = ECO_CFG["global"].get("max_upgrade_level", 15)
SELL_RATIO = ECO_CFG["global"].get("sell_ratio", 0.5)

DB_FILE = BASE_DIR / "data" / "users.db"