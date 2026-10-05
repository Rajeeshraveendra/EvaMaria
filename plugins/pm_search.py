import logging
import asyncio
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
from database.ia_filterdb import get_search_results
from utils import temp

logger = logging.getLogger(__name__)

# നിങ്ങളുടെ ലോഗ് ചാനൽ ID (RRK Movies Productions)
TARGET_LOG_CHANNEL = -1003799495012

@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template"]))
async def movie_search_and_sender(client, message):
    if not message.text or message.text.startswith(("/", "!", "#")):
        return
    if message.from_user and message.from_user.is_bot:
        return

    query = message.text.strip()
    if len(query) < 2:
        return

    user_id = message.from_user.id
    user_name = message.from_user.mention
    chat_type = message.chat.type

    # ഡാറ്റാബേസിൽ നിന്ന് ഫയലുകൾ തിരയുന്നു
    try:
        files, _, _ = await get_search_results(query, max_results=10)
    except Exception as e:
        logger.error(f"Search Query Error: {e}")
        return

    # ഫയലുകൾ ലഭ്യമല്ലെങ്കിൽ സ്പെല്ലിംഗ് ചെക്ക് നിർദ്ദേശം
    if not files:
        google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
        buttons = [
            [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_url)],
            [InlineKeyboardButton("🎬 Join Channel / Releases", url="https://t.me/+NoL3OkqPwBtiZjY0")]
        ]
        reply_text = (
            f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
            f"Hey {user_name},\n"
            f"📌 <b>You Searched :</b> <code>{query}</code>\n\n"
            f"💡 <b>Please check the spelling and send again.</b>\n"
            f"<i>(ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക)</i>\n\n"
            f"👉 <b>Example / ഉദാഹരണം :</b> <i>Drishyam, Manjummel Boys</i>"
        )
        try:
            await message.reply_text(
                text=reply_text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
        return

    # ഉപയോക്താവിന്റെ വ്യക്തിഗത ചാറ്റിലേക്ക് (PM) ഫയലുകൾ അയക്കുന്നു
    sent_count = 0
    blocked_or_not_started = False

    for doc in files:
        file_id = getattr(doc, "file_id", None) or (doc.get("file_id") if isinstance(doc, dict) else None)
        file_name = getattr(doc, "file_name", "Movie File") if hasattr(doc, "file_name") else (doc.get("file_name", "Movie File") if isinstance(doc, dict) else "Movie File")

        if not file_id:
            continue

        caption = (
            f"🎬 <b>File Name:</b> <code>{file_name}</code>\n\n"
            f"⚡ <b>Uploaded By:</b> @RRK_Movies\n\n"
            f"📥 <b>ഇപ്പോൾ തന്നെ ജോയിൻ ചെയ്യൂ:</b>\n"
            f"👉 https://t.me/+NoL3OkqPwBtiZjY0"
        )

        try:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file_id,
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
            sent_count += 1
            await asyncio.sleep(1.2)
        except (UserIsBlocked, PeerIdInvalid):
            blocked_or_not_started = True
            break
        except Exception as e:
            logger.error(f"Send File Error: {e}")

    # ഉപയോക്താവ് ബോട്ട് PM-ൽ Start ചെയ്തിട്ടില്ലെങ്കിൽ നിർദ്ദേശം നൽകുന്നു
    if blocked_or_not_started:
        btn = [[InlineKeyboardButton("🍿 Start Bot in PM", url=f"https://t.me/{temp.U_NAME}?start=start")]]
        await message.reply_text(
            f"ഹലോ {user_name}, സിനിമ നിങ്ങളുടെ ഇൻബോക്സിലേക്ക് (PM) അയക്കാൻ താഴെ കാണുന്ന ബട്ടൺ ക്ലിക്ക് ചെയ്ത് ബോട്ട് <b>Start</b> ചെയ്യുക!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # ഗ്രൂപ്പിലാണ് സെർച്ച് ചെയ്തതെങ്കിൽ വിവരം ഗ്രൂപ്പിൽ അറിയിക്കുന്നു
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and sent_count > 0:
        btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
        await message.reply_text(
            f"✅ {user_name}, താങ്കൾ ആവശ്യപ്പെട്ട സിനിമയുടെ {sent_count} ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയച്ചിട്ടുണ്ട്!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )

    # ലോഗ് ചാനലിലേക്ക് കൃത്യമായി #FileSentToPM അയക്കുന്നു
    if sent_count > 0:
        try:
            chat_title = message.chat.title if message.chat.title else "Bot PM"
            user_link = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
            log_text = (
                f"📁 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> {chat_title}\n"
                f"👤 <b>User:</b> {user_link} (<code>{user_id}</code>)\n"
                f"🔍 <b>Query:</b> <code>{query}</code>\n"
                f"📦 <b>Files Sent:</b> {sent_count}"
            )
            await client.send_message(
                chat_id=TARGET_LOG_CHANNEL,
                text=log_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as log_err:
            logger.error(f"Failed to send log to channel: {log_err}")
