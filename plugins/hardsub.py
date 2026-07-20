import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from database import is_premium_user
from progress import progress_bar

# Temporary dictionary to track state (video and subtitle pairing)
USER_STATE = {}

@Client.on_message(filters.private & (filters.video | filters.document))
async def handle_incoming_file(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check File Size Limits
    file_size = 0
    file_name = ""
    
    if message.video:
        file_size = message.video.file_size
        file_name = message.video.file_name or f"video_{message.id}.mp4"
    elif message.document:
        file_size = message.document.file_size
        file_name = message.document.file_name or f"file_{message.id}"

    is_premium = await is_premium_user(user_id)
    max_limit = Config.PREMIUM_LIMIT if is_premium else Config.FREE_LIMIT

    if file_size > max_limit:
        limit_gb = 4 if is_premium else 2
        return await message.reply_text(f"❌ <b>File size exceeds your plan limit of {limit_gb}GB.</b>")

    # Detect subtitle extension
    is_sub = file_name.endswith(('.srt', '.ass', '.ssa', '.sub', '.txt'))
    
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {"video": None, "subtitle": None}

    if is_sub:
        USER_STATE[user_id]["subtitle"] = message
        await message.reply_text("✅ <b>Subtitle file received!</b>\nNow send the video file to start hardsubbing.")
    else:
        USER_STATE[user_id]["video"] = message
        await message.reply_text("✅ <b>Video file received!</b>\nNow send the subtitle file (.srt, .ass, etc.).")

    # If both files are provided, initiate merge
    if USER_STATE[user_id]["video"] and USER_STATE[user_id]["subtitle"]:
        vid_msg = USER_STATE[user_id]["video"]
        sub_msg = USER_STATE[user_id]["subtitle"]
        # Clear state
        USER_STATE[user_id] = {"video": None, "subtitle": None}
        
        await start_hardsub_process(client, message, vid_msg, sub_msg)

async def start_hardsub_process(bot_client: Client, user_msg: Message, vid_msg: Message, sub_msg: Message):
    status_msg = await user_msg.reply_text("⏳ <b>Initializing processing...</b>")
    
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    video_path = f"downloads/vid_{user_msg.from_user.id}_{int(time.time())}.mp4"
    sub_path = f"downloads/sub_{user_msg.from_user.id}_{int(time.time())}.srt"
    output_path = f"outputs/hardsub_{user_msg.from_user.id}_{int(time.time())}.mp4"

    try:
        # 1. Download Subtitle
        await status_msg.edit_text("📥 <b>Downloading Subtitle...</b>")
        await bot_client.download_media(sub_msg, file_name=sub_path)

        # 2. Download Video (Use User Session if available for faster speed/large files)
        start_time = time.time()
        await status_msg.edit_text("📥 <b>Downloading Video...</b>")
        dl_client = getattr(bot_client, "user_app", bot_client)
        
        await dl_client.download_media(
            vid_msg,
            file_name=video_path,
            progress=progress_bar,
            progress_args=("📥 Downloading Video", status_msg, start_time)
        )

        # 3. FFmpeg Hardsub Processing
        await status_msg.edit_text("⚙️ <b>Merging Subtitles (FFmpeg)... This may take time.</b>")
        
        # Escape path for FFmpeg subtitles filter
        escaped_sub_path = sub_path.replace(":", "\\:").replace("'", "'\\\\''")
        
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_sub_path}'",
            "-c:a", "copy",
            "-preset", "veryfast",
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

        # 4. Upload Result
        await status_msg.edit_text("📤 <b>Uploading Processed Video...</b>")
        upload_start = time.time()
        
        await dl_client.send_video(
            chat_id=user_msg.chat.id,
            video=output_path,
            caption="🎬 <b>Hardsub process completed successfully!</b>",
            progress=progress_bar,
            progress_args=("📤 Uploading Video", status_msg, upload_start)
        )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>An error occurred:</b> {str(e)}")

    finally:
        # Cleanup files
        for path in [video_path, sub_path, output_path]:
            if os.path.exists(path):
                os.remove(path)
