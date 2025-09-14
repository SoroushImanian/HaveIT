import logging
import os
import asyncio
import time
import requests
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.error import RetryAfter
import yt_dlp


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# List of Allowed People and Channels - Enter your IDs here :
ALLOWED_CHAT_IDS = [809612055, -1001919485429, 93365812] 

MAX_DURATION_SECONDS = 600 #10 min - You can change it

active_chats = set()
USER_COOLDOWNS = {}
COOLDOWN_SECONDS = 20


async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in ALLOWED_CHAT_IDS: return
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
        'سلام! من ربات دانلود از یوتیوب هستم.\n'
        'فقط کافیه لینک ویدیوی یوتیوب رو برام بفرستی تا به صورت فایل صوتی (MP3 320kbps) تحویل بدم.'
        )

async def handle_youtube_link(update: Update, context: CallbackContext) -> None:
    message_obj = update.message or update.channel_post
    if not message_obj or not message_obj.text: return
        
    chat_id = message_obj.chat.id
    if chat_id not in ALLOWED_CHAT_IDS:
        logger.warning(f"دسترسی غیرمجاز از chat_id: {chat_id}")
        return

    if chat_id in USER_COOLDOWNS:
        time_since_last = time.time() - USER_COOLDOWNS[chat_id]
        if time_since_last < COOLDOWN_SECONDS:
            remaining_time = int(COOLDOWN_SECONDS - time_since_last)
            await message_obj.reply_text(f'شما یک محدودیت زمانی دارید. لطفاً {remaining_time} ثانیه دیگر دوباره تلاش کنید.', quote=True)
            return

    youtube_url = message_obj.text
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        if message_obj.chat.type == 'private': await message_obj.reply_text('لطفاً یک لینک معتبر از یوتیوب ارسال کنید.')
        return
        
    if chat_id in active_chats:
        await message_obj.reply_text('شما یک دانلود دیگر در حال انجام دارید. لطفاً تا پایان آن صبر کنید.', quote=True)
        return
        
    active_chats.add(chat_id)
    user_states[chat_id] = {'running': True}

    keyboard = [[InlineKeyboardButton("لغو عملیات ❌", callback_data=f'cancel_{chat_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    status_message = await message_obj.reply_text('در حال پردازش... لطفاً صبر کنید.', reply_markup=reply_markup)

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
                raise yt_dlp.utils.DownloadError("Download cancelled by user.")
            asyncio.run_coroutine_threadsafe(update_status_message(d, status_message, context), loop)

        await update_status_message({'status': 'preprocess'}, status_message, context)

        ydl_opts = {
            'format': 'bestaudio/best',
            'cookiefile': '/root/youtube-cookies.txt',
            'outtmpl': {'default': '%(title)s.%(ext)s'},
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'writethumbnail': True,
            'noplaylist': True,
            'logger': logger,
        }

        info_dict = await loop.run_in_executor(
            None, blocking_download_and_process, youtube_url, chat_id, ydl_opts, progress_hook_sync
        )

        if not info_dict:
            raise Exception("اطلاعات ویدیو دریافت نشد.")
            
        file_name_base = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info_dict)
        file_name_mp3 = os.path.splitext(file_name_base)[0] + '.mp3'
        
        thumbnail_path_webp = os.path.splitext(file_name_base)[0] + '.webp'
        thumbnail_path_jpg = os.path.splitext(file_name_base)[0] + '.jpg'
        
        if os.path.exists(thumbnail_path_webp):
            thumbnail_path = thumbnail_path_webp
        elif os.path.exists(thumbnail_path_jpg):
            thumbnail_path = thumbnail_path_jpg

        if not os.path.exists(file_name_mp3):
            raise FileNotFoundError("فایل MP3 ساخته نشد!")

        if 'duration' in info_dict and info_dict['duration'] > MAX_DURATION_SECONDS:
            duration_min = info_dict['duration'] // 60
            await safe_edit_message(context, status_message, f"خطا: این ویدیو {duration_min} دقیقه است. حداکثر زمان مجاز ۱۰ دقیقه می‌باشد.")
            return

        if thumbnail_path:
            await update_status_message({'status': 'embedding'}, status_message, context)
            await loop.run_in_executor(
                None, embed_cover_art, file_name_mp3, thumbnail_path, info_dict
            )

        await update_status_message({'status': 'uploading'}, status_message, context)
        with open(file_name_mp3, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=info_dict.get('title'),
                performer=info_dict.get('channel'),
                duration=info_dict.get('duration'),
                caption=f"Downloaded by @{context.bot.username} - @sorblack"
            )
        await context.bot.delete_message(chat_id=status_message.chat.id, message_id=status_message.message_id)

    except Exception as e:
        error_message = f"یک خطای غیرمنتظره رخ داد: {e}"
        if isinstance(e, yt_dlp.utils.DownloadError):
            error_message = f"خطا در دانلود از یوتیوب: {str(e).split(': ERROR: ')[-1]}"
        logger.error(error_message)
        await safe_edit_message(context, status_message, error_message)
    finally:
        for path in [file_name_mp3, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)
        if chat_id in active_chats:
            active_chats.remove(chat_id)
        if chat_id in user_states:
            del user_states[chat_id]
        USER_COOLDOWNS[chat_id] = time.time()

def embed_cover_art(mp3_path, image_path, info):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass
        
        with open(image_path, 'rb') as art:
            audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art.read()))
        
        audio.tags.add(TIT2(encoding=3, text=info.get('title', '')))
        audio.tags.add(TPE1(encoding=3, text=info.get('channel', '')))
        audio.save()
    except Exception as e:
        logger.error(f"خطا در چسباندن کاور: {e}")

async def update_status_message(status_dict, message, context):
    text = "در حال پردازش..."
    if status_dict['status'] == 'downloading':
        percent = status_dict.get('_percent_str', 'N/A')
        speed = status_dict.get('_speed_str', 'N/A')
        text = f"در حال دانلود: {percent} با سرعت {speed}"
    elif status_dict['status'] == 'finished':
        text = "دانلود تمام شد، در حال تبدیل به MP3..."
    elif status_dict['status'] == 'preprocess':
        text = "در حال دریافت اطلاعات ویدیو..."
    elif status_dict['status'] == 'embedding':
        text = "در حال چسباندن کاور به فایل..."
    elif status_dict['status'] == 'uploading':
        text = "فایل آماده شد! در حال آپلود..."
        
    await safe_edit_message(context, message, text, keep_buttons=True)

async def safe_edit_message(context, message, text, keep_buttons=False):
    try:
        reply_markup = message.reply_markup if keep_buttons else None
        await context.bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=message.message_id, reply_markup=reply_markup)
    except RetryAfter: logger.warning("Flood control exceeded. Skipping message edit.")
    except Exception: pass

user_states = {}
async def cancel_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split('_')[1])
    if chat_id in user_states:
        user_states[chat_id]['running'] = False
        logger.info(f"درخواست لغو برای {chat_id} ثبت شد.")
        await safe_edit_message(context, query.message, "درخواست لغو ارسال شد. عملیات متوقف خواهد شد...")

def main() -> None:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("توکن ربات در متغیر محیطی TELEGRAM_BOT_TOKEN یافت نشد!")
        
    application = (
        Application.builder()
        .token(TOKEN).connect_timeout(120).read_timeout(120).write_timeout(120)
        .build()
    )
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel_'))
    print("ربات دانلودر (نسخه نهایی و پایدار با yt-dlp) در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()