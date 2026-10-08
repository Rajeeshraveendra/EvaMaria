import io
import re
import asyncio
import logging
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS, LOG_CHANNEL

logger = logging.getLogger(__name__)

USER_GRP_MSGS = {}

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

    if is_group:
        spam_words = ["xxx", "18+", "playnow", "oiled", "massage", "moaning", "homemade", "sweet dreams", "audition"]
        if any(w in text.lower() for w in spam_words) or (message.forward_date and userid not in ADMINS):
            try:
                await message.delete()
                return
            except Exception:
                pass

    files, offset, total_results = await get_search_results(text, max_results=10)

    if not files:
        log_txt = (
            f"❌ <b>#MovieNotFound</b>\n\n"
            f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
            f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
            f"🔍 <b>Query:</b> <code>{text}</code>"
        )
        await send_log_safe(client, log_txt)

        btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={text}+movie")]]
        err_msg = await message.reply_text(
            f"❌ <b>Cinema kandethaan kazhinjilla!</b>\n\n"
            f"Hello {user_mention},\n"
            f"📌 <b>Ningal thiranjathu :</b> <code>{text}</code>\n\n"
            f"💡 Dhayavayi shariyaya spelling parishodhikuka.",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        
        if is_group:
            asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, err_msg.id], delay=10))
        
        message.stop_propagation()
        return

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
# PAGINATION CALLBACK HANDLER (Next / Back Work Aavaan)
# ============================================================
@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page_handler(client, query: CallbackQuery):
    try:
        _, text, offset, curr_page = query.data.split("_", 3)
        curr_page = int(curr_page)
    except Exception:
        return await query.answer("Kooduthal results illa!", show_alert=True)

    files, next_offset, total_results = await get_search_results(text, offset=int(offset), max_results=10)
    if not files:
        return await query.answer("Avasanathe page aayi!", show_alert=True)

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
    # Back button
    prev_offset = max(0, int(offset) - 10)
    page_btns.append(InlineKeyboardButton("⏪ Back", callback_data=f"next_{text}_{prev_offset}_{new_page - 2}"))
    page_btns.append(InlineKeyboardButton(f"{new_page}/{total_pages} Pages", callback_data="pages_info"))

    # Next button (kooduthal undengil maathram)
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
