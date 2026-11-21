import os
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.environ.get("PORT", 10000))

# --- Fake Web Server for Render ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "🤖 Bot is Alive! ✅"

@app_web.route('/health')
def health():
    return "OK", 200

def run_web():
    app_web.run(host="0.0.0.0", port=PORT)

# --- Telegram Bot ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Video Downloader Bot!* 🤖✨\n\n"
        "📥 *Send me any link from:*\n"
        "▶️ YouTube\n"
        "🎵 TikTok\n"
        "📸 Instagram\n"
        "📘 Facebook\n"
        "🐦 Twitter / X\n"
        "🔴 Reddit\n"
        "🎥 Vimeo\n"
        "🔊 SoundCloud\n"
        "🎮 Twitch\n\n"
        "🌍 *1000+ sites supported via yt-dlp!*\n\n"
        "💡 *Commands:*\n"
        "/audio - Download MP3 Only 🎧\n"
        "/help - Help Menu ❓\n\n"
        "🚀 *Just send a link to start!*",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *How To Use Me:*\n\n"
        "1️⃣ Send any video / audio link\n"
        "2️⃣ Choose quality from buttons 👇\n"
        "3️⃣ Wait for download ⏳\n"
        "4️⃣ Get your file 📤\n\n"
        "⚠️ *Limits:*\n"
        "• Telegram Max: 50MB\n"
        "• Long videos -> Use /audio\n\n"
        "🎧 *Tip:* Type /audio before sending link for MP3",
        parse_mode="Markdown"
    )

async def audio_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['audio_only'] = True
    await update.message.reply_text(
        "🎧 *Audio Mode ON!* ✅\n\nNow send me a link and I'll send MP3 only. 🎶",
        parse_mode="Markdown"
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text("❌ Please send a valid URL starting with http/https")
        return

    context.user_data['url'] = url
    context.user_data['audio_only'] = False

    keyboard = [
        [InlineKeyboardButton("🎧 Audio MP3", callback_data="audio")],
        [InlineKeyboardButton("📱 480p SD", callback_data="480"),
         InlineKeyboardButton("📺 720p HD", callback_data="720")],
        [InlineKeyboardButton("🎬 1080p Full HD", callback_data="1080"),
         InlineKeyboardButton("✨ Best <50MB", callback_data="best")],
    ]
    await update.message.reply_text(
        "🎬 *Choose Quality:* 👇\n\n"
        "What do you want?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    url = context.user_data.get('url')

    if not url:
        await query.edit_message_text("❌ Link expired, please send again. 🔄")
        return

    msg = await query.edit_message_text("⏳ *Downloading... Please wait!* 🕐", parse_mode="Markdown")
    os.makedirs('downloads', exist_ok=True)

    # --- BASE OPTIONS - YOUTUBE FIX ---
    base_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragments': 5,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36',
        },
    }

    # Add cookies if file exists
    if os.path.exists('cookies.txt'):
        base_opts['cookiefile'] = 'cookies.txt'

    if choice == 'audio':
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        }
    elif choice == 'best':
        ydl_opts = {
            **base_opts,
            'format': 'best[height<=720][filesize<48M]/best[height<=720]/best[filesize<48M]/best',
        }
    else:
        # 480 / 720 / 1080
        height = int(choice)
        ydl_opts = {
            **base_opts,
            'format': f'bestvideo[height<={height}][filesize<48M]+bestaudio/bestvideo[height<={height}]+bestaudio/best[height<={height}][filesize<48M]/best[height<={height}]/best',
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if choice == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'

        if not os.path.exists(filename):
            # Find file if extension changed
            import glob
            files = glob.glob('downloads/*')
            if files:
                filename = max(files, key=os.path.getctime)

        if os.path.getsize(filename) > 50 * 1024 * 1024:
            await msg.edit_text("😢 *File Too Big!* Telegram limit is 50MB.\nTry lower quality or /audio 🎧", parse_mode="Markdown")
            os.remove(filename)
            return

        await msg.edit_text("📤 *Uploading now...* 🚀", parse_mode="Markdown")

        with open(filename, 'rb') as f:
            if choice == 'audio':
                await query.message.reply_audio(audio=f, title=info.get('title', 'Audio'), caption=f"🎧 *{info.get('title', 'Audio')}* ✅", parse_mode="Markdown")
            else:
                await query.message.reply_video(video=f, caption=f"✅ *{info.get('title', 'Video')}* 🎬", parse_mode="Markdown")

        os.remove(filename)
        await msg.delete()

    except Exception as e:
        error_msg = str(e)[:400]
        await msg.edit_text(f"⚠️ *Error:* `{error_msg}`\n\n🔒 Try another link or check if video is private.", parse_mode="Markdown")

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("audio", audio_mode))
    app.add_handler(CallbackQueryHandler(handle_quality))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    print(f"🤖 Bot Started on Port {PORT}...")
    app.run_polling()

if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
