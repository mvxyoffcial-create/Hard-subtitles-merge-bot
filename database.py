import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URI)
db = client[Config.DATABASE_NAME]
users_col = db["users"]

async def add_user(user_id: int, first_name: str, username: str):
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        new_user = {
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "is_premium": False,
            "expiry_time": None,
            "joined_date": datetime.datetime.now(datetime.timezone.utc)
        }
        await users_col.insert_one(new_user)

async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})

async def is_premium_user(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    if user.get("is_premium") and user.get("expiry_time"):
        if user["expiry_time"] > datetime.datetime.now(datetime.timezone.utc):
            return True
        else:
            # Plan expired
            await users_col.update_one({"user_id": user_id}, {"$set": {"is_premium": False, "expiry_time": None}})
            return False
    return False

async def update_premium(user_id: int, expiry_time: datetime.datetime):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": True, "expiry_time": expiry_time}},
        upsert=True
    )

async def remove_premium(user_id: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": False, "expiry_time": None}}
    )
