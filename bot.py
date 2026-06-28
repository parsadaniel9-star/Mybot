import os
import re
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = "8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o"
REQUIRED_CHANNELS = ["@chaayy0"]
RAPIDAPI_KEY = "e56243e197mshbe6077d2ae26f7ap12531fjsnf12ff9fff7d0"

AUDIO_HOST = "youtube-mp3-2025.p.rapidapi.com"
AUDIO_URL = "https://youtube-mp3-2025.p.rapidapi.com/v1/social/youtube/audio"
VIDEO_HOST = "youtube-mp36.p.rapidapi.com"
VIDEO_URL = "https://youtube-mp36.p.rapidapi.com/dl"


def extract_video_id(url):
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


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
        buttons.append([InlineKeyboardButton(f"📢 عضویت در {ch}", url=f"https://t.me/{name}")])
    buttons.append([InlineKeyboardButton("✅ عضو شدم، تایید کن", callback_data="check_membership")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            f"👋 سلام {user.first_name}!\n\nبرای استفاده از ربات عضو کانال زیر شو:",
            reply_markup=membership_keyboard(not_joined)
        )
        return
    await send_welcome(update.message, user.first_name)


async def send_welcome(message, first_name):
    await message.reply_text(
        f"👋 سلام {first_name}!\n\n"
        "🎬 لینک یوتیوب رو بفرست تا دانلود کنم."
    )


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await query.message.edit_text(
            "❌ هنوز عضو نشدی! اول عضو شو بعد تایید کن:",
            reply_markup=membership_keyboard(not_joined)
        )
        return
    await query.message.delete()
    await send_welcome(query.message, user.first_name)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ لطفاً لینک یوتیوب بفرست.")
        return

    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            "⚠️ ابتدا عضو کانال شو:",
            reply_markup=membership_keyboard(not_joined)
        )
        return

    video_id = extract_video_id(url)
    if not video_id:
        await update.message.reply_text("❌ لینک یوتیوب معتبر نیست.")
        return

    context.user_data["video_id"] = video_id

    buttons = [
        [
            InlineKeyboardButton("🎬 1080p", callback_data="dl_video_1080"),
            InlineKeyboardButton("🎬 720p", callback_data="dl_video_720"),
            InlineKeyboardButton("🎬 480p", callback_data="dl_video_480"),
        ],
        [
            InlineKeyboardButton("🎬 360p", callback_data="dl_video_360"),
            InlineKeyboardButton("🎬 240p", callback_data="dl_video_240"),
            InlineKeyboardButton("🎬 144p", callback_data="dl_video_144"),
        ],
        [
            InlineKeyboardButton("🎵 MP3 320kbps", callback_data="dl_audio_320"),
            InlineKeyboardButton("🎵 MP3 128kbps", callback_data="dl_audio_128"),
        ],
    ]

    await update.message.reply_text(
        "👇 کیفیت مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    video_id = context.user_data.get("video_id")

    if not video_id:
        await query.message.edit_text("❌ لینک پیدا نشد. دوباره بفرست.")
        return

    parts = data.split("_")
    dl_type = parts[1]
    quality = parts[2]

    await query.message.edit_text("⏳ در حال پردازش...")

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "Content-Type": "application/json",
    }

    try:
        if dl_type == "audio":
            headers["x-rapidapi-host"] = AUDIO_HOST
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    AUDIO_URL,
                    json={"id": video_id},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()

            # لینک دانلود
            download_url = result.get("url") or result.get("link") or result.get("download_url")
            title = result.get("title", "audio")

            if not download_url:
                await query.message.edit_text(f"❌ خطا در دریافت لینک:\n{str(result)[:200]}")
                return

            await query.message.edit_text("⬇️ در حال دانلود...")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    download_url,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    content = await resp.read()

            size_mb = len(content) / (1024 * 1024)
            if size_mb > 50:
                await query.message.edit_text(f"❌ حجم {size_mb:.1f}MB زیاده.")
                return

            await query.message.edit_text(f"📤 در حال آپلود ({size_mb:.1f}MB)...")
            await query.message.reply_audio(
                audio=content,
                title=title,
                filename=f"{title}.mp3"
            )

        else:
            # دانلود ویدیو با API اول
            headers["x-rapidapi-host"] = VIDEO_HOST
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{VIDEO_URL}?id={video_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()

            status = result.get("status")
            if status != "ok":
                await query.message.edit_text("❌ خطا در دریافت ویدیو. کیفیت دیگه‌ای امتحان کن.")
                return

            # پیدا کردن لینک با کیفیت مناسب
            links = result.get("link", [])
            download_url = None
            title = result.get("title", "video")

            quality_int = int(quality)
            best_url = None
            best_diff = 99999

            for item in links:
                q = item.get("quality", "")
                numbers = re.findall(r"\d+", q)
                if numbers:
                    q_int = int(numbers[0])
                    diff = abs(q_int - quality_int)
                    if diff < best_diff:
                        best_diff = diff
                        best_url = item.get("url")

            download_url = best_url

            if not download_url:
                await query.message.edit_text("❌ این کیفیت موجود نیست. کیفیت دیگه‌ای امتحان کن.")
                return

            await query.message.edit_text("⬇️ در حال دانلود...")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    download_url,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    content = await resp.read()

            size_mb = len(content) / (1024 * 1024)
            if size_mb > 50:
                await query.message.edit_text(
                    f"❌ حجم {size_mb:.1f}MB زیاده.\nکیفیت پایین‌تر امتحان کن."
                )
                return

            await query.message.edit_text(f"📤 در حال آپلود ({size_mb:.1f}MB)...")
            await query.message.reply_video(
                video=content,
                caption=title,
                supports_streaming=True
            )

        await query.message.delete()

    except Exception as e:
        await query.message.edit_text(f"❌ خطا:\n{str(e)}")


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
