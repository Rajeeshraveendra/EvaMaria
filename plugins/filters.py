import io
import logging
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS, LOG_CHANNEL

logger = logging.getLogger(__name__)

@Client.on_message((filters.group | filters.private) & filters.text & filters.incoming)
async def give_filter(client, message):
    if not message.text:
        return

    text = message.text.strip()
    if text.startswith(("/", "!", "#")):
        return

    if len(text) < 2:
        return

    user = message.from_user
    userid = user.id if user else None
    if not userid:
        return

    user_mention = user.mention
    chat_title = message.chat.title if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else "Bot PM / Personal"

    grp_id = message.chat.id
    settings = await get_settings(grp_id)

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. സിനിമ കിട്ടിയില്ലെങ്കിൽ:
    if not files:
        # ലോഗ് ചാനലിലേക്ക് നോട്ടിഫിക്കേഷൻ അയക്കുന്നു
        if LOG_CHANNEL:
            try:
                log_txt = (
                    f"❌ <b>#MovieNotFound</b>\n\n"
                    f"👥 <b>Requested In:</b> {chat_title}\n"
                    f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
                    f"🔍 <b>Query:</b> <code>{text}</code>"
                )
                await client.send_message(LOG_CHANNEL, log_txt)
            except Exception as e:
                logger.error(f"Log Error: {e}")

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

    # 2. ഫയലുകൾ ലഭ്യമാണെങ്കിൽ:
    # ലോഗ് ചാനലിലേക്ക് കൃത്യമായ സെർച്ച് ഡീറ്റെയിൽസ് അയക്കുന്നു
    if LOG_CHANNEL:
        try:
            log_txt = (
                f"🎬 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
                f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
                f"🔍 <b>Query:</b> <code>{text}</code>\n"
                f"📦 <b>Files Found:</b> {total_results}"
            )
            await client.send_message(LOG_CHANNEL, log_txt)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    # ഉപയോക്താവിന് റിസൾട്ട് ബട്ടണുകൾ നൽകുന്നു
    btn = []
    for file in files:
        title = file.file_name
        size = get_size(file.file_size)
        f_caption = f"🎬 {title} [{size}]"
        btn.append([InlineKeyboardButton(f_caption, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    await message.reply_text(
        f"<b>Here is the result for:</b> <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )
