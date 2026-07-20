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

# Extensions used only as a first-pass hint — mime_type is the real source of truth
SUB_EXTENSIONS = ('.srt', '.ass', '.ssa', '.sub', '.vtt', '.txt')
VIDEO_EXTENSIONS = (
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v',
    '.ts', '.m2ts', '.flv', '.wmv', '.3gp', '.mpg', '.mpeg', '.ogv'
)
SUB_MIME_TYPES = (
    'application/x-subrip', 'text/plain', 'application/x-ass',
    'text/vtt', 'application/x-ssa'
)


def classify_file(message: Message, file_name: str, mime_type: str):
    """
    Returns ('video' | 'subtitle' | None) for an incoming video/document message.
    Priority: explicit pyrogram type > mime_type > extension > fallback-to-video.
    Since this bot only ever expects a video or a subtitle, anything that isn't
    clearly a subtitle (by mime or extension) is treated as video. This avoids
    false "Unsupported file format" rejections when a video is forwarded as a
    generic document with a missing/unusual extension or mime_type (common with
    MKV/MP4 files relayed through other bots).
    """
    file_name_lower = (file_name or "").lower()

    # Pyrogram already tells us this is a video message
    if message.video:
        return 'video'

    # Subtitle detection: mime_type first, then extension
    if mime_type and any(mime_type.startswith(m) for m in SUB_MIME_TYPES):
        return 'subtitle'
    if file_name_lower.endswith(SUB_EXTENSIONS):
        return 'subtitle'

    # Video detection: mime_type first, then extension
    if mime_type and mime_type.startswith('video/'):
        return 'video'
    if file_name_lower.endswith(VIDEO_EXTENSIONS):
        return 'video'

    # Reject obviously non-video/subtitle documents (images, audio, archives, etc.)
    if mime_type and (
        mime_type.startswith('image/')
        or mime_type.startswith('audio/')
        or mime_type in ('application/zip', 'application/x-rar-compressed', 'application/pdf')
    ):
        return None

    # Fallback: unknown extension/mime on a document -> assume it's the video
    # (this bot's workflow only ever deals with video + subtitle pairs)
    if message.document:
        return 'video'

    return None


@Client.on_message(filters.private & (filters.video | filters.document))
async def handle_incoming_media(client: Client, message: Message):
    user_id = message.from_user.id

    file_size = 0
    file_name = ""
    mime_type = ""

    if message.video:
        file_size = message.video.file_size
        file_name = message.video.file_name or f"video_{message.id}.mp4"
        mime_type = message.video.mime_type or ""
    elif message.document:
        file_size = message.document.file_size
        file_name = message.document.file_name or f"file_{message.id}"
        mime_type = message.document.mime_type or ""

    kind = classify_file(message, file_name, mime_type)

    if kind is None:
        return await message.reply_text("❌ <b>Unsupported file format!</b> Please send a valid Video or Subtitle file.")

    is_subtitle = kind == 'subtitle'
    is_video = kind == 'video'

    # Initialize user state if missing
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {"video": None, "subtitle": None}

    # STEP 1: Process Video First
    if is_video:
        # Check plan limit for video files
        is_prem = await is_premium_user(user_id)
        max_limit = Config.PREMIUM_LIMIT if is_prem else Config.FREE_LIMIT

        if file_size > max_limit:
            limit_str = "4GB" if is_prem else "2GB"
            return await message.reply_text(
                f"❌ <b>File Exceeds Your Limit!</b>\n"
                f"Your current plan allows up to <b>{limit_str}</b>."
            )

        # Store video message
        USER_STATE[user_id]["video"] = message
        await message.reply_text("✅ <b>Video received!</b> Now send the subtitle file.")
        return

    # STEP 2: Process Subtitle Second
    if is_subtitle:
        # Require video to be sent first
        if not USER_STATE[user_id].get("video"):
            return await message.reply_text("⚠️ <b>Please send the Video file first!</b>")

        USER_STATE[user_id]["subtitle"] = message

    # STEP 3: Prompt for Codec when both are present
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

    # Clear memory state immediately
    USER_STATE.pop(user_id, None)

    await callback_query.message.delete()
    await start_hardsub_pipeline(client, callback_query.message, vid_msg, sub_msg, codec)


async def start_hardsub_pipeline(bot_client: Client, trigger_msg: Message, vid_msg: Message, sub_msg: Message, codec: str):
    status_msg = await trigger_msg.reply_text(f"⏳ <b>Initializing HardSub process ({codec.upper()})...</b>")

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    uid = trigger_msg.chat.id
    ts = int(time.time())

    video_path = os.path.abspath(f"downloads/vid_{uid}_{ts}.mp4")
    sub_path = os.path.abspath(f"downloads/sub_{uid}_{ts}.srt")
    output_path = os.path.abspath(f"outputs/hardsub_{uid}_{ts}.mp4")

    try:
        # 1. Download Subtitle
        await status_msg.edit_text("📥 <b>Downloading Subtitle File...</b>")
        await bot_client.download_media(sub_msg, file_name=sub_path)

        # 2. Download Video File
        file_obj = vid_msg.video or vid_msg.document
        expected_size = file_obj.file_size if file_obj else 0

        start_dl = time.time()
        await status_msg.edit_text("📥 <b>Downloading Video File...</b>")

        dl_client = bot_client
        if expected_size > (2 * 1024 * 1024 * 1024) and hasattr(bot_client, "user_app") and bot_client.user_app:
            dl_client = bot_client.user_app

        dl_file = await dl_client.download_media(
            vid_msg,
            file_name=video_path,
            progress=progress_bar,
            progress_args=("📥 Downloading Video", status_msg, start_dl)
        )

        # Fallback download logic
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

        # Validation
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

        clean_sub_path = sub_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

        if codec == "x265":
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={clean_sub_path}",
                "-c:v", "libx265",
                "-preset", "ultrafast",
                "-x265-params", "log-level=0:no-info=1",
                "-crf", "28",
                "-c:a", "copy",
                output_path
            ]
        else:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={clean_sub_path}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
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

        output_file_size = os.path.getsize(output_path)

        ul_client = bot_client
        if output_file_size > (2 * 1024 * 1024 * 1024) and hasattr(bot_client, "user_app") and bot_client.user_app:
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
