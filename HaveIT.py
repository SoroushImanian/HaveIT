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
ALLOWED_CHAT_IDS = [809611155, -1001919409429, 93389812, 110725592]
MAX_DURATION_SECONDS = 1200
PROXY_URL = 'socks5://127.0.0.1:3420'
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_DATA_DIR = "Users_Data"
CACHE_CHANNEL_ID = -100384683897
CACHE_FILE = os.path.join(BASE_DATA_DIR, "global_cache.json")
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

def load_global_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_to_global_cache(unique_key, audio_msg_id, photo_msg_id=None):
    cache = load_global_cache()
    cache[unique_key] = {
        'audio': audio_msg_id,
        'photo': photo_msg_id,
        'timestamp': time.time()
    }
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

def get_from_cache(unique_key):
    cache = load_global_cache()
    return cache.get(unique_key)

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
    "\n"
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
            # اصلاح: تبدیل دقیق آیدی عکس
            photo_id = int(parts[4]) if parts[4] != '0' else None
            
            ch = get_user_channel(user_id)
            
            if ch:
                # 1. اول تلاش برای ارسال عکس (اگر وجود دارد)
                if photo_id: 
                    try: 
                        await context.bot.copy_message(chat_id=ch['channel_id'], from_chat_id=q.message.chat_id, message_id=photo_id)
                    except Exception as e: 
                        logger.error(f"Banner Send Error: {e}") # اگر عکس نشد، ادامه بده و آهنگ رو بفرست
                
                # 2. ارسال آهنگ و دریافت نتیجه
                sent_msg = await context.bot.copy_message(chat_id=ch['channel_id'], from_chat_id=q.message.chat_id, message_id=audio_id)
                
                # ذخیره در هیستوری
                target_audio = q.message.reply_to_message.audio if q.message.reply_to_message else None
                if target_audio:
                    clean_a = clean_text_for_search(target_audio.performer or "")
                    clean_t = clean_text_for_search(target_audio.title or "")
                    unique_key = f"{clean_a}_{clean_t}"
                    save_to_history(user_id, unique_key, sent_msg.message_id)

                await q.answer("✅ Sent!")
                
                # ساخت لینک جدید
                new_link = get_message_link(ch['channel_id'], sent_msg.message_id, ch.get('channel_username'))
                
                # نکته مهم: آیدی پیام ارسال شده (sent_msg.message_id) را در دکمه بازگشت ذخیره میکنیم
                # فرمت جدید: restore_menu_AudioID_PhotoID_SentMessageID
                kb = [[InlineKeyboardButton("🔗 View in Channel", url=new_link)],
                      [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"restore_menu_{audio_id}_{photo_id or 0}_{sent_msg.message_id}")]]
                
                await q.edit_message_text(
                    f"✅ <b>Successfully sent to channel:</b>\n📢 {html.escape(ch['channel_title'])}", 
                    reply_markup=InlineKeyboardMarkup(kb), 
                    parse_mode=ParseMode.HTML
                )
            else: 
                await q.answer("❌ Channel not found.", show_alert=True)
        except Exception as e: 
            logger.error(f"Send Error: {e}")
            await q.answer("❌ Error sending to channel.", show_alert=True)

    elif data.startswith('restore_menu_'):
        parts = data.split('_')
        aid = parts[2]
        pid = parts[3]
        
        # گرفتن آیدی پیام ارسال شده (اگر قبلا ارسال شده باشد)
        # اگر عدد بزرگتر از 1 باشد یعنی آیدی پیام است، اگر 0 یا 1 باشد یعنی فلگ قدیمی
        sent_msg_id = int(parts[4]) if len(parts) > 4 else 0
        
        kb_buttons = []
        ch = get_user_channel(user_id)
        
        # اگر پیام قبلاً ارسال شده (آیدی معتبر داریم) و کانال هنوز هست
        if sent_msg_id > 1 and ch:
            link = get_message_link(ch['channel_id'], sent_msg_id, ch.get('channel_username'))
            kb_buttons.append([InlineKeyboardButton("🔗 View in Channel", url=link)])
        else:
            # اگر هنوز ارسال نشده یا آیدی نداریم، دکمه ارسال را نشان بده
            kb_buttons.append([InlineKeyboardButton("✅ Send to Channel", callback_data=f'send_to_ch_{aid}_{pid}')])
            
        kb_buttons.append([
            InlineKeyboardButton("📝 Get Lyrics", callback_data=f'get_lyrics_{aid}'),
            InlineKeyboardButton("❌ Close", callback_data='cancel_send')
        ])
        
        await q.edit_message_text(
            "File Ready! 👇", 
            reply_markup=InlineKeyboardMarkup(kb_buttons),
            parse_mode=ParseMode.HTML
        )   
    
    elif data.startswith('cancel_dl_'):
        chat_id = int(data.split('_')[2])
        if chat_id in user_states:
            user_states[chat_id]['running'] = False
            await q.answer("🛑 Requesting cancel...")
            await q.edit_message_text("⛔️ <b>Operation cancelled by user.</b>", parse_mode=ParseMode.HTML)

    elif data.startswith('get_lyrics_'):
        try:
            await q.answer("🔍 Searching Genius & LrcLib...", cache_time=0)
            
            audio_msg_id = int(data.split('_')[2])
            chat_id = q.message.chat_id
            
            target_audio = None
            if q.message.reply_to_message and q.message.reply_to_message.audio:
                target_audio = q.message.reply_to_message.audio
            
            if not target_audio:
                await q.edit_message_text("❌ Reference audio file not found.", parse_mode=ParseMode.HTML)
                return

            raw_artist = target_audio.performer or ""
            raw_title = target_audio.title or ""
            
            lyrics, source = await asyncio.get_running_loop().run_in_executor(
                None, get_lyrics_smart, raw_artist, raw_title
            )
            
            if lyrics:
                header = f"🎤 <b>{html.escape(raw_title)}</b>\n\n"
                footer = f"\n\n✅ Source: <b>{source}</b>"
                
                if len(lyrics) > 3000:
                    with open("Lyrics.txt", "w", encoding="utf-8") as f:
                        f.write(f"{raw_artist} - {raw_title}\nSource: {source}\n\n{lyrics}")
                    with open("Lyrics.txt", "rb") as f:
                        await context.bot.send_document(
                            chat_id=chat_id, document=f, caption="📝 Full Lyrics File", reply_to_message_id=audio_msg_id
                        )
                    os.remove("Lyrics.txt")
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=header + f"<code>{html.escape(lyrics)}</code>" + footer,
                        parse_mode=ParseMode.HTML,
                        reply_to_message_id=audio_msg_id
                    )
            else:
                clean_q = clean_text_for_search(raw_title)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Lyrics not found.\n\nI searched for:\n<b>{html.escape(clean_q)}</b>\n\nDatabase returned no results (Maybe instrumental?).",
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=audio_msg_id
                )

        except Exception as e:
            logger.error(f"Lyrics Error: {e}")
            await q.answer("❌ Search Error.", show_alert=True)


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


def clean_text_for_search(text):
    """
    V6 Cleaner: Handles Nightcore brackets, years, genres, and splits features.
    """
    if not text: return ""
    text = str(text)
    
    text = re.sub(r'[\(\[\u300c].*?[\)\]\u300d]', '', text)
    
    text = re.sub(r'\b(19|20)\d{2}\b', '', text)
    
    junk_words = [
        'official video', 'official music video', 'official audio', 
        'lyrics', 'lyric video', 'visualizer', 'remastered', 'remaster',
        '4k', 'hd', 'hq', 'mv', 'cover', 'live', 'mix', 'original mix',
        'extended mix', 'club mix', 'uplifting trance', 'trance', 'house',
        'dubstep', 'techno', 'pop', 'rap', 'nightcore', 'slowed', 'reverb'
    ]
    
    lower_text = text.lower()
    for junk in junk_words:
        if junk in lower_text:
            pattern = re.compile(re.escape(junk), re.IGNORECASE)
            text = pattern.sub('', text)

    text = re.sub(r'(?i)\b(ft\.?|feat\.?|featuring|prod\.?|with|by|x)\b.*', '', text)
    
    text = text.replace('"', '').replace("'", "").replace("|", "").replace("_", " ").replace("-", " ")
    
    return " ".join(text.split())

