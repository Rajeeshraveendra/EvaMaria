import io
import logging
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS

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
    user_name = user.first_name

    grp_id = message.chat.id
    settings = await get_settings(grp_id)

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. സിനിമ കണ്ടെത്താനായില്ലെങ്കിൽ യൂസർ ഡീറ്റെയിൽസ് സഹിതം മെസ്സേജ്
    if not files:
        if settings.get("spell_check", True):
            btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={text}+movie")]]
            not_found_msg = (
                f"❌ <b>സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"👤 <b>അംഗം :</b> {user_mention} (<code>{userid}</code>)\n"
                f"📌 <b>തിരഞ്ഞ വാക്ക് :</b> <code>{text}</code>\n\n"
                f"💡 <i>ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.</i>"
            )
            await message.reply_text(
                not_found_msg,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        return

    # 2. ഫയലുകൾ കിട്ടുമ്പോൾ യൂസർ ഡീറ്റെയിൽസ് അടങ്ങിയ തലക്കെട്ട്
    btn = []
    for file in files:
        title = file.file_name
        size = get_size(file.file_size)
        f_caption = f"🎬 {title} [{size}]"
        btn.append([InlineKeyboardButton(f_caption, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    cap = (
        f"🎬 <b>Here is the result for:</b> <code>{text}</code>\n\n"
        f"👤 <b>Requested By :</b> {user_mention}\n"
        f"🆔 <b>User ID :</b> <code>{userid}</code>\n"
        f"📁 <b>Total Files Found :</b> <code>{total_results}</code>"
    )

    await message.reply_text(
        cap,
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )
