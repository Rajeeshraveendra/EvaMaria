import io
import re
import asyncio
import logging
import json
import urllib.request
import urllib.parse
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS, LOG_CHANNEL

logger = logging.getLogger(__name__)

USER_GRP_MSGS = {}
OMDB_API_KEY = "97960898"

# ============================================================
# DUAL AUTO-SUGGESTION ENGINE (Google + OMDb)
# ============================================================
async def get_smart_suggestions(query):
    """Google & OMDb ഉപയോഗിച്ച് ഇംഗ്ലീഷിലും മലയാളത്തിലുമുള്ള കൃത്യമായ പേരുകൾ കണ്ടെത്തുന്നു"""
    loop = asyncio.get_event_loop()
    def fetch():
        suggestions = []
        cleaned_query = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
        if not cleaned_query:
            return []

        # 1. Google Autocomplete API
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urllib.parse.quote(cleaned_query + ' movie')}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode('utf-8'))
                if len(data) > 1:
                    for item in data[1]:
                        item_clean = re.sub(r'(?i)\b(movie|film|full movie|download|malayalam|tamil|watch online)\b', '', item).strip()
                        if item_clean and item_clean.lower() not in [s.lower() for s in suggestions]:
                            suggestions.append(item_clean.title())
        except Exception:
            pass

        # 2. OMDb API ബാക്കപ്പ്
        if len(suggestions) < 4:
            try:
                omdb_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={urllib.parse.quote(cleaned_query)}&type=movie"
                req2 = urllib.request.Request(omdb_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=4) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    for m in res.get("Search", []):
                        title = m.get("Title")
                        if title and title.lower() not in [s.lower() for s in suggestions]:
                            suggestions.append(title)
            except Exception:
                pass

        return suggestions[:6]

    return await loop.run_in_executor(None, fetch)


# ============================================================
# HELPER TAG FUNCTIONS
# ============================================================
def get_audio_tag(name):
    n = name.lower()
    audios = []
    if any(x in n for x in ['malayalam', 'mal']):
        audios.append('Mal')
    if any(x in n for x in ['tamil', 'tam']):
        audios.append('Tam')
    if any(x in n for x in ['hindi', 'hin']):
        audios.append('Hin')
    if any(x in n for x in ['telugu', 'tel']):
        audios.append('Tel')
    if any(x in n for x in ['kannada', 'kan']):
        audios.append('Kan')
    if any(x in n for x in ['english', 'eng']):
        audios.append('Eng')
    if 'multi' in n:
        return 'Multi'
    if 'dual' in n:
        return 'Dual'
    return "/".join(audios) if audios else ""

def get_quality_tag(name):
    n = name.lower()
    if '2160p' in n or '4k' in n:
        return '4K'
    if '1080p' in n:
        return '1080p'
    if '720p' in n:
        return '720p'
    if '480p' in n:
        return '480p'
    if 'hdrip' in n:
        return 'HDRip'
    return ""

async def send_log_safe(client, log_txt):
    if not LOG_CHANNEL:
        return
    try:
        chat_target = int(LOG_CHANNEL) if str(LOG_CHANNEL).startswith("-100") or str(LOG_CHANNEL).isdigit() else str(LOG_CHANNEL)
        await client.send_message(chat_id=chat_target, text=log_txt)
    except Exception as e:
        logger.error(f"Log Channel Error: {e}")

async def safe_delete_messages(client, chat_id, message_ids, delay=10):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except Exception as e:
        logger.error(f"Error in safe_delete_messages: {e}")


