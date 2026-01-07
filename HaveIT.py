import logging
import os
import asyncio
import time
import html
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.error import RetryAfter
import yt_dlp

ALLOWED_CHAT_IDS = [809612055, -1001919485429, 93365812] 
MAX_DURATION_SECONDS = 900 
PROXY_URL = 'socks5://127.0.0.1:3420' 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

active_chats = set()
last_update_time = {}

async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in ALLOWED_CHAT_IDS: return
    
    start_text = (
        "سلام! من ربات دانلود از یوتیوب هستم.\n"
        "لینک بفرست تا عکس و موزیک با کیفیت تحویل بگیری!"
    )
    if update.effective_chat.type == 'private':
        await update.message.reply_text(start_text)

async def handle_youtube_link(update: Update, context: CallbackContext) -> None:
    message_obj = update.message or update.channel_post
    if not message_obj or not message_obj.text: return
        
    chat_id = message_obj.chat.id
    if chat_id not in ALLOWED_CHAT_IDS: return

    youtube_url = message_obj.text
    if "http" not in youtube_url: return 
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url: return
        
    if chat_id in active_chats:
        await message_obj.reply_text('⚠️ یک دانلود در جریان دارید. لطفاً صبر کنید.', quote=True)
        return
        
    active_chats.add(chat_id)
    user_states[chat_id] = {'running': True}

    keyboard = [[InlineKeyboardButton("لغو عملیات ❌", callback_data=f'cancel_{chat_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_message = await message_obj.reply_text(
        '🔍 <b>در حال بررسی لینک و دریافت اطلاعات...</b>', 
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    loop = asyncio.get_running_loop()
    context.application.create_task(
        download_and_upload(youtube_url, chat_id, status_message, context, loop)
    )

def blocking_download_and_process(youtube_url, chat_id, ydl_opts, progress_hook):
    ydl_opts['progress_hooks'] = [progress_hook]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(youtube_url, download=True)
        return info_dict

async def download_and_upload(youtube_url, chat_id, status_message, context, loop):
    global user_states
    file_name_mp3 = None
    thumbnail_path = None

    try:
        def progress_hook_sync(d):
            if not user_states.get(chat_id, {}).get('running'):
                raise yt_dlp.utils.DownloadError("Cancelled")
            
            now = time.time()
            if chat_id in last_update_time:
                if now - last_update_time[chat_id] < 3.0 and d['status'] == 'downloading':
                    return
            
            last_update_time[chat_id] = now
            asyncio.run_coroutine_threadsafe(update_status_message(d, status_message, context), loop)

        ydl_opts = {
            'format': 'bestaudio/best',
            'proxy': PROXY_URL,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_creator', 'android'], 
                    'player_skip': ['webpage', 'configs', 'js'],
                }
            },
            'outtmpl': {'default': '%(title)s.%(ext)s'},
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'writethumbnail': True,
            'noplaylist': True,
            'logger': logger,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            }
        }

        info_dict = await loop.run_in_executor(
            None, blocking_download_and_process, youtube_url, chat_id, ydl_opts, progress_hook_sync
        )

        if not info_dict: raise Exception("اطلاعات دریافت نشد.")
            
        file_name_base = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info_dict)
        file_name_mp3 = os.path.splitext(file_name_base)[0] + '.mp3'
        
        for ext in ['.webp', '.jpg', '.png']:
            possible_path = os.path.splitext(file_name_base)[0] + ext
            if os.path.exists(possible_path):
                thumbnail_path = possible_path
                break

        if not os.path.exists(file_name_mp3):
            raise FileNotFoundError("فایل صوتی یافت نشد.")

        if 'duration' in info_dict and info_dict['duration'] > MAX_DURATION_SECONDS:
            await safe_edit_message(context, status_message, "❌ خطا: فایل بیش از حد طولانی است.")
            return

        raw_title = info_dict.get('title', 'Unknown')
        raw_channel = info_dict.get('uploader', 'Unknown')
        
        safe_title = html.escape(raw_title)
        safe_channel = html.escape(raw_channel)
        
        caption_text = (
            f"🎵 Name: <b>{safe_title}</b>\n"
            f"👤 Channel: <b>{safe_channel}</b>\n"
            f"⚡️ Quality: 320kbps\n\n"
            f"✨ Downloaded by <b>@ytdownplusbot</b>\n"
            f"🎈 By: <b>@sorblack</b>"
        )
        # ---------------------------------------

        if thumbnail_path:
            await update_status_message({'status': 'uploading_photo'}, status_message, context)
            with open(thumbnail_path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,
                    caption=f"🖼 <b>{safe_title}</b>",
                    parse_mode=ParseMode.HTML,
                    connect_timeout=60,
                    read_timeout=60
                )

        if thumbnail_path:
            await update_status_message({'status': 'embedding'}, status_message, context)
            await loop.run_in_executor(
                None, embed_cover_art, file_name_mp3, thumbnail_path, info_dict
            )

        await update_status_message({'status': 'uploading_audio'}, status_message, context)
        with open(file_name_mp3, 'rb') as audio_file:
            thumb_open = open(thumbnail_path, 'rb') if thumbnail_path else None
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                thumbnail=thumb_open,
                title=raw_title,
                performer=raw_channel,
                duration=info_dict.get('duration'),
                caption=caption_text,
                parse_mode=ParseMode.HTML,
                write_timeout=60,
                connect_timeout=60
            )
            if thumb_open: thumb_open.close()
        
        try:
            await context.bot.delete_message(chat_id=status_message.chat.id, message_id=status_message.message_id)
        except: pass

    except Exception as e:
        error_msg = str(e)
        if "Cancelled" in error_msg: text = "⛔️ عملیات لغو شد."
        elif "Sign in" in error_msg: text = "⚠️ یوتیوب درخواست لاگین دارد."
        else: text = f"❌ <b>خطا:</b>\n<code>{html.escape(error_msg)}</code>" # ارور هم باید escape شود
        await safe_edit_message(context, status_message, text, parse_mode=ParseMode.HTML)
        logger.error(f"Error: {e}")
        
    finally:
        if file_name_mp3 and os.path.exists(file_name_mp3): os.remove(file_name_mp3)
        if thumbnail_path and os.path.exists(thumbnail_path): os.remove(thumbnail_path)
        if chat_id in active_chats: active_chats.remove(chat_id)
        if chat_id in user_states: del user_states[chat_id]

def embed_cover_art(mp3_path, image_path, info):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        try: audio.add_tags()
        except: pass
        with open(image_path, 'rb') as art:
            audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art.read()))
        audio.tags.add(TIT2(encoding=3, text=info.get('title', '')))
        audio.tags.add(TPE1(encoding=3, text=info.get('uploader', '')))
        audio.save()
    except Exception as e: logger.error(f"Cover Art Error: {e}")

def make_progress_bar(percent):
    filled = int(percent / 10)
    return "▰" * filled + "▱" * (10 - filled)

async def update_status_message(status_dict, message, context):
    status = status_dict.get('status')
    text = ""
    
    if status == 'downloading':
        try: percent = float(status_dict.get('_percent_str', '0%').replace('%',''))
        except: percent = 0
        text = (
            f"⬇️ <b>در حال دانلود از یوتیوب...</b>\n\n"
            f"{make_progress_bar(percent)} <b>{percent}%</b>\n"
            f"🚀 سرعت: {status_dict.get('_speed_str', 'N/A')}"
        )
    elif status == 'uploading_photo':
        text = "🖼 <b>در حال ارسال تصویر کاور...</b>"
    elif status == 'embedding':
        text = "⚙️ <b>در حال تنظیم تگ‌ها و کاور...</b>"
    elif status == 'uploading_audio':
        text = "📤 <b>در حال آپلود فایل موزیک...</b>"
    
    if text and message.text != text:
        await safe_edit_message(context, message, text, keep_buttons=True, parse_mode=ParseMode.HTML)

async def safe_edit_message(context, message, text, keep_buttons=False, parse_mode=None):
    try:
        reply_markup = message.reply_markup if keep_buttons else None
        await context.bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=message.message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except RetryAfter as e: await asyncio.sleep(e.retry_after)
    except Exception: pass

user_states = {}
async def cancel_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split('_')[1])
    if chat_id in user_states:
        user_states[chat_id]['running'] = False
        await safe_edit_message(context, query.message, "🛑 لغو شد.")

def main() -> None:
    if not BOT_TOKEN:
        print("Error: TOKEN not found. Set TELEGRAM_BOT_TOKEN env variable.")
        return
    application = (
        Application.builder().token(BOT_TOKEN)
        .connect_timeout(60).read_timeout(60).write_timeout(60)
        .build()
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel_'))
    print("Secure Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
