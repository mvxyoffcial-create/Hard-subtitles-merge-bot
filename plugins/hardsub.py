import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import is_premium_user, users_col
from progress import progress_bar

# Store pending files and choices per user
USER_STATE = {}

@Client.on_message(filters.private & (filters.video | filters.document))
async def handle_incoming_media(client: Client, message: Message):
    user_id = message.from_user.id
    
    file_size = 0
    file_name = ""

    if message.video:
        file_size = message.video.file_size
        file_name = message.video.file_name or f"video_{message.id}.mp4"
    elif message.document:
        file_size = message.document.file_size
        file_name = message.document.file_name or f"file_{message.id}"

    # Plan Limit Check
    is_prem = await is_premium_user(user_id)
    max_limit = Config.PREMIUM_LIMIT if is_prem else Config.FREE_LIMIT

    if file_size > max_limit:
        limit_str = "4GB" if is_prem else "2GB"
        return await message.reply_text(
            f"❌ <b>File Exceeds Your Limit!</b>\n"
            f"Your current plan allows up to <b>{limit_str}</b>."
        )

    sub_extensions = ('.srt', '.ass', '.ssa', '.sub', '.txt')
    is_subtitle = file_name.lower().endswith(sub_extensions)

    if user_id not in USER_STATE:
        USER_STATE[user_id] = {"video": None, "subtitle": None}

    if is_subtitle:
        USER_STATE[user_id]["subtitle"] = message
        if not USER_STATE[user_id]["video"]:
            await message.reply_text("✅ <b>Subtitle received!</b> Now send the video file.")
    else:
        USER_STATE[user_id]["video"] = message
        if not USER_STATE[user_id]["subtitle"]:
            await message.reply_text("✅ <b>Video received!</b> Now send the subtitle file.")

    # When both files are present, ask user for Codec choice
    if USER_STATE[user_id]["video"] and USER_STATE[user_id]["subtitle"]:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ x264 (Faster Encoding)", callback_data="codec_x264"),
                InlineKeyboardButton("🗜️ x265 (Smaller Size)", callback_data="codec_x265")
            ]
        ])
        await message.reply_text(
            "🎬 <b>Both files received!</b>\nPlease select your preferred video encoder:",
            reply_markup=keyboard
        )


@Client.on_callback_query(filters.regex(r"^codec_"))
async def handle_codec_choice(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    codec = callback_query.data.split("_")[1]  # 'x264' or 'x265'

    if user_id not in USER_STATE or not USER_STATE[user_id]["video"] or not USER_STATE[user_id]["subtitle"]:
        await callback_query.answer("⚠️ Session expired or missing files. Send files again.", show_alert=True)
        return

    vid_msg = USER_STATE[user_id]["video"]
    sub_msg = USER_STATE[user_id]["subtitle"]
    USER_STATE[user_id] = {"video": None, "subtitle": None}

    await callback_query.message.delete()
    await start_hardsub_pipeline(client, callback_query.message, vid_msg, sub_msg, codec)


async def start_hardsub_pipeline(bot_client: Client, trigger_msg: Message, vid_msg: Message, sub_msg: Message, codec: str):
    status_msg = await trigger_msg.reply_text(f"⏳ <b>Initializing HardSub process ({codec.upper()})...</b>")
    
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    uid = trigger_msg.chat.id
    ts = int(time.time())

    # Preserve the original subtitle extension so FFmpeg parses the format correctly
    sub_file_obj = sub_msg.document
    orig_sub_name = sub_file_obj.file_name if sub_file_obj and sub_file_obj.file_name else "sub.srt"
    sub_ext = os.path.splitext(orig_sub_name)[1].lower()
    if sub_ext not in ('.srt', '.ass', '.ssa', '.sub', '.txt'):
        sub_ext = ".srt"

    video_path = f"downloads/vid_{uid}_{ts}.mp4"
    sub_path = f"downloads/sub_{uid}_{ts}{sub_ext}"
    output_path = f"outputs/hardsub_{uid}_{ts}.mp4"

    try:
        # 1. Download Subtitle
        await status_msg.edit_text("📥 <b>Downloading Subtitle File...</b>")
        await bot_client.download_media(sub_msg, file_name=sub_path)

        # 2. Download Video File
        file_obj = vid_msg.video or vid_msg.document
        expected_size = file_obj.file_size if file_obj else 0

        start_dl = time.time()
        await status_msg.edit_text("📥 <b>Downloading Video File...</b>")

        # Standard Bot Client handles files under 2GB. Session client used for > 2GB
        dl_client = bot_client
        if expected_size > (2 * 1024 * 1024 * 1024) and hasattr(bot_client, "user_app") and bot_client.user_app:
            dl_client = bot_client.user_app

        dl_file = await dl_client.download_media(
            vid_msg,
            file_name=video_path,
            progress=progress_bar,
            progress_args=("📥 Downloading Video", status_msg, start_dl)
        )

        # Fallback to primary bot client if download wrote 0 bytes
        if (not dl_file or not os.path.exists(video_path) or os.path.getsize(video_path) == 0) and dl_client != bot_client:
            await status_msg.edit_text("🔄 <b>Retrying download with Primary Bot Client...</b>")
            if os.path.exists(video_path):
                os.remove(video_path)
            
            dl_file = await bot_client.download_media(
                vid_msg,
                file_name=video_path,
                progress=progress_bar,
                progress_args=("📥 Retrying Download", status_msg, start_dl)
            )

        # Download validation
        if not dl_file or not os.path.exists(video_path):
            return await status_msg.edit_text("❌ <b>Download failed: File not created.</b>")

        downloaded_size = os.path.getsize(video_path)
        if downloaded_size < expected_size:
            return await status_msg.edit_text(
                f"❌ <b>Incomplete download!</b>\n"
                f"Expected: {expected_size} bytes | Downloaded: {downloaded_size} bytes."
            )

        # 3. FFmpeg HardSub Processing
        await status_msg.edit_text(f"⚡ <b>Burning subtitles with lib{codec}...</b>\n<i>Please wait...</i>")
        
        escaped_sub_path = sub_path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\''")
        
        # Configure Encoder Settings
        video_encoder = "libx264" if codec == "x264" else "libx265"
        crf_value = "23" if codec == "x264" else "28"

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_sub_path}'",
            "-c:v", video_encoder,
            "-preset", "ultrafast",
            "-crf", crf_value,
            "-c:a", "copy",
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_log = stderr.decode()
            await status_msg.edit_text(f"❌ <b>FFmpeg Error:</b>\n<code>{err_log[-500:]}</code>")
            return

        # 4. Upload Output Video
        await status_msg.edit_text("📤 <b>Uploading HardSubbed Video...</b>")
        start_ul = time.time()

        ul_client = bot_client
        if expected_size > (2 * 1024 * 1024 * 1024) and hasattr(bot_client, "user_app") and bot_client.user_app:
            ul_client = bot_client.user_app

        await ul_client.send_video(
            chat_id=trigger_msg.chat.id,
            video=output_path,
            caption=f"🎬 <b>HardSub completed using {codec.upper()}!</b>\n\n👨‍💻 Developer: @Venuboyy",
            progress=progress_bar,
            progress_args=("📤 Uploading Video", status_msg, start_ul)
        )

        await users_col.update_one({"user_id": uid}, {"$inc": {"total_merges": 1}})
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>An unexpected error occurred:</b>\n<code>{str(e)}</code>")

    finally:
        # Cleanup temporary files
        for path in [video_path, sub_path, output_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