def check_similarity(input_str, result_str):
    """
    Verifies if the result matches the request.
    Returns True if similarity is acceptable (>60%).
    """
    if not input_str or not result_str: return False
    ratio = fuzz.token_set_ratio(input_str.lower(), result_str.lower())
    return ratio >= 60

def search_genius_direct(query):
    """ Source 2: Genius Search """
    try:
        url = "https://genius.com/api/search/multi"
        params = {'q': query, 'per_page': '1'}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            for section in data.get('response', {}).get('sections', []):
                if section.get('type') in ['top_results', 'song'] and section.get('hits'):
                    hit = section['hits'][0]['result']
                    page_url = f"https://genius.com{hit['path']}"
                    page_resp = requests.get(page_url, headers=headers, timeout=5)
                    if page_resp.status_code == 200:
                        soup = BeautifulSoup(page_resp.content, 'html.parser')
                        lyrics_divs = soup.find_all('div', {'data-lyrics-container': 'true'})
                        if lyrics_divs:
                            return "\n".join([div.get_text(separator="\n") for div in lyrics_divs]), "Genius.com"
    except: pass
    return None, None

def cleanup_files(file_mp3, thumb_path, stem):
    try:
        if file_mp3 and os.path.exists(file_mp3): os.remove(file_mp3)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
        if stem:
            for f in glob.glob(f"{glob.escape(stem)}*"):
                try: os.remove(f)
                except: pass
    except Exception as e:
        print(f"Cleanup Error: {e}")

