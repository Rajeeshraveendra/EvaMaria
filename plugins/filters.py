import io
import logging
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS

logger = logging.getLogger(__name__)

# group=-1 നൽകുന്നതിലൂടെ ഈ ഫയൽ ആദ്യം പ്രവർത്തിക്കും
@Client.on_message(filters.group & filters.text & filters.incoming, group=-1)
async def give_filter(client, message):
    if not message.text:
        return

    text = message.text.strip()
    if text.startswith(("/", "!", "#")):
        return

    if len(text) < 2:
        return

    userid = message.from_user.id if message.from_user else None
    if not userid:
        return

    grp_id = message.chat.id
    settings = await get_settings(grp_id)

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. ഫയലുകൾ കിട്ടിയാൽ:
    if files:
        # ബാക്കി എല്ലാ ഫയലുകളിലേക്കും ഈ മെസ്സേജ് പോകുന്നത് ഇവിടെവച്ച് തടയുന്നു!
        message.stop_propagation()
        
        btn = []
        if settings.get("botpm"):
            btn.append([InlineKeyboardButton("📥 View in PM / ഫയലുകൾ ഇൻബോക്സിൽ കാണുക", url=f"https://t.me/{temp.U_NAME}?start=search_{text}")])
        else:
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
        return

    # 2. ഫയലുകൾ ഇല്ലാത്തപ്പോൾ മാത്രം:
    if not files:
        # സിനിമ ഇല്ലാത്തപ്പോഴും ആ പഴയ തെറ്റായ മെസ്സേജ് വരാതിരിക്കാൻ സ്റ്റോപ്പ് ചെയ്യുന്നു
        message.stop_propagation()
        
        btn = [[InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={text}+movie")]]
        await message.reply_text(
            f"❌ <b>സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
            f"ഹലോ {message.from_user.mention},\n"
            f"📌 <b>നിങ്ങൾ തിരഞ്ഞത് :</b> <code>{text}</code>\n\n"
            f"💡 ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return
