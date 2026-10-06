import io
import re
import asyncio
import logging
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS, LOG_CHANNEL

logger = logging.getLogger(__name__)

# User file edukkumbol grp message delete cheyyan ulla global store
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

@Client.on_message((filters.group | filters.private) & filters.text & filters.incoming)
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

    grp_id = message.chat.id
    settings = await get_settings(grp_id)

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. Cinema kittiyillengil
    if not files:
        log_txt = (
            f"❌ <b>#MovieNotFound</b>\n\n"
            f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
            f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
            f"🔍 <b>Query:</b> <code>{text}</code>"
        )
        await send_log_safe(client, log_txt)

        if settings.get("spell_check", True):
            btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={text}+movie")]]
            await message.reply_text(
                f"❌ <b>സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"ഹലോ {user_mention},\n"
                f"📌 <b>നിങ്ങൾ തിരഞ്ഞത് :</b> <code>{text}</code>\n\n"
                f"💡 ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        return

    # 2. Cinema kittiyaal log channel-ilekku ayakkunnu
    log_txt = (
        f"🎬 <b>#FileSentToPM</b>\n\n"
        f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
        f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
        f"🔍 <b>Query:</b> <code>{text}</code>\n"
        f"📦 <b>Files Found:</b> {total_results}"
    )
    await send_log_safe(client, log_txt)

    # Buttons format cheyyunnu
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

    result_msg = await message.reply_text(
        f"<b>Here is the result for:</b> <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )

    # User-nte search details store cheyyunnu (PM-il file kitti kazhinju delete aavan)
    if is_group:
        USER_GRP_MSGS[userid] = {
            "chat_id": message.chat.id,
            "user_msg_id": message.id,
            "bot_msg_id": result_msg.id
        }
