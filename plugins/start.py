import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    Message, CallbackQuery
)
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, MessageNotModified
from config import Config
from database import add_user, get_user, is_premium_user

# --- Helper Functions ---
async def check_force_sub(client: Client, user_id: int) -> bool:
    """Check if user joined required channels."""
    if not Config.FORCE_SUB_CHANNELS:
        return True
    for channel in Config.FORCE_SUB_CHANNELS:
        channel = channel.strip().replace("https://t.me/", "").replace("@", "")
        if not channel:
            continue
        try:
            await client.get_chat_member(channel, user_id)
        except UserNotParticipant:
            return False
        except Exception:
            pass
    return True

def get_force_sub_keyboard():
    buttons = []
    for idx, channel in enumerate(Config.FORCE_SUB_CHANNELS, start=1):
        channel_clean = channel.strip().replace("https://t.me/", "").replace("@", "")
        buttons.append([InlineKeyboardButton(f"📢 Join Channel {idx}", url=f"https://t.me/{channel_clean}")])
    buttons.append([InlineKeyboardButton("🔄 Refresh / Try Again", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)

# --- Text Builders (shared by command handlers & callback editors) ---
def get_welcome_text(first_name: str) -> str:
    return (
        f"<b>ʜᴇʏ, {first_name}! 👋</b>\n\n"
        f"ɪ'ᴍ ᴀɴ <b>ʜᴀʀᴅsᴜʙ ᴍᴇʀɢᴇ ʙᴏᴛ</b> 🎬\n"
        f"ɪ ᴄᴀɴ ᴍᴇʀɢᴇ ʜᴀʀᴅ sᴜʙᴛɪᴛʟᴇs ɪɴᴛᴏ ᴠɪᴅᴇᴏs ᴏғ ᴀɴʏ ʟᴀɴɢᴜᴀɢᴇ 🌍\n\n"
        f"📤 Sᴇɴᴅ ᴍᴇ ᴀ ᴠɪᴅᴇᴏ + sᴜʙᴛɪᴛʟᴇ ғɪʟᴇ\n"
        f"⚡ I'ʟʟ ᴍᴇʀɢᴇ ᴛʜᴇᴍ ᴘᴇʀғᴇᴄᴛʟʏ!\n"
        f"🚀 Uᴘ ᴛᴏ 4GB ғᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀs\n\n"
        f"👨‍💻 Dᴇᴠᴇʟᴏᴘᴇʀ: @Venuboyy"
    )

def get_welcome_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Home", callback_data="cb_home"),
            InlineKeyboardButton("❓ Help", callback_data="cb_help"),
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
            InlineKeyboardButton("💎 Premium", callback_data="cb_premium"),
        ]
    ])

def get_help_text() -> str:
    return (
        "<b>✨ Hᴏᴡ Tᴏ Usᴇ HᴀʀᴅSᴜʙ Mᴇʀɢᴇ Bᴏᴛ ✨</b>\n\n"
        "1️⃣ <b>Sᴇɴᴅ Vɪᴅᴇᴏ:</b> Send the video file you want to merge 🎬\n"
        "2️⃣ <b>Sᴇɴᴅ Sᴜʙᴛɪᴛʟᴇ:</b> Send the subtitle file (.srt, .ass, etc.) 📝\n"
        "3️⃣ <b>Mᴇʀɢᴇ:</b> Bot will automatically detect & merge them ⚡\n"
        "4️⃣ <b>Dᴏᴡɴʟᴏᴀᴅ:</b> Get your hardsubbed video! 📥\n\n"
        "📌 <b>Features:</b>\n"
        "➤ Supports all languages 🌐\n"
        "➤ Free: Up to 2GB | Premium: Up to 4GB 💎\n"
        "➤ Ultra-fast high-speed processing ⚡"
    )

def get_about_text() -> str:
    return (
        "<b>╭────[ Mʏ Dᴇᴛᴀɪʟs ]────⍟\n"
        "├⍟ Nᴀᴍᴇ : HᴀʀᴅSᴜʙ Mᴇʀɢᴇ Bᴏᴛ\n"
        "├⍟ Dᴇᴠᴇʟᴏᴘᴇʀ : <a href='https://t.me/Venuboyy'>Vᴇɴᴜʙᴏʏʏ</a> 👨‍💻\n"
        "├⍟ Lɪʙʀᴀʀʏ : <a href='https://github.com/pyrogram/pyrogram'>Pʏʀᴏɢʀᴀᴍ</a> 📚\n"
        "├⍟ Lᴀɴɢᴜᴀɢᴇ : <a href='https://www.python.org/'>Pʏᴛʜᴏɴ 𝟹</a> 🐍\n"
        "├⍟ Dᴀᴛᴀʙᴀsᴇ : <a href='https://www.mongodb.com/'>MᴏɴɢᴏDB</a> 🍃\n"
        "├⍟ Fᴇᴀᴛᴜʀᴇ : Hᴀʀᴅ Sᴜʙᴛɪᴛʟᴇ Mᴇʀɢᴇ 🔤\n"
        "├⍟ Mᴀx Sɪᴢᴇ : 4GB (Pʀᴇᴍɪᴜᴍ) 💎\n"
        "╰───────────────⍟</b>"
    )