# ============================================================
# MAIN SEARCH FILTER HANDLER
# ============================================================
@Client.on_message((filters.group | filters.private) & filters.text & filters.incoming, group=1)
async def give_filter(client, message):
    if not message.text or message.text.startswith(("/", "!", "#")) or len(message.text.strip()) < 2:
        return

    text = message.text.strip()
    user = message.from_user
    if not user:
        return

    userid = user.id
    user_mention = user.mention
    is_group = message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]
    chat_title = message.chat.title if is_group else "Bot PM / Personal"

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    # ഗ്രൂപ്പ് സ്പാം ഡിലീറ്റ്
    if is_group:
        spam_words = ["xxx", "18+", "playnow", "oiled", "massage", "moaning", "homemade", "sweet dreams", "audition"]
        if any(w in text.lower() for w in spam_words) or (message.forward_date and userid not in ADMINS):
            try:
                await message.delete()
                return
            except Exception:
                pass

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. ഫയലുകൾ കിട്ടിയില്ലെങ്കിൽ (Dual Language Suggestions)
    if not files:
        suggestions = await get_smart_suggestions(text)

        # സജഷനുകൾ കണ്ടെത്തിയാൽ
        if suggestions:
            btn = []
            for mov in suggestions:
                btn.append([InlineKeyboardButton(f"🎬 {mov}", callback_data=f"spolling#{mov}")])

            suggest_text = (
                f"👋 <b>ഹലോ / Hello {user_mention},</b>\n\n"
                f"❓ <b>നിങ്ങൾ ഉദ്ദേശിച്ചത് താഴെ പറയുന്നവയിൽ ഏതെങ്കിലും ആണോ?</b>\n"
                f"<i>Did you mean one of the movies listed below?</i>\n\n"
                f"👇 <i>ശരിയായ സിനിമയിൽ ടാപ്പ് ചെയ്യുക / Tap on the correct movie:</i>"
            )
            suggest_msg = await message.reply_text(
                suggest_text,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            if is_group:
                asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, suggest_msg.id], delay=60))
            message.stop_propagation()
            return

        # സജഷനുകൾ ഒന്നും കണ്ടെത്താൻ സാധിച്ചില്ലെങ്കിൽ (Dual Language Error)
        log_txt = (
            f"❌ <b>#MovieNotFound</b>\n\n"
            f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
            f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
            f"🔍 <b>Query:</b> <code>{text}</code>"
        )
        await send_log_safe(client, log_txt)

        btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={urllib.parse.quote(text)}+movie")]]
        err_text = (
            f"❌ <b>സിനിമ കണ്ടെത്താനായില്ല / Movie Not Found!</b>\n\n"
            f"👋 <b>ഹലോ / Hello {user_mention},</b>\n"
            f"📌 <b>നിങ്ങൾ തിരഞ്ഞത് / Your Query:</b> <code>{text}</code>\n\n"
            f"💡 <i>ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.</i>\n"
            f"<i>Please check your spelling and try again.</i>"
        )
        err_msg = await message.reply_text(
            err_text,
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        
        if is_group:
            asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, err_msg.id], delay=15))
        
        message.stop_propagation()
        return

    # 2. ഫയലുകൾ കണ്ടെത്തിയാൽ
    log_txt = (
        f"🎬 <b>#FileSentToPM</b>\n\n"
        f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
        f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
        f"🔍 <b>Query:</b> <code>{text}</code>\n"
        f"📦 <b>Files Found:</b> {total_results}"
    )
    await send_log_safe(client, log_txt)

    btn = []
    for file in files:
        raw_name = file.file_name
        size = get_size(file.file_size)
        audio = get_audio_tag(raw_name)
        quality = get_quality_tag(raw_name)

        cleaned_name = re.sub(r'\[.*?\]|\(.*?\)', '', raw_name)
        cleaned_name = re.sub(r'[_.-]', ' ', cleaned_name).strip()
        cleaned_name = re.sub(' +', ' ', cleaned_name)

        tag_parts = [size]
        if audio:
            tag_parts.append(audio)
        if quality:
            tag_parts.append(quality)
        tag_str = " | ".join(tag_parts)

        if len(cleaned_name) > 20:
            cleaned_name = cleaned_name[:18] + ".."

        btn_caption = f"🎬 [{tag_str}] {cleaned_name}"
        btn.append([InlineKeyboardButton(btn_caption, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    if offset != "":
        total_pages = (total_results + 9) // 10
        btn.append([
            InlineKeyboardButton(f"1/{total_pages} Pages", callback_data="pages_info"),
            InlineKeyboardButton("Next ⏩", callback_data=f"next_{text}_{offset}_1")
        ])

    result_msg = await message.reply_text(
        f"<b>Here is the result for:</b> <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )

    if is_group:
        USER_GRP_MSGS[userid] = {
            "chat_id": message.chat.id,
            "user_msg_id": message.id,
            "bot_msg_id": result_msg.id
        }
        asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, result_msg.id], delay=120))

    message.stop_propagation()


# ============================================================
# CALLBACK: SPELL CHECK CLICK HANDLER
# ============================================================
@Client.on_callback_query(filters.regex(r"^spolling#"))
async def spelling_click_handler(client, query: CallbackQuery):
    movie_name = query.data.split("#", 1)[1]
    files, offset, total_results = await get_search_results(movie_name, max_results=10)
    
    if not files:
        return await query.answer(f"'{movie_name}' ഫയലുകൾ ഡാറ്റാബേസിൽ ലഭ്യമല്ല!", show_alert=True)

    btn = []
    for file in files:
        raw_name = file.file_name
        size = get_size(file.file_size)
        audio = get_audio_tag(raw_name)
        quality = get_quality_tag(raw_name)

        cleaned_name = re.sub(r'\[.*?\]|\(.*?\)', '', raw_name)
        cleaned_name = re.sub(r'[_.-]', ' ', cleaned_name).strip()
        cleaned_name = re.sub(' +', ' ', cleaned_name)

        tag_parts = [size]
        if audio:
            tag_parts.append(audio)
        if quality:
            tag_parts.append(quality)
        tag_str = " | ".join(tag_parts)

        if len(cleaned_name) > 20:
            cleaned_name = cleaned_name[:18] + ".."

        btn_caption = f"🎬 [{tag_str}] {cleaned_name}"
        btn.append([InlineKeyboardButton(btn_caption, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    if offset != "":
        total_pages = (total_results + 9) // 10
        btn.append([
            InlineKeyboardButton(f"1/{total_pages} Pages", callback_data="pages_info"),
            InlineKeyboardButton("Next ⏩", callback_data=f"next_{movie_name}_{offset}_1")
        ])

    await query.message.edit_text(
        f"<b>Here is the result for:</b> <code>{movie_name}</code>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )
    await query.answer()


# ============================================================
# CALLBACK: PAGINATION (Next / Back)
# ============================================================
@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page_handler(client, query: CallbackQuery):
    try:
        _, text, offset, curr_page = query.data.split("_", 3)
        curr_page = int(curr_page)
    except Exception:
        return await query.answer("കൂടുതൽ ഫയലുകളില്ല / No more results!", show_alert=True)

    files, next_offset, total_results = await get_search_results(text, offset=int(offset), max_results=10)
    if not files:
        return await query.answer("അവസാനത്തെ പേജ് ആയി / Last page reached!", show_alert=True)

    total_pages = (total_results + 9) // 10
    new_page = curr_page + 1

    btn = []
    for file in files:
        raw_name = file.file_name
        size = get_size(file.file_size)
        audio = get_audio_tag(raw_name)
        quality = get_quality_tag(raw_name)

        cleaned_name = re.sub(r'\[.*?\]|\(.*?\)', '', raw_name)
        cleaned_name = re.sub(r'[_.-]', ' ', cleaned_name).strip()
        cleaned_name = re.sub(' +', ' ', cleaned_name)

        tag_parts = [size]
        if audio:
            tag_parts.append(audio)
        if quality:
            tag_parts.append(quality)
        tag_str = " | ".join(tag_parts)

        if len(cleaned_name) > 20:
            cleaned_name = cleaned_name[:18] + ".."

        btn_caption = f"🎬 [{tag_str}] {cleaned_name}"
        btn.append([InlineKeyboardButton(btn_caption, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    page_btns = []
    prev_offset = max(0, int(offset) - 10)
    page_btns.append(InlineKeyboardButton("⏪ Back", callback_data=f"next_{text}_{prev_offset}_{new_page - 2}"))
    page_btns.append(InlineKeyboardButton(f"{new_page}/{total_pages} Pages", callback_data="pages_info"))

    if next_offset != "":
        page_btns.append(InlineKeyboardButton("Next ⏩", callback_data=f"next_{text}_{next_offset}_{new_page}"))

    btn.append(page_btns)

    try:
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        await query.answer()
    except Exception as e:
        logger.error(f"Page edit error: {e}")
        await query.answer()

@Client.on_callback_query(filters.regex(r"^pages_info"))
async def pages_info_click(client, query: CallbackQuery):
    await query.answer("Current Page Number", show_alert=False)
