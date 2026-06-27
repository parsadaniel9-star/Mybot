import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ===================== تنظیمات =====================
BOT_TOKEN = "8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o"

# آیدی کانال‌هایی که کاربر باید عضو باشه
# مثال: REQUIRED_CHANNELS = ["@mychannel", "@mychannel2"]
REQUIRED_CHANNELS = ["@chaayy0"]

# آیدی ادمین (اختیاری - برای اطلاع از خطاها)
ADMIN_ID = None
# ===================================================


async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> list:
    """لیست کانال‌هایی که کاربر عضو نیست رو برمی‌گردونه"""
    not_joined = []
    for channel in REQUIRED_CHANNELS: https:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)
    return not_joined


def membership_keyboard(not_joined: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in not_joined:
        name = ch.lstrip("@")
        buttons.append([InlineKeyboardButton(f"📢 عضویت در {ch}", url=f"https://t.me/{name}")])
    buttons.append([InlineKeyboardButton("✅ عضو شدم، تأیید کن", callback_data="check_membership")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if REQUIRED_CHANNELS:
        not_joined = await check_membership(user.id, context)
        if not_joined:
            await update.message.reply_text(
                f"👋 سلام {user.first_name}!\n\n"
                "برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شو:",
                reply_markup=membership_keyboard(not_joined)
            )
            return

    await send_welcome(update.message, user.first_name)


async def send_welcome(message, first_name: str):
    await message.reply_text(
        f"👋 سلام {first_name}!\n\n"
        "🎬 لینک ویدیوی یوتیوب رو برام بفرست تا دانلودش کنم.\n\n"
        "📌 فقط لینک‌های یوتیوب پشتیبانی میشه."
    )


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if REQUIRED_CHANNELS:
        not_joined = await check_membership(user.id, context)
        if not_joined:
            await query.message.edit_text(
                "❌ هنوز در همه کانال‌ها عضو نشدی!\n\nلطفاً اول عضو شو بعد تأیید کن:",
                reply_markup=membership_keyboard(not_joined)
            )
            return

    await query.message.delete()
    await send_welcome(query.message, user.first_name)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ لطفاً یه لینک یوتیوب معتبر بفرست.")
        return

    # بررسی عضویت
    if REQUIRED_CHANNELS:
        not_joined = await check_membership(user.id, context)
        if not_joined:
            await update.message.reply_text(
                "⚠️ ابتدا باید در کانال‌های زیر عضو بشی:",
                reply_markup=membership_keyboard(not_joined)
            )
            return

    msg = await update.message.reply_text("🔍 در حال بررسی لینک...")

    # گرفتن اطلاعات ویدیو
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await msg.edit_text(f"❌ خطا در بررسی لینک:\n{str(e)}")
        return

    title = info.get("title", "ویدیو")
    duration = info.get("duration", 0)
    thumb = info.get("thumbnail", "")
    mins = duration // 60
    secs = duration % 60

    # پیدا کردن کیفیت‌های موجود
    formats = info.get("formats", [])
    seen = set()
    video_qualities = []
    for f in formats:
        h = f.get("height")
        if h and f.get("vcodec") != "none" and h not in seen:
            seen.add(h)
            video_qualities.append(h)
    video_qualities = sorted(video_qualities, reverse=True)

    # ذخیره اطلاعات
    context.user_data["url"] = url
    context.user_data["title"] = title

    # ساخت کیبورد
    buttons = []

    # ردیف‌های کیفیت ویدیو
    row = []
    for q in video_qualities[:6]:  # حداکثر 6 کیفیت
        row.append(InlineKeyboardButton(f"🎬 {q}p", callback_data=f"dl_video_{q}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # ردیف صدا
    buttons.append([
        InlineKeyboardButton("🎵 MP3 - 320kbps", callback_data="dl_audio_320"),
        InlineKeyboardButton("🎵 MP3 - 128kbps", callback_data="dl_audio_128"),
    ])

    keyboard = InlineKeyboardMarkup(buttons)

    await msg.delete()
    await update.message.reply_text(
        f"🎬 *{title}*\n"
        f"⏱ مدت: {mins}:{secs:02d}\n\n"
        "👇 کیفیت مورد نظر رو انتخاب کن:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # مثال: dl_video_720 یا dl_audio_320
    url = context.user_data.get("url")
    title = context.user_data.get("title", "فایل")

    if not url:
        await query.message.edit_text("❌ لینک پیدا نشد. دوباره لینک بفرست.")
        return

    parts = data.split("_")
    dl_type = parts[1]   # video یا audio
    quality = parts[2]   # مثلاً 720 یا 320

    await query.message.edit_text("⏳ در حال دانلود، صبر کن...")

    output_path = f"/tmp/tg_{query.from_user.id}_{query.id}"
    os.makedirs(output_path, exist_ok=True)

    try:
        if dl_type == "audio":
            bitrate = quality  # 320 یا 128
            ydl_opts = {
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }],
                "quiet": True,
                "no_warnings": True,
            }
            type_label = f"🎵 MP3 {bitrate}kbps"

        else:  # video
            height = quality  # مثلاً 720
            ydl_opts = {
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
            }
            type_label = f"🎬 ویدیو {height}p"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = os.listdir(output_path)
        if not files:
            await query.message.edit_text("❌ دانلود ناموفق بود.")
            return

        file_path = os.path.join(output_path, files[0])
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)

        if file_size > 50 * 1024 * 1024:
            await query.message.edit_text(
                f"❌ حجم فایل {size_mb:.1f}MB هست و تلگرام فقط تا 50MB رو قبول می‌کنه.\n"
                "یه کیفیت پایین‌تر امتحان کن."
            )
            return

        await query.message.edit_text(f"📤 در حال آپلود ({size_mb:.1f}MB)...")

        caption = f"{type_label}\n🎬 {title}"

        with open(file_path, "rb") as f:
            if dl_type == "audio":
                await query.message.reply_audio(
                    audio=f,
                    title=title,
                    caption=caption
                )
            else:
                await query.message.reply_video(
                    video=f,
                    caption=caption,
                    supports_streaming=True
                )

        await query.message.delete()

    except Exception as e:
        await query.message.edit_text(f"❌ خطا:\n{str(e)}")

    finally:
        # پاک کردن فایل‌های موقت
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

    print("✅ ربات شروع به کار کرد...")
    app.run_polling()


if __name__ == "__main__":
    main()
