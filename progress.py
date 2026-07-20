import time
import math
from pyrogram.types import Message

async def progress_bar(current: int, total: int, status_text: str, message: Message, start_time: float):
    now = time.time()
    diff = now - start_time
    if diff == 0:
        return

    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff)
    eta = round((total - current) / speed) if speed > 0 else 0

    filled_length = int(round(12 * current / float(total)))
    bar = '█' * filled_length + '░' * (12 - filled_length)

    progress_str = (
        f"<b>{status_text}</b>\n\n"
        f"[{bar}] {percentage:.2f}%\n\n"
        f"🚀 <b>Speed:</b> {human_bytes(speed)}/s\n"
        f"📦 <b>Processed:</b> {human_bytes(current)} / {human_bytes(total)}\n"
        f"⏱️ <b>ETA:</b> {time_formatter(eta)}\n"
    )

    # Update progress every 4 seconds to avoid rate limits
    if not hasattr(progress_bar, "last_updated"):
        progress_bar.last_updated = {}

    msg_id = message.id
    if msg_id not in progress_bar.last_updated or (now - progress_bar.last_updated[msg_id]) > 4:
        try:
            await message.edit_text(progress_str)
            progress_bar.last_updated[msg_id] = now
        except Exception:
            pass

def human_bytes(size: int) -> str:
    if not size:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {units[i]}"

def time_formatter(seconds: int) -> str:
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((f"{days}d, " if days else "") +
           (f"{hours}h, " if hours else "") +
           (f"{minutes}m, " if minutes else "") +
           (f"{seconds}s" if seconds else ""))
    return tmp[:-2] if tmp.endswith(", ") else tmp or "0s"
