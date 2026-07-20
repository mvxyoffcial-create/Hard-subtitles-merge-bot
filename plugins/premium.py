import datetime
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageTooLong
from config import Config
from database import update_premium, remove_premium, get_user, users_col

IST = pytz.timezone("Asia/Kolkata")

# Helper to parse time string like "1 day", "1 month"
async def get_seconds(time_str: str) -> int:
    try:
        parts = time_str.lower().split()
        num = int(parts[0])
        unit = parts[1]
        if "min" in unit:
            return num * 60
        elif "hour" in unit:
            return num * 3600
        elif "day" in unit:
            return num * 86400
        elif "month" in unit:
            return num * 86400 * 30
        elif "year" in unit:
            return num * 86400 * 365
    except Exception:
        pass
    return 0

# --- User: Check Plan ---
@Client.on_message(filters.command("myplan") & filters.private)
async def myplan(client: Client, message: Message):
    user_id = message.from_user.id
    data = await get_user(user_id)

    if data and data.get("is_premium") and data.get("expiry_time"):
        expiry = data.get("expiry_time")
        if expiry.tzinfo is None:
            expiry = pytz.utc.localize(expiry)
        
        expiry_ist = expiry.astimezone(IST)
        expiry_str = expiry_ist.strftime("%d-%m-%Y | %I:%M:%S %p")

        current_time = datetime.datetime.now(pytz.utc)
        time_left = expiry - current_time
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        caption = (
            f"⚜️ <b>ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ᴅᴀᴛᴀ :</b>\n\n"
            f"👤 <b>ᴜꜱᴇʀ :</b> {message.from_user.mention}\n"
            f"⚡ <b>ᴜꜱᴇʀ ɪᴅ :</b> <code>{user_id}</code>\n"
            f"⏰ <b>ᴛɪᴍᴇ ʟᴇꜰᴛ :</b> {days} days, {hours} hours, {minutes} mins\n"
            f"⌛️ <b>ᴇxᴘɪʀʏ ᴅᴀᴛᴇ :</b> {expiry_str}"
        )
        await message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Extend Plan", user_id=Config.ADMINS[0])]])
        )
    else:
        caption = (
            f"<b>ʜᴇʏ {message.from_user.mention},\n\n"
            f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴛɪᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ.\n"
            f"ʙᴜʏ ᴏᴜʀ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ ᴛᴏ ᴇɴᴊᴏʏ ᴘʀᴇᴍɪᴜᴍ ʙᴇɴᴇꜰɪᴛꜱ (Up to 4GB files).</b>"
        )
        await message.reply_text(caption)

# --- Admin: Add Premium ---
@Client.on_message(filters.command(["add_premium", "addpremium"]) & filters.user(Config.ADMINS))
async def give_premium_cmd_handler(client: Client, message: Message):
    if len(message.command) >= 3:
        try:
            user_id = int(message.command[1])
            time_input = " ".join(message.command[2:])
            seconds = await get_seconds(time_input)

            if seconds <= 0:
                return await message.reply_text("❌ Invalid time format! Example: <code>/add_premium 12345678 1 month</code>")

            expiry_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
            await update_premium(user_id, expiry_time)

            user = await client.get_users(user_id)
            expiry_ist = expiry_time.astimezone(IST).strftime("%d-%m-%Y | %I:%M:%S %p")

            await message.reply_text(
                f"✅ <b>Premium Added Successfully!</b>\n\n"
                f"👤 <b>User:</b> {user.mention}\n"
                f"⚡ <b>User ID:</b> <code>{user_id}</code>\n"
                f"⌛️ <b>Expiry Date:</b> {expiry_ist}"
            )
            await client.send_message(
                chat_id=user_id,
                text=f"👋 <b>Hey {user.mention}, Premium activated!</b>\n\n⌛️ <b>Expires on:</b> {expiry_ist}"
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    else:
        await message.reply_text("📌 Usage: <code>/add_premium user_id 1 month</code>")

# --- Admin: Remove Premium ---
@Client.on_message(filters.command(["remove_premium", "removepremium"]) & filters.user(Config.ADMINS))
async def remove_premium_cmd(client: Client, message: Message):
    if len(message.command) == 2:
        try:
            user_id = int(message.command[1])
            await remove_premium(user_id)
            await message.reply_text(f"✅ Premium removed for user <code>{user_id}</code>")
            await client.send_message(chat_id=user_id, text="⚠️ Your premium access has been removed.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    else:
        await message.reply_text("📌 Usage: <code>/remove_premium user_id</code>")

# --- Admin: Get All Premium Users ---
@Client.on_message(filters.command("premium_users") & filters.user(Config.ADMINS))
async def list_premium_users(client: Client, message: Message):
    sts = await message.reply_text("<i>Fetching premium users...</i>")
    msg_text = "<b>👑 Premium Users List:</b>\n\n"
    count = 1

    async for user in users_col.find({"is_premium": True}):
        u_id = user.get("user_id")
        expiry = user.get("expiry_time")
        if expiry:
            if expiry.tzinfo is None:
                expiry = pytz.utc.localize(expiry)
            exp_str = expiry.astimezone(IST).strftime("%d-%m-%Y")
            msg_text += f"{count}. <code>{u_id}</code> | Expiry: {exp_str}\n"
            count += 1

    try:
        await sts.edit_text(msg_text)
    except MessageTooLong:
        with open("premium_users.txt", "w") as f:
            f.write(msg_text)
        await message.reply_document("premium_users.txt", caption="Premium Users List")
        os.remove("premium_users.txt")
