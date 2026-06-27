import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = "8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o"
REQUIRED_CHANNELS = ["@chaayy0"]
ADMIN_ID = None


async def check_membership(user_id, context):
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)
    return not_joined


def membership_keyboard(not_joined):
    buttons = []
    for ch in not_joined:
        name = ch.lstrip("@")
        buttons.append([InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{name}")])
    buttons.append([InlineKeyboardButton("تایید عضویت", callback_data="check_membership")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            f"سلام {user.first_name}!\nبرای استفاده از ربات عضو کانال زیر شو:",
            reply_markup=membership_keyboard(not_joined)
        )
        return
    await send_welcome(update.message, user.first_name)


async def send_welcome(message, first_name):
    await message.reply_text(
        f"سلام {first_name}!\nلینک یوتیوب رو بفرست تا دانلود کنم."
    )


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await query.message.edit_text(
            "هنوز عضو نشدی! اول عضو شو بعد تایید کن:",
            reply_markup=membership_keyboard(not_joined)
        )
        return
    await query.message.delete()
    await send_welcome(query.message, user.first_name)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("لطفا لینک یوتیوب بفرست.")
        return

    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            "ابتدا عضو کانال شو:",
            reply_markup=membership_keyboard(not_joined)
        )
        return

    msg = await update.message.reply_text("در حال بررسی لینک...")

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await msg.edit_text(f"خطا: {str(e)}")
        return

    title = info.get("title", "ویدیو")
    duration = info.get("duration", 0)
    mins = duration // 60
    secs = duration % 60

    formats = info.get("formats", [])
    seen = set()
    video_qualities = []
    for f in formats:
        h = f.get("height")
        if h and f.get("vcodec") != "none" and h not in seen:
            seen.add(h)
            video_qualities.append(h)
    video_qualities = sorted(video_qualities, reverse=True)

    context.user_data["url"] = url
    context.user_data["title"] = title

    buttons = []
    row = []
    for q in video_qualities[:6]:
        row.append(InlineKeyboardButton(f"{q}p", callback_data=f"dl_video_{q}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("MP3 320kbps", callback_data="dl_audio_320"),
        InlineKeyboardButton("MP3 128kbps", callback_data="dl_audio_128"),
    ])

    await msg.delete()
    await update.message.reply_text(
        f"{title}\n{mins}:{secs:02d}\n\nکیفیت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    url = context.user_data.get("url")
    title = context.user_data.get("title", "فایل")

    if not url:
        await query.message.edit_text("لینک پیدا نشد. دوباره بفرست.")
        return

    parts = data.split("_")
    dl_type = parts[1]
    quality = parts[2]

    await query.message.edit_text("در حال دانلود...")

    output_path = f"/tmp/tg_{query.from_user.id}"
    os.makedirs(output_path, exist_ok=True)

    try:
        if dl_type == "audio":
            ydl_opts = {
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality,
                }],
                "quiet": True,
            }
        else:
            ydl_opts = {
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "format": f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]",
                "merge_output_format": "mp4",
                "quiet": True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = os.listdir(output_path)
        if not files:
            await query.message.edit_text("دانلود ناموفق بود.")
            return

        file_path = os.path.join(output_path, files[0])
        size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if size_mb > 50:
            await query.message.edit_text(f"حجم {size_mb:.1f}MB زیاده. کیفیت پایین‌تر امتحان کن.")
            return

        await query.message.edit_text(f"در حال آپلود ({size_mb:.1f}MB)...")

        with open(file_path, "rb") as f:
            if dl_type == "audio":
                await query.message.reply_audio(audio=f, title=title)
            else:
                await query.message.reply_video(video=f, caption=title, supports_streaming=True)

        await query.message.delete()

    except Exception as e:
        await query.message.edit_text(f"خطا: {str(e)}")
    finally:
        if os.path.exists(output_path):
            for f in os.listdir(output_path):
                os.remove(os.path.join(output_path, f))
            os.rmdir(output_path)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    print("ربات شروع به کار کرد...")
    app.run_polling()


if __name__ == "__main__":
    main()