async def process_media(url, platform, chat_id, status_msg, context, origin_msg):
    loop = asyncio.get_running_loop()
    display_source_name = "Unknown" 
    file_name_mp3 = None
    thumbnail_path = None
    filename_stem = None
    unique_key = None
    info_dict = None 
    
    final_audio_msg = None
    final_photo_msg = None

    cache_audio_id = None
    cache_photo_id = None
    
    freshly_downloaded_photo = False
    freshly_downloaded_audio = False

    try:
        download_target = url
        
        if platform == "Spotify":
            await safe_edit(status_msg, "🟢 <b>Processing...</b>", chat_id)
            song, artist = await loop.run_in_executor(None, get_spotify_metadata, url)
            if song:
                display_source_name = artist 
                clean_a = clean_text_for_search(artist)
                clean_t = clean_text_for_search(song)
                unique_key = f"{clean_a}_{clean_t}"
                
                await safe_edit(status_msg, f"🔎 <b>Search:</b>\n🎶 {artist} - {song}", chat_id)
                temp_opts = {
                    'proxy': PROXY_URL, 
                    'quiet': True, 
                    'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
                }
                best = await loop.run_in_executor(None, smart_find_best_match, song, artist, temp_opts)
                download_target = best if best else f"ytsearch1:{artist} - {song} Audio"
            else: 
                raise Exception("Invalid Spotify Link")

        if unique_key and CACHE_CHANNEL_ID:
            cached_data = get_from_cache(unique_key)
            if cached_data:
                cache_audio_id = cached_data.get('audio')
                cache_photo_id = cached_data.get('photo')

        if cache_photo_id:
            try:
                final_photo_msg = await context.bot.copy_message(chat_id, CACHE_CHANNEL_ID, cache_photo_id)
            except:
                final_photo_msg = None

        if not final_photo_msg:
            await safe_edit(status_msg, "🖼 <b>Fetching Cover...</b>", chat_id)
            
            for attempt in range(1, 4):
                try:
                    ydl_opts_photo = {
                        'format': 'bestaudio/best', 
                        'proxy': PROXY_URL, 
                        'noplaylist': True, 
                        'writethumbnail': True, 
                        'skip_download': True,
                        'nocheckcertificate': True, 
                        'outtmpl': {'default': '%(title)s.%(ext)s'},
                        'source_address': '0.0.0.0', 
                        'cachedir': False,
                        'extractor_args': {'youtube': {'player_client': ['android']}},
                        'http_headers': {'User-Agent': 'Mozilla/5.0'}
                    }
                    
                    if not unique_key:
                        info_temp = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts_photo).extract_info(download_target, download=False))
                        if 'entries' in info_temp: info_temp = info_temp['entries'][0]
                        
                        raw_a = clean_text_for_search(info_temp.get('uploader', ''))
                        raw_t = clean_text_for_search(info_temp.get('title', ''))
                        if " - " in info_temp.get('title', ''):
                            parts = info_temp['title'].split(" - ", 1)
                            raw_a = clean_text_for_search(parts[0])
                            raw_t = clean_text_for_search(parts[1])
                        
                        unique_key = f"{raw_a}_{raw_t}"

                        if CACHE_CHANNEL_ID:
                            c_new = get_from_cache(unique_key)
                            if c_new:
                                cache_audio_id = c_new.get('audio')
                                if c_new.get('photo') and not final_photo_msg:
                                    try:
                                        final_photo_msg = await context.bot.copy_message(chat_id, CACHE_CHANNEL_ID, c_new['photo'])
                                        cache_photo_id = c_new.get('photo')
                                        break
                                    except: pass

                    dl_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts_photo).extract_info(download_target, download=True))
                    if 'entries' in dl_info: dl_info = dl_info['entries'][0]
                    info_dict = dl_info
                    
                    full_filename = yt_dlp.YoutubeDL(ydl_opts_photo).prepare_filename(dl_info)
                    filename_stem = os.path.splitext(full_filename)[0]
                    
                    for ext in ['.webp', '.jpg', '.png']:
                        if os.path.exists(filename_stem + ext): 
                            thumbnail_path = filename_stem + ext
                            break
                    
                    freshly_downloaded_photo = True
                    break
                except Exception as e:
                    await asyncio.sleep(1)

            if not final_photo_msg and thumbnail_path and os.path.exists(thumbnail_path):
                t_title = info_dict.get('title', 'Music') if info_dict else "Music"
                with open(thumbnail_path, 'rb') as f:
                    final_photo_msg = await context.bot.send_photo(chat_id, f, caption=f"🖼 <b>{html.escape(t_title)}</b>", parse_mode=ParseMode.HTML)

        if cache_audio_id and not final_audio_msg:
            try:
                final_audio_msg = await context.bot.copy_message(chat_id, CACHE_CHANNEL_ID, cache_audio_id)
            except:
                final_audio_msg = None

        if not final_audio_msg:
            for attempt in range(1, 4):
                try:
                    if not user_states.get(chat_id, {}).get('running'): raise Exception("Cancelled")
                    
                    await safe_edit(status_msg, "⬇️ <b>Downloading Audio...</b>", chat_id)
                    
                    ydl_opts_audio = {
                        'format': 'bestaudio/best', 'proxy': PROXY_URL, 'noplaylist': True, 
                        'writethumbnail': False,
                        'nocheckcertificate': True, 'outtmpl': {'default': '%(title)s.%(ext)s'},
                        'source_address': '0.0.0.0', 'cachedir': False,
                        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '320'}],
                        'http_headers': {'User-Agent': 'Mozilla/5.0'}
                    }

                    def hook(d):
                        if not user_states.get(chat_id, {}).get('running'): raise yt_dlp.utils.DownloadError("Cancelled")
                        now = time.time()
                        if chat_id in last_update_time:
                            if now - last_update_time[chat_id] < 3.0 and d['status'] == 'downloading': return
                        last_update_time[chat_id] = now
                        asyncio.run_coroutine_threadsafe(update_status_message(d, status_msg, chat_id), loop)

                    dl_info = await loop.run_in_executor(None, blocking_download, download_target, ydl_opts_audio, hook)
                    if 'entries' in dl_info: dl_info = dl_info['entries'][0]
                    info_dict = dl_info
                    
                    full_filename = yt_dlp.YoutubeDL(ydl_opts_audio).prepare_filename(dl_info)
                    filename_stem = os.path.splitext(full_filename)[0]
                    file_name_mp3 = filename_stem + '.mp3'
                    
                    if dl_info.get('duration', 0) > MAX_DURATION_SECONDS:
                        await safe_edit(status_msg, f"❌ Too long.", chat_id, remove_keyboard=True)
                        cleanup_files(file_name_mp3, thumbnail_path, filename_stem)
                        return

                    freshly_downloaded_audio = True
                    break
                except Exception as e:
                    if "Cancelled" in str(e): 
                        cleanup_files(file_name_mp3, thumbnail_path, filename_stem)
                        return
                    if attempt == 3: 
                        await safe_edit(status_msg, f"❌ Error: {e}", chat_id, remove_keyboard=True)
                        cleanup_files(file_name_mp3, thumbnail_path, filename_stem)
                        return
                    await loop.run_in_executor(None, rotate_warp_ip)

            if not final_audio_msg and file_name_mp3 and os.path.exists(file_name_mp3):
                final_title = info_dict.get('title', 'Unknown Track')
                final_artist = display_source_name
                if platform != "Spotify":
                    raw_ch = info_dict.get('uploader', '') or info_dict.get('channel', 'Unknown')
                    final_artist = raw_ch.replace(" - Topic", "").replace("VEVO", "").replace("Official", "").strip()
                    if " - " in final_title:
                        parts = final_title.split(" - ", 1)
                        if len(parts[0]) < 50: 
                            final_artist = parts[0].strip()
                            final_title = parts[1].strip()

                safe_title = html.escape(final_title)
                safe_artist = html.escape(final_artist)
                caption = (f"🎵 Name: <b>{safe_title}</b>\n👤 Artist/Source: <b>{safe_artist}</b>\n"
                           f"📱 Platform: <b>{platform}</b>\n⚡️ Quality: 320kbps\n\n"
                           f"✨ Downloaded by <b>@{context.bot.username}</b>\n🎈 By: <b>@sorblack</b>")

                await safe_edit(status_msg, "📤 <b>Uploading...</b>", chat_id)
                
                if thumbnail_path: 
                    await loop.run_in_executor(None, embed_cover, file_name_mp3, thumbnail_path, info_dict, final_artist)
                
                with open(file_name_mp3, 'rb') as f:
                    th = open(thumbnail_path, 'rb') if thumbnail_path else None
                    final_audio_msg = await context.bot.send_audio(
                        chat_id, f, thumbnail=th, 
                        title=final_title, performer=final_artist, caption=caption, parse_mode=ParseMode.HTML
                    )
                    if th: th.close()

        if CACHE_CHANNEL_ID and unique_key:

            needs_repair = freshly_downloaded_photo or freshly_downloaded_audio
            
            if needs_repair:

                if cache_audio_id: 
                    try: await context.bot.delete_message(CACHE_CHANNEL_ID, cache_audio_id)
                    except: pass
                if cache_photo_id: 
                    try: await context.bot.delete_message(CACHE_CHANNEL_ID, cache_photo_id)
                    except: pass
                
                new_db_p = None
                new_db_a = None
                
                if final_photo_msg:
                    try:
                        bk_p = await context.bot.copy_message(CACHE_CHANNEL_ID, chat_id, final_photo_msg.message_id)
                        new_db_p = bk_p.message_id
                    except: pass
                
                if final_audio_msg:
                    try:
                        bk_a = await context.bot.copy_message(CACHE_CHANNEL_ID, chat_id, final_audio_msg.message_id)
                        new_db_a = bk_a.message_id
                    except: pass
                
                if new_db_a:
                    save_to_global_cache(unique_key, new_db_a, new_db_p)

        try: await status_msg.delete()
        except: pass
        
        kb_buttons = []
        if origin_msg.chat.type == ChatType.PRIVATE:
             ch = get_user_channel(origin_msg.from_user.id)
             if ch:
                 if final_audio_msg:
                     pid = final_photo_msg.message_id if final_photo_msg else 0
                     aid = final_audio_msg.message_id
                     kb_buttons.append([InlineKeyboardButton("✅ Send to Channel", callback_data=f'send_to_ch_{aid}_{pid}')])
             else:
                 kb_buttons.append([InlineKeyboardButton("Set Channel", callback_data='settings_home')])

        if final_audio_msg:
            kb_buttons.append([
                InlineKeyboardButton("📝 Get Lyrics", callback_data=f'get_lyrics_{final_audio_msg.message_id}'),
                InlineKeyboardButton("❌ Close", callback_data='cancel_send')
            ])

            await context.bot.send_message(
                chat_id, 
                f"File Ready! 👇", 
                reply_markup=InlineKeyboardMarkup(kb_buttons), 
                parse_mode=ParseMode.HTML, 
                reply_to_message_id=final_audio_msg.message_id
            )

        else:
            await safe_edit(status_msg, "❌ <b>Download Failed.</b>", chat_id, remove_keyboard=True)

    except Exception as e:
        if "Cancelled" in str(e):
            await safe_edit(status_msg, "⛔️ <b>Cancelled.</b>", chat_id, remove_keyboard=True)
        else:
            await safe_edit(status_msg, f"❌ Error: {e}", chat_id, remove_keyboard=True)
            logger.error(e)
            
    finally:
        cleanup_files(file_name_mp3, thumbnail_path, filename_stem)
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

