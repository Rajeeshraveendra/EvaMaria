import io
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    if message.text.startswith(("/", "!", "#")):
        return

    userid = message.from_user.id if message.from_user else None
    if not userid:
        return

    grp_id = message.chat.id
    settings = await get_settings(grp_id)

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    text = message.text.strip()
    files, offset, total_results = await get_search_results(text, max_results=10)

    if not files:
        if settings.get("spell_check", True):
            btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={text}+movie")]]
            await message.reply_text(
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Hey {message.from_user.mention},\n"
                f"📌 <b>You Searched :</b> <code>{text}</code>\n\n"
                f"💡 Please check the spelling and send again.",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        return

    btn = []
    # Bot PM settings അനുസരിച്ച് ബട്ടൺ നിർമ്മിക്കുന്നു
    if settings.get("botpm"):
        btn.append([InlineKeyboardButton("📥 View in PM / ഫയലുകൾ കാണാൻ ഇവിടെ ക്ലിക്ക് ചെയ്യുക", url=f"https://t.me/{temp.U_NAME}?start=search_{text}")])
    else:
        for file in files:
            title = file.file_name
            size = get_size(file.file_size)
            btn.append([InlineKeyboardButton(f"🎬 {title} [{size}]", url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])

    await message.reply_text(
        f"<b>Here is the result for:</b> <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )
