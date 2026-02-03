import logging
import os
import asyncio
import time
import html
import subprocess
import requests
import re
import json
import math
import glob
from thefuzz import fuzz
from bs4 import BeautifulSoup
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Chat
from telegram.constants import ParseMode, ChatType, ChatMemberStatus
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackContext, 
    CallbackQueryHandler,
    ChatMemberHandler
)
from telegram.error import RetryAfter, TimedOut, BadRequest, Forbidden
import yt_dlp

# --- CONFIGURATION ---
ALLOWED_CHAT_IDS = [809612055, -1001919485429, 93365812, 114726592]
MAX_DURATION_SECONDS = 1200
PROXY_URL = 'socks5://127.0.0.1:3420'
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_DATA_DIR = "Users_Data"
# ---------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

active_chats = set()
last_update_time = {}
user_states = {}


def get_user_folder(user_id):
    path = os.path.join(BASE_DATA_DIR, str(user_id))
    if not os.path.exists(path): os.makedirs(path, exist_ok=True)
    return path

def save_user_channel(user_id, channel_id, channel_title, channel_username=None):
    user_path = get_user_folder(user_id)
    data = {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "channel_username": channel_username,
        "set_at": time.time()
    }
    with open(os.path.join(user_path, "config.json"), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_channel(user_id):
    config_file = os.path.join(get_user_folder(user_id), "config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return None
    return None

def delete_user_channel(user_id):
    config_file = os.path.join(get_user_folder(user_id), "config.json")
    if os.path.exists(config_file):
        os.remove(config_file)
        return True
    return False


def human_readable_size(size):
    if not size: return "..."
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels.get(n, '')}B"

def human_readable_time(seconds):
    if not seconds or seconds < 0: return "..."
    try:
        val = int(seconds)
        m, s = divmod(val, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
    except: return "..."


def rotate_warp_ip():
    """Disconnects and Reconnects Warp to get a fresh IP."""
    try:
        # logger.info("♻️ Rotating Warp IP...")
        subprocess.run(['warp-cli', 'disconnect'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        time.sleep(2)
        subprocess.run(['warp-cli', 'connect'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        time.sleep(5)
        print("✅ [AUTO-HEAL] New IP Assigned Successfully.\n")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to rotate IP: {e}")
        return False

def get_spotify_metadata(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                full = title_tag.text.strip().replace('| Spotify', '')
                if " - song by " in full: return full.split(" - song by ")[0], full.split(" - song by ")[1]
                elif " by " in full: return full.split(" by ")[0], full.split(" by ")[-1]
                return full, ""
    except: pass
    return None, None

def smart_find_best_match(song_name, artist_name, ydl_opts_base):
    """
    Algorithm V4 (Linear Popularity):
    Difference: Use linear score for views.
    112M views = 100 points.
    12M views = 12 points.
    This makes the original version win over fakes!
    """
    search_query = f"{artist_name} - {song_name}"
    opts = ydl_opts_base.copy()
    opts['extract_flat'] = True
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        try: res = ydl.extract_info(f"ytsearch10:{search_query}", download=False)
        except: return None
    
    if not res or 'entries' not in res: return None
    candidates = res['entries']
    
    best_video = None
    highest_score = -500 
    
    target_clean = f"{artist_name} {song_name}".lower()
    artist_lower = artist_name.lower()

    for vid in candidates:
        if not vid: continue
        
        vid_title = vid.get('title', '')
        vid_channel = vid.get('uploader', '') or vid.get('channel', '')
        view_count = vid.get('view_count', 0) or 0
        duration = vid.get('duration', 0)
        
        score = 0
        
        popularity_score = min(view_count / 1000000, 80)
        score += popularity_score
        
        if " - Topic" in vid_channel: 
            score += 50 
        elif artist_lower in vid_channel.lower(): 
            score += 40
        elif "VEVO" in vid_channel.upper():
            score += 30
            
        similarity = fuzz.token_set_ratio(target_clean, vid_title.lower())
        score += (similarity * 0.5) 
        
        if duration > 600: score -= 50
        if duration < 90: score -= 20 
        
        vid_title_low = vid_title.lower()
        if "remix" in vid_title_low and "remix" not in target_clean: score -= 100
        if "cover" in vid_title_low: score -= 100
        if "live" in vid_title_low and "live" not in target_clean: score -= 50
        
        if "official video" in vid_title_low or "official music video" in vid_title_low:
            score += 15

        if score > highest_score:
            highest_score = score
            best_video = vid

    if highest_score < 10 and candidates: return candidates[0].get('url')
    return best_video.get('url') if best_video else None


def clean_ansi(text):
    """Clean ANSI color codes."""
    if not text: return None
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', str(text)).strip()

async def on_my_chat_member_update(update: Update, context: CallbackContext):
    if not update.my_chat_member: return
    new = update.my_chat_member.new_chat_member
    chat = update.my_chat_member.chat
    user = update.my_chat_member.from_user 
    if user.id not in ALLOWED_CHAT_IDS: return

    if new.status == ChatMemberStatus.ADMINISTRATOR:
        if new.can_post_messages:
            old_ch = get_user_channel(user.id)
            if old_ch and str(old_ch['channel_id']) != str(chat.id):
                try: await context.bot.leave_chat(old_ch['channel_id'])
                except: pass
            save_user_channel(user.id, chat.id, chat.title, chat.username)
            try: await context.bot.send_message(user.id, f"✅ Channel <b>{html.escape(chat.title)}</b> connected successfully.", parse_mode=ParseMode.HTML)
            except: pass
    elif new.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        ch = get_user_channel(user.id)
        if ch and str(ch['channel_id']) == str(chat.id):
            delete_user_channel(user.id)


START_TEXT = (
    "🎧 <b>Smart Music Assistant</b>\n\n"
    "Send your link from the following services:\n"
    "🔴 YouTube\n"
    "🟢 Spotify\n"
    "🟠 SoundCloud\n\n"
    "I am equipped with a smart search engine.\n"
    "I download for you with the highest possible quality (320kbps)!\n\n"
    "To connect to a channel (even private), tap the Settings button."
)

async def start(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id not in ALLOWED_CHAT_IDS: return
    kb = [[InlineKeyboardButton("Settings ⚙️", callback_data='settings_home')]]
    if update.message: await update.message.reply_text(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    else: await update.callback_query.edit_message_text(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def settings_command(update: Update, context: CallbackContext):
    await show_settings_menu(update, context, True)

async def show_settings_menu(update: Update, context: CallbackContext, is_new=False):
    user_id = update.effective_user.id
    ch = get_user_channel(user_id)
    
    if ch:
        text = (
            f"⚙️ <b>Channel Management</b>\n\n"
            f"🟢 <b>Connected to:</b> {html.escape(ch['channel_title'])}\n"
            f"🆔 <code>{ch['channel_id']}</code>\n\n"
            f"What would you like to do?"
        )
        kb = [
            [InlineKeyboardButton("Change Channel 🔄", callback_data='ask_change_channel')],
            [InlineKeyboardButton("Disconnect & Leave ❌", callback_data='ask_disconnect')],
            [InlineKeyboardButton("Back 🔙", callback_data='main_menu')]
        ]
    else:
        text = (
            "⚙️ <b>Settings</b>\n\n"
            "🔴 <b>No channel connected.</b>\n"
            "By connecting a channel, you can forward music directly."
        )
        kb = [
            [InlineKeyboardButton("Connect New Channel ➕", callback_data='show_connect_guide')],
            [InlineKeyboardButton("Back 🔙", callback_data='main_menu')]
        ]

    markup = InlineKeyboardMarkup(kb)
    if is_new: await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else: await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def callback_handler(update: Update, context: CallbackContext):
    q = update.callback_query
    data = q.data
    user_id = q.from_user.id
    
    if data == 'main_menu': await start(update, context)
    elif data == 'settings_home': await show_settings_menu(update, context)
    elif data == 'show_connect_guide':
        txt = "📢 <b>Smart Connection Guide</b>\n\n1️⃣ Enter your channel.\n2️⃣ Make me (the bot) an <b>Admin</b>.\n3️⃣ Done! I will detect the channel automatically."
        kb = [[InlineKeyboardButton("Back 🔙", callback_data='settings_home')]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'ask_disconnect':
        ch = get_user_channel(user_id)
        if not ch: return await show_settings_menu(update, context)
        txt = f"⚠️ <b>Warning</b>\n\nAre you sure you want to remove channel <b>{ch['channel_title']}</b>?\n‼️ I will leave the channel."
        kb = [[InlineKeyboardButton("Yes, Remove ✅", callback_data='do_disconnect'), InlineKeyboardButton("No 🔙", callback_data='settings_home')]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'do_disconnect':
        ch = get_user_channel(user_id)
        if ch:
            try: await context.bot.leave_chat(chat_id=ch['channel_id'])
            except: pass
            delete_user_channel(user_id)
            await q.answer("Disconnected.")
            await show_settings_menu(update, context)

    elif data == 'ask_change_channel':
        ch = get_user_channel(user_id)
        txt = f"🔄 <b>Change Destination</b>\n\nCurrent Channel: <b>{ch['channel_title']}</b>\nDo you want to replace it?"
        kb = [[InlineKeyboardButton("Yes, Change 🔄", callback_data='show_connect_guide'), InlineKeyboardButton("No 🔙", callback_data='settings_home')]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith('send_to_ch_'):
        try:
            parts = data.split('_')
            audio_id = int(parts[3])
            photo_id = int(parts[4]) if parts[4] != '0' else None
            ch = get_user_channel(user_id)
            if ch:
                if photo_id: await context.bot.copy_message(chat_id=ch['channel_id'], from_chat_id=q.message.chat_id, message_id=photo_id)
                await context.bot.copy_message(chat_id=ch['channel_id'], from_chat_id=q.message.chat_id, message_id=audio_id)
                await q.answer("✅ Sent!")
                await q.edit_message_text("✅ <b>Successfully sent to channel.</b>", parse_mode=ParseMode.HTML)
            else: await q.answer("❌ Channel not found.", show_alert=True)
        except Exception as e: 
            logger.error(f"Send Error: {e}")
            await q.answer("❌ Error sending.", show_alert=True)

    elif data == 'cancel_send': await q.message.delete()
    elif data.startswith('cancel_dl_'):
        chat_id = int(data.split('_')[2])
        if chat_id in user_states:
            user_states[chat_id]['running'] = False
            await q.answer("🛑 Requesting cancel...")
            await q.edit_message_text("⛔️ <b>Operation cancelled by user.</b>", parse_mode=ParseMode.HTML)


async def handle_message(update: Update, context: CallbackContext):
    msg = update.message or update.channel_post
    if not msg or not msg.text: return
    chat_id = msg.chat.id
    if chat_id not in ALLOWED_CHAT_IDS: return
    
    text = msg.text.strip()
    platform = None
    if "youtube.com" in text or "youtu.be" in text: platform = "YouTube"
    elif "soundcloud.com" in text: platform = "SoundCloud"
    elif "spotify.com" in text: platform = "Spotify"
    
    if platform:
        if chat_id in active_chats:
            await msg.reply_text('⚠️ You have an active process. Please wait.')
            return
        active_chats.add(chat_id)
        user_states[chat_id] = {'running': True, 'start_time': time.time()}
        kb = [[InlineKeyboardButton("Cancel Operation ❌", callback_data=f'cancel_dl_{chat_id}')]]
        status = await msg.reply_text(f"🔍 <b>Checking {platform} link...</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        asyncio.create_task(process_media(text, platform, chat_id, status, context, msg))

async def process_media(url, platform, chat_id, status_msg, context, origin_msg):
    loop = asyncio.get_running_loop()
    display_source_name = "Unknown" 
    file_name_mp3 = None
    thumbnail_path = None
    filename_stem = None

    def cleanup_now():
        """Cleans up all associated files (main, part, temp, cover)."""
        try:
            if file_name_mp3 and os.path.exists(file_name_mp3): os.remove(file_name_mp3)
            if thumbnail_path and os.path.exists(thumbnail_path): os.remove(thumbnail_path)

            if filename_stem:
                search_pattern = f"{glob.escape(filename_stem)}*"
                found_files = glob.glob(search_pattern)
                for f in found_files:
                    try:
                        if os.path.exists(f): os.remove(f)
                    except: pass
        except Exception as e:
            print(f"Cleanup Error: {e}")

    try:
        download_target = url
        
        if platform == "Spotify":
            await safe_edit(status_msg, "🟢 <b>Extracting metadata from Spotify...</b>", chat_id)
            song, artist = await loop.run_in_executor(None, get_spotify_metadata, url)
            if song:
                display_source_name = artist 
                await safe_edit(status_msg, f"🔎 <b>Smart searching for original version...</b>\n🎶 {artist} - {song}", chat_id)
                temp_opts = {'proxy': PROXY_URL, 'quiet': True, 'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}}
                best = await loop.run_in_executor(None, smart_find_best_match, song, artist, temp_opts)
                download_target = best if best else f"ytsearch1:{artist} - {song} Audio"
            else: raise Exception("Spotify link could not be read.")

        for attempt in range(1, 4): 
            try:
                if not user_states.get(chat_id, {}).get('running'): raise yt_dlp.utils.DownloadError("Cancelled")

                ydl_opts_base = {
                    'format': 'bestaudio/best', 'proxy': PROXY_URL, 'noplaylist': True, 'writethumbnail': True,
                    'nocheckcertificate': True, 'outtmpl': {'default': '%(title)s.%(ext)s'},
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '320'}],
                    'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
                    'http_headers': {'User-Agent': 'Mozilla/5.0'}
                }
                
                info_dict = await loop.run_in_executor(
                    None, lambda: yt_dlp.YoutubeDL(ydl_opts_base).extract_info(download_target, download=False)
                )
                
                if 'entries' in info_dict: info_dict = info_dict['entries'][0]
                if not info_dict: raise Exception("Information not received.")

                full_filename = yt_dlp.YoutubeDL(ydl_opts_base).prepare_filename(info_dict)
                filename_stem = os.path.splitext(full_filename)[0]
                file_name_mp3 = filename_stem + '.mp3'

                duration = info_dict.get('duration', 0)
                if duration > MAX_DURATION_SECONDS:
                    duration_min = duration // 60
                    limit_min = MAX_DURATION_SECONDS // 60
                    await safe_edit(status_msg, f"❌ <b>Error:</b> Video is {duration_min} minutes long.\n(Max allowed: {limit_min} minutes)", chat_id, remove_keyboard=True)
                    cleanup_now()
                    if chat_id in active_chats: active_chats.remove(chat_id)
                    if chat_id in user_states: del user_states[chat_id]
                    return

                def hook(d):
                    if not user_states.get(chat_id, {}).get('running'): raise yt_dlp.utils.DownloadError("Cancelled")
                    now = time.time()
                    if chat_id in last_update_time:
                        if now - last_update_time[chat_id] < 3.0 and d['status'] == 'downloading': return
                    last_update_time[chat_id] = now
                    asyncio.run_coroutine_threadsafe(update_status_message(d, status_msg, chat_id), loop)
                
                if attempt == 1:
                    await safe_edit(status_msg, "⬇️ <b>Confirmed. Starting download...</b>", chat_id)
                else: 
                    await safe_edit(status_msg, "🔄 <b>Retrying with new IP (Auto-Heal)...</b>", chat_id)

                await loop.run_in_executor(None, blocking_download, download_target, ydl_opts_base, hook)
                break

            except Exception as e:
                error_msg = str(e)
                
                if "Cancelled" in error_msg: 
                    await safe_edit(status_msg, "⛔️ <b>Operation cancelled.</b>", chat_id, remove_keyboard=True)
                    await asyncio.sleep(1)
                    cleanup_now()
                    
                    if chat_id in active_chats: active_chats.remove(chat_id)
                    if chat_id in user_states: del user_states[chat_id]
                    return 

                if "Sign in" in error_msg or "429" in error_msg or "unavailable" in error_msg or "403" in error_msg or "Forbidden" in error_msg:
                    if attempt < 3: 
                        await safe_edit(status_msg, "⚠️ <b>Network error detected.</b>\n🛠 Diagnosing and switching secure network path (Auto-Fix)...", chat_id)
                        await loop.run_in_executor(None, rotate_warp_ip)
                        continue 
                
                text = f"❌ <b>Error:</b>\n<code>{html.escape(error_msg)}</code>"
                if "Sign in" in error_msg: text = "❌ Auto-attempt failed. YouTube denied access."
                elif "Timed out" in error_msg: text = "⏳ Upload timed out."
                
                await safe_edit(status_msg, text, chat_id, remove_keyboard=True)
                cleanup_now()
                logger.error(f"Error: {e}")
                
                if chat_id in active_chats: active_chats.remove(chat_id)
                if chat_id in user_states: del user_states[chat_id]
                return

        if not user_states.get(chat_id, {}).get('running'): raise yt_dlp.utils.DownloadError("Cancelled")
        if not file_name_mp3 or not os.path.exists(file_name_mp3): raise Exception("Download failed.") 

        for ext in ['.webp', '.jpg', '.png']:
            possible_thumb = filename_stem + ext
            if os.path.exists(possible_thumb): 
                thumbnail_path = possible_thumb
                break

        if platform != "Spotify":
            raw_uploader = info_dict.get('uploader', '') or info_dict.get('channel', 'Unknown')
            display_source_name = raw_uploader.replace(" - Topic", "").replace("VEVO", "").replace("Official", "").strip()

        if thumbnail_path: await loop.run_in_executor(None, embed_cover, file_name_mp3, thumbnail_path, info_dict, display_source_name)

        await safe_edit(status_msg, "📤 <b>Uploading to Telegram...</b>", chat_id)
        
        title = info_dict.get('title', 'Unknown')
        safe_title = html.escape(title)
        safe_source = html.escape(display_source_name)
        
        caption = (
            f"🎵 Name: <b>{safe_title}</b>\n"
            f"👤 Artist/Source: <b>{safe_source}</b>\n"
            f"📱 Platform: <b>{platform}</b>\n"
            f"⚡️ Quality: 320kbps\n\n"
            f"✨ Downloaded by <b>@{context.bot.username}</b>\n"
            f"🎈 By: <b>@sorblack</b>"
        )
        
        sent_photo = None
        if thumbnail_path:
            with open(thumbnail_path, 'rb') as photo_file:
                sent_photo = await context.bot.send_photo(
                    chat_id=chat_id, photo=photo_file, caption=f"🖼 <b>{safe_title}</b>", parse_mode=ParseMode.HTML, connect_timeout=300, read_timeout=300
                )

        with open(file_name_mp3, 'rb') as f:
            th = open(thumbnail_path, 'rb') if thumbnail_path else None
            sent_audio = await context.bot.send_audio(
                chat_id=chat_id, audio=f, thumbnail=th, title=title, performer=safe_source, caption=caption, parse_mode=ParseMode.HTML, read_timeout=300, write_timeout=300
            )
            if th: th.close()
            
        try: await status_msg.delete()
        except: pass

        if origin_msg.chat.type == ChatType.PRIVATE:
            ch = get_user_channel(origin_msg.from_user.id)
            if ch:
                pid = sent_photo.message_id if sent_photo else 0
                aid = sent_audio.message_id
                kb = [[InlineKeyboardButton("✅ Send to Channel", callback_data=f'send_to_ch_{aid}_{pid}'), InlineKeyboardButton("Close", callback_data='cancel_send')]]
                await context.bot.send_message(chat_id, f"Send to <b>{ch['channel_title']}</b>?", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML, reply_to_message_id=sent_audio.message_id)
            else:
                kb = [[InlineKeyboardButton("Set Channel", callback_data='settings_home')]]
                await context.bot.send_message(chat_id, "💡 Channel is not set.", reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        if "Cancelled" in str(e):
            await safe_edit(status_msg, "⛔️ <b>Operation cancelled.</b>", chat_id, remove_keyboard=True)
            cleanup_now()
        else:
            await safe_edit(status_msg, f"❌ Error: {e}", chat_id, remove_keyboard=True)
            logger.error(e)
            cleanup_now()
            
    finally:
        cleanup_now()
        
        if chat_id in active_chats: active_chats.remove(chat_id)
        if chat_id in user_states: del user_states[chat_id]


def blocking_download(url, opts, hook):
    opts['progress_hooks'] = [hook]
    with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(url, download=True)

def embed_cover(mp3, img, info, artist_name=""):
    try:
        audio = MP3(mp3, ID3=ID3)
        try: audio.add_tags()
        except: pass
        with open(img, 'rb') as f: audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=f.read()))
        audio.tags.add(TIT2(encoding=3, text=info.get('title','')))
        final_artist = artist_name if artist_name else info.get('uploader','')
        audio.tags.add(TPE1(encoding=3, text=final_artist))
        audio.save()
    except: pass

def make_progress_bar(percent):
    filled = int(percent / 10)
    return "▰" * filled + "▱" * (10 - filled)

async def update_status_message(status_dict, message, chat_id):
    status = status_dict.get('status')
    text = ""
    
    if status == 'downloading':
        try:
            downloaded = status_dict.get('downloaded_bytes', 0)
            total = status_dict.get('total_bytes') or status_dict.get('total_bytes_estimate', 0)
            
            start_time = user_states.get(chat_id, {}).get('start_time', time.time())
            elapsed = time.time() - start_time
            if elapsed < 1: elapsed = 1

            speed_str = clean_ansi(status_dict.get('_speed_str'))
            
            if not speed_str or "N/A" in speed_str or "Unknown" in speed_str:
                speed_bytes = downloaded / elapsed
                speed_str = f"{human_readable_size(speed_bytes)}/s"
            
            current_speed = status_dict.get('speed')
            if not current_speed: current_speed = downloaded / elapsed

            eta_str = "..."
            time_label = "⏳ Time"

            native_eta = clean_ansi(status_dict.get('_eta_str'))
            
            if native_eta and "N/A" not in native_eta and ":" in native_eta:
                eta_str = native_eta
            else:
                if total > 0 and current_speed > 0:
                    eta_seconds = (total - downloaded) / current_speed
                    if eta_seconds > 1200:
                        time_label = "⏱ Elapsed"
                        eta_str = human_readable_time(elapsed)
                    else:
                        eta_str = human_readable_time(eta_seconds)
                else:
                    time_label = "⏱ Elapsed"
                    eta_str = human_readable_time(elapsed)

            if total > 0:
                p = (downloaded / total) * 100
            else:
                p = 0

            size_str = clean_ansi(status_dict.get('_total_bytes_str')) or clean_ansi(status_dict.get('_total_bytes_estimate_str'))
            if not size_str or "N/A" in size_str:
                size_str = human_readable_size(total) if total else "..."


            text = (
                f"📥 <b>Downloading...</b>\n\n"
                f"{make_progress_bar(p)} <b>{int(p)}%</b>\n\n"
                f"🚀 Speed: <b>{speed_str}</b>\n"
                f"💾 Size: <b>{size_str}</b>\n"
                f"{time_label}: <b>{eta_str}</b>"
            )
        except Exception:
            text = f"📥 <b>Downloading...</b>"
    
    if text and message.text != text:
        await safe_edit(message, text, chat_id)

async def safe_edit(message, text, chat_id, remove_keyboard=False):
    try:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel Operation ❌", callback_data=f'cancel_dl_{chat_id}')]]) if not remove_keyboard else None
        await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except RetryAfter as e: await asyncio.sleep(e.retry_after)
    except Exception: pass

def main():
    if not BOT_TOKEN: return
    if not os.path.exists(BASE_DATA_DIR): os.makedirs(BASE_DATA_DIR)
    
    app = Application.builder().token(BOT_TOKEN).connect_timeout(300).read_timeout(300).write_timeout(300).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(ChatMemberHandler(on_my_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Full Fixed Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
