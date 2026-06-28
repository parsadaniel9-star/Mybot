import os
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = "8910395655:AAEZuuWT96CZx3lDLVQe5ey8ShEGHLo6R4o"
REQUIRED_CHANNELS = ["@chaayy0"]
COBALT_API = "https://api.cobalt.tools/api/json"


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


async def get_cobalt(url, quality="1080", audio_only=False, audio_quality="320"):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "vQuality": quality,
        "aFormat": "mp3",
        "isAudioOnly": audio_only,
        "isAudioMuted": False,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(COBALT_API, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            return data


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

    context.user_data["url"] = url

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
    url = context.user_data.get("url")

    if not url:
        await query.message.edit_text("❌ لینک پیدا نشد. دوباره بفرست.")
        return

    parts = data.split("_")
    dl_type = parts[1]
    quality = parts[2]

    await query.message.edit_text("⏳ در حال دریافت لینک دانلود...")

    try:
        audio_only = dl_type == "audio"
        result = await get_cobalt(url, quality=quality, audio_only=audio_only, audio_quality=quality)

        status = result.get("status")

        if status not in ["stream", "redirect", "tunnel"]:
            error = result.get("text", "خطای ناشناخته")
            await query.message.edit_text(f"❌ خطا: {error}")
            return

        download_url = result.get("url")
        filename = result.get("filename", "video.mp4")

        await query.message.edit_text("⬇️ در حال دانلود و آپلود...")

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                content = await resp.read()

        size_mb = len(content) / (1024 * 1024)

        if size_mb > 50:
            await query.message.edit_text(
                f"❌ حجم {size_mb:.1f}MB زیاده.\nکیفیت پایین‌تر امتحان کن."
            )
            return

        await query.message.edit_text(f"📤 در حال آپلود ({size_mb:.1f}MB)...")

        if audio_only:
            await query.message.reply_audio(
                audio=content,
                filename=filename,
                title=filename.replace(".mp3", "")
            )
        else:
            await query.message.reply_video(
                video=content,
                filename=filename,
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