def get_back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cb_home")]])

async def edit_panel(message: Message, text: str, buttons: InlineKeyboardMarkup):
    """Edit the existing message in place (photo caption or plain text) instead of sending a new one."""
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=buttons)
        else:
            await message.edit_text(text, reply_markup=buttons, disable_web_page_preview=True)
    except MessageNotModified:
        pass
    except Exception:
        # Fallback: if edit fails for any reason, send a fresh message
        try:
            await message.reply_text(text, reply_markup=buttons, disable_web_page_preview=True)
        except Exception:
            pass

# --- Start Handler ---
@Client.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.first_name, user.username or "")

    # Force Sub Check
    if not await check_force_sub(client, user.id):
        return await message.reply_text(
            f"<b>Hello {user.mention}! 👋</b>\n\n"
            "⚠️ You must join our official updates channels to use this bot.",
            reply_markup=get_force_sub_keyboard()
        )

    # 1. Sticker Animation (Auto-delete after 2 seconds)
    sticker_id = "CAACAgIAAxkBAAEQZtFpgEdROhGouBVFD3e0K-YjmVHwsgACtCMAAphLKUjeub7NKlvk2TgE"
    try:
        stk = await message.reply_sticker(sticker_id)
        await asyncio.sleep(2)
        await stk.delete()
    except Exception:
        pass

    # 2. Welcome UI Message
    welcome_text = get_welcome_text(user.first_name)
    buttons = get_welcome_buttons()

    welcome_img = "https://i.ibb.co/nMRFW6Kx/AQAD2w5r-G3a2b-VF8.jpg"
    try:
        await message.reply_photo(
            photo=welcome_img,
            caption=welcome_text,
            reply_markup=buttons,
            quote=True
        )
    except Exception:
        await message.reply_text(
            welcome_text,
            reply_markup=buttons,
            quote=True
        )

# --- Force Sub Check Callback ---
@Client.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_cb(client: Client, query: CallbackQuery):
    if await check_force_sub(client, query.from_user.id):
        await query.message.delete()
        await query.answer("✅ Thank you for joining! You can now use the bot.", show_alert=True)
        # Re-trigger start command
        await start_handler(client, query.message)
    else:
        await query.answer("❌ You haven't joined all channels yet! Please join and try again.", show_alert=True)

# --- Help Command ---
@Client.on_message(filters.private & filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(get_help_text())

# --- About Command ---
@Client.on_message(filters.private & filters.command("about"))
async def about_command(client: Client, message: Message):
    await message.reply_text(get_about_text(), disable_web_page_preview=True)

# --- Info Command ---
@Client.on_message(filters.private & filters.command("info"))
async def info_command(client: Client, message: Message):
    user = message.from_user
    db_user = await get_user(user.id) or {}
    is_prem = await is_premium_user(user.id)
    dc_id = user.dc_id or "Unknown"

    info_text = (
        f"➲ <b>Fɪʀsᴛ Nᴀᴍᴇ:</b> {user.first_name}\n"
        f"➲ <b>Lᴀsᴛ Nᴀᴍᴇ:</b> {user.last_name or 'None'}\n"
        f"➲ <b>Tᴇʟᴇɢʀᴀᴍ ID:</b> <code>{user.id}</code>\n"
        f"➲ <b>Dᴀᴛᴀ Cᴇɴᴛʀᴇ:</b> {dc_id}\n"
        f"➲ <b>Usᴇʀɴᴀᴍᴇ:</b> @{user.username or 'None'}\n"
        f"➲ <b>Usᴇʀ Lɪɴᴋ:</b> {user.mention}\n"
        f"➲ <b>Pʀᴇᴍɪᴜᴍ:</b> {'✅ Yes' if is_prem else '❌ No'}\n"
        f"➲ <b>Tᴏᴛᴀʟ Mᴇʀɢᴇs:</b> {db_user.get('total_merges', 0)}"
    )

    photos = [p async for p in client.get_chat_photos(user.id, limit=1)]
    if photos:
        await message.reply_photo(photo=photos[0].file_id, caption=info_text)
    else:
        await message.reply_text(info_text)

# --- Inline Navigation Callbacks ---
@Client.on_callback_query(filters.regex("^cb_"))
async def navigation_callbacks(client: Client, query: CallbackQuery):
    data = query.data.replace("cb_", "")
    if data == "home":
        await query.answer("Home Menu")
        await edit_panel(query.message, get_welcome_text(query.from_user.first_name), get_welcome_buttons())
    elif data == "help":
        await query.answer()
        await edit_panel(query.message, get_help_text(), get_back_button())
    elif data == "about":
        await query.answer()
        await edit_panel(query.message, get_about_text(), get_back_button())
    elif data == "premium":
        await query.answer("💎 Premium Info")
        await edit_panel(
            query.message,
            "💎 Use /myplan or contact @Venuboyy to purchase Premium.",
            get_back_button()
        )