def get_history_file(user_id):
    return os.path.join(get_user_folder(user_id), "history.json")

def load_history(user_id):
    try:
        with open(get_history_file(user_id), 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def save_to_history(user_id, unique_key, message_id):
    """Saves song signature and channel message ID"""
    hist = load_history(user_id)
    hist[unique_key] = message_id
    with open(get_history_file(user_id), 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False)

def get_message_link(chat_id, message_id, username=None):
    """Generates a direct link to a message in a channel"""
    if username:
        return f"https://t.me/{username}/{message_id}"
    else:
        clean_id = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{clean_id}/{message_id}"

def get_lyrics_smart(artist, title):
    """
    V6 Engine: With STRICT Verification to avoid garbage results.
    """
    clean_artist = clean_text_for_search(artist)
    clean_title = clean_text_for_search(title)
    
    if " - " in title:
        parts = title.split(" - ", 1)
        potential_artist = clean_text_for_search(parts[0])
        potential_title = clean_text_for_search(parts[1])
        
        if re.search(r'[a-zA-Z]', potential_artist):
             clean_artist = potential_artist
        clean_title = potential_title

    clean_title_en = re.sub(r'[^\x00-\x7F]+', '', clean_title).strip()
    clean_artist_en = re.sub(r'[^\x00-\x7F]+', '', clean_artist).strip()
    
    queries = []
    if clean_artist_en and clean_title_en:
        queries.append(f"{clean_artist_en} {clean_title_en}")
    
    if clean_title_en:
        queries.append(clean_title_en)

    logger.info(f"Searching: {queries}")

    for query in queries:
        if len(query) < 2: continue

        try:
            url = "https://lrclib.net/api/search"
            params = {'q': query}
            resp = requests.get(url, params=params, timeout=4)
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    for track in results[:3]:
                        if track.get('instrumental'): continue
                        
                        res_artist = track.get('artistName', '')
                        res_track = track.get('trackName', '')
                        
                        if clean_artist_en and len(clean_artist_en) > 2:
                            if not check_similarity(clean_artist_en, res_artist):
                                continue
                        
                        if not check_similarity(clean_title_en, res_track):
                            continue

                        if track.get('syncedLyrics'): return track['syncedLyrics'], "LrcLib (Synced)"
                        if track.get('plainLyrics'): return track['plainLyrics'], "LrcLib (Plain)"
        except: pass

        if clean_artist_en in query and len(query) > 5: 
            lyrics, source = search_genius_direct(query)
            if lyrics: return lyrics, source

    return None, None

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
