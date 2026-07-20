import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = 36282056
    API_HASH = "3a948acece533f362b4c90b2b3c14b60"
    BOT_TOKEN = "8737705568:AAGSjZlCgT6yrs6h045X88EEq63-iZLCiD4"
    
    # User Session String for 2GB to 4GB Uploads (Telegram Premium Account)
    STRING_SESSION = "BQIpnsgAgca4GkfxvaSH8YS0wOPwZ00EwEDYuuEMG7Q2KQJcKm8nltMZGBMLobx69FvkZe46vF_mEW2DENX2WfLGLI2gMTydwJIB1EZoUmwXu3s-SUJ5KbhLzFZ0Z9jIvyUUSVBI3kizWtvTSV0jkSvH4DJpU811-ZohuR_gZ7o20iiIAFv2wlLTIAv8Zy0WlSGtWO3T2OJe9dGeni6RwTjsdrZisgs26j34q75usxV327BX6k1dv9gw3F1asezIiwQk7wlp-DPz1gFHTN2AKLslGSpm9k1YPGtilTjVc-kOnjBvemI4O6jy18pGFNHJHfJZs88ZC9kaFdu0l1YPpPsjCF2H5QAAAAHvdyxsAA"
    
    # Database Settings
    MONGO_URI = "mongodb+srv://cloudnestoffcail_db_user:Venura8907@cluster0.hjqkg75.mongodb.net/?appName=Cluster0"
    DATABASE_NAME = "hardsub_bot"
    
    # Admin User IDs & Required Force Subscribe Channels
    ADMINS = [8312532076]
    FORCE_SUB_CHANNELS = ["spideyoffcail", "mvxyoffcail"]
    
    # Limits (in bytes)
    FREE_LIMIT = 2 * 1024 * 1024 * 1024  # 2 GB
    PREMIUM_LIMIT = 4 * 1024 * 1024 * 1024  # 4 GB
