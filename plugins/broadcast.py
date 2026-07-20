import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import Config
from database import users_col

CANCEL_BROADCAST = False

@Client.on_callback_query(filters.regex("^cancel_broadcast$"))
async def cancel_bc(_, query):
    global CANCEL_BROADCAST
    CANCEL_BROADCAST = True
    await query.message.edit_text("🛑 <b>Cancelling broadcast... Please wait.</b>")

@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMINS) & filters.private)
async def broadcast_handler(client: Client, message: Message):
    global CANCEL_BROADCAST
    CANCEL_BROADCAST = False

    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to a message you want to broadcast.")

    ask = await message.reply(
        "<b>Do you want to pin this message for users?</b>",
        reply_markup=ReplyKeyboardMarkup([["Yes", "No"]], one_time_keyboard=True, resize_keyboard=True)
    )
    
    try:
        res = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=30)
        is_pin = res.text.strip().lower() == "yes"
        await ask.delete()
    except Exception:
        await ask.delete()
        is_pin = False

    b_msg = message.reply_to_message
    sts_msg = await message.reply_text("🚀 <b>Starting Broadcast...</b>")

    users = [doc["user_id"] async for doc in users_col.find({}, {"user_id": 1})]
    total_users = len(users)
    success = blocked = failed = 0
    start_time = time.time()

    for idx, user_id in enumerate(users, start=1):
        if CANCEL_BROADCAST:
            break
        try:
            sent = await b_msg.copy(chat_id=user_id)
            if is_pin:
                await sent.pin(both_sides=True)
            success += 1
        except Exception as e:
            if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                blocked += 1
            else:
                failed += 1

        if idx % 20 == 0 or idx == total_users:
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")]])
            await sts_msg.edit_text(
                f"📣 <b>Broadcast Progress:</b>\n\n"
                f"👥 Total Users: <code>{total_users}</code>\n"
                f"✅ Completed: <code>{idx}/{total_users}</code>\n"
                f"📬 Successful: <code>{success}</code>\n"
                f"🚫 Blocked: <code>{blocked}</code>\n"
                f"❌ Failed: <code>{failed}</code>",
                reply_markup=btn
            )
        await asyncio.sleep(0.05)

    elapsed = round(time.time() - start_time)
    await sts_msg.edit_text(
        f"✅ <b>Broadcast Finished in {elapsed}s!</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"📬 Successful: <code>{success}</code>\n"
        f"🚫 Blocked: <code>{blocked}</code>\n"
        f"❌ Failed: <code>{failed}</code>"
    )

@Client.on_message(filters.command("stats") & filters.user(Config.ADMINS))
async def stats_command(client: Client, message: Message):
    total = await users_col.count_documents({})
    premium = await users_col.count_documents({"is_premium": True})
    free = total - premium

    await message.reply_text(
        f"📊 <b>Bot Statistics:</b>\n\n"
        f"👥 Total Users: <code>{total}</code>\n"
        f"💎 Premium Users: <code>{premium}</code>\n"
        f"🆓 Free Users: <code>{free}</code>"
    )
