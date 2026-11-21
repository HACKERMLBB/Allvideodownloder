import os
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

    if choice == 'audio':
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        }
    elif choice == 'best':
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': 'best[ext=mp4][filesize<48M]/best[filesize<48M]/best',
            'noplaylist': True,
            'quiet': True,
        }
    else:
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': f'bestvideo[height<={choice}][ext=mp4]+bestaudio[ext=m4a]/best[height<={choice}][filesize<48M]/best',
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'quiet': True,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if choice == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'

        if os.path.getsize(filename) > 50 * 1024 * 1024:
            await msg.edit_text("😢 *File Too Big!* Telegram limit is 50MB.\nTry lower quality or /audio 🎧", parse_mode="Markdown")
            os.remove(filename)
            return

        await msg.edit_text("📤 *Uploading now...* 🚀", parse_mode="Markdown")

        with open(filename, 'rb') as f:
            if choice == 'audio':
                await query.message.reply_audio(audio=f, title=info.get('title', 'Audio'), caption=f"🎧 *{info.get('title', 'Audio')}* ✅", parse_mode="Markdown")
            else:
                await query.message.reply_video(video=f, caption=f"✅ *{info.get('title', 'Video')}* 🎬\n\nDownloaded by @YourBot", parse_mode="Markdown")

        os.remove(filename)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"⚠️ *Error:* `{str(e)[:400]}`\n\n🔒 Try another link or check if video is private.", parse_mode="Markdown")

def main():
    # Start Web Server in background thread for Render Port
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
    main()
