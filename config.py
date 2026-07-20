import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.environ.get("API_ID", "123456"))
    API_HASH = os.environ.get("API_HASH", "your_api_hash")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
    
    # Session String of a Telegram Premium Account (Required for 4GB uploads/downloads)
    STRING_SESSION = os.environ.get("STRING_SESSION", "")
    
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "HardSubBot")
    
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "123456789").split()]
    FORCE_SUB_CHANNELS = os.environ.get("FORCE_SUB_CHANNELS", "spideyoffcail,mvxyoffcail").split(",")
    
    # Limits (in bytes)
    FREE_LIMIT = 2 * 1024 * 1024 * 1024  # 2 GB
    PREMIUM_LIMIT = 4 * 1024 * 1024 * 1024  # 4 GB
