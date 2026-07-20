import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from database import is_premium_user, users_col
from progress import progress_bar

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

    # Plan validation
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

    if USER_STATE[user_id]["video"] and USER_STATE[user_id]["subtitle"]:
        vid_msg = USER_STATE[user_id]["video"]
        sub_msg = USER_STATE[user_id]["subtitle"]
        USER_STATE[user_id] = {"video": None, "subtitle": None}
        
        await start_hardsub_pipeline(client, message, vid_msg, sub_msg)


async def start_hardsub_pipeline(bot_client: Client, trigger_msg: Message, vid_msg: Message, sub_msg: Message):
    status_msg = await trigger_msg.reply_text("⏳ <b>Initializing HardSub process...</b>")
    
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    uid = trigger_msg.from_user.id
    ts = int(time.time())
    
    video_path = f"downloads/vid_{uid}_{ts}.mp4"
    sub_path = f"downloads/sub_{uid}_{ts}.srt"
    output_path = f"outputs/hardsub_{uid}_{ts}.mp4"

    try:
        # 1. Download Subtitle
        await status_msg.edit_text("📥 <b>Downloading Subtitle File...</b>")
        await bot_client.download_media(sub_msg, file_name=sub_path)

        # 2. Download Video using the bot client safely
        # Note: Bot client downloads up to 2GB files fine. Use user_app if present and available.
        target_client = bot_client
        if hasattr(bot_client, "user_app") and bot_client.user_app:
            target_client = bot_client.user_app

        expected_size = vid_msg.video.file_size if vid_msg.video else vid_msg.document.file_size

        start_dl = time.time()
        await status_msg.edit_text("📥 <b>Downloading Video File...</b>")
        
        dl_file = await target_client.download_media(
            vid_msg,
            file_name=video_path,
            progress=progress_bar,
            progress_args=("📥 Downloading Video", status_msg, start_dl)
        )

        # Validate download completion
        if not dl_file or not os.path.exists(video_path):
            return await status_msg.edit_text("❌ <b>Download failed: File not created.</b>")

        downloaded_size = os.path.getsize(video_path)
        if downloaded_size < expected_size:
            return await status_msg.edit_text(
                f"❌ <b>Incomplete download!</b>\n"
                f"Expected: {expected_size} bytes | Downloaded: {downloaded_size} bytes.\n"
                "Please try sending the file again."
            )

        # 3. FFmpeg HardSub Processing
        await status_msg.edit_text("⚡ <b>Merging subtitles into video...</b>")
        
        escaped_sub_path = sub_path.replace(":", "\\:").replace("'", "'\\\\''")
        
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_sub_path}'",
            "-c:a", "copy",
            "-preset", "ultrafast",
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
            await status_msg.edit_text(f"❌ <b>FFmpeg Error:</b>\n<code>{err_log[-400:]}</code>")
            return

        # 4. Upload HardSubbed Video
        await status_msg.edit_text("📤 <b>Uploading HardSubbed Video...</b>")
        start_ul = time.time()

        await target_client.send_video(
            chat_id=trigger_msg.chat.id,
            video=output_path,
            caption="🎬 <b>HardSub process completed successfully!</b>\n\n👨‍💻 Developer: @Venuboyy",
            progress=progress_bar,
            progress_args=("📤 Uploading Video", status_msg, start_ul)
        )

        await users_col.update_one({"user_id": uid}, {"$inc": {"total_merges": 1}})
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>An unexpected error occurred:</b> {str(e)}")

    finally:
        # File Cleanup
        for path in [video_path, sub_path, output_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
