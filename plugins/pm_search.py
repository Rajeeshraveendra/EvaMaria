import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
from database.ia_filterdb import get_search_results
from info import LOG_CHANNEL
from utils import temp

logger = logging.getLogger(__name__)

@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template"]), group=1)
async def pm_movie_sender(client, message):
    query = (message.text or "").strip()

    if query.startswith(("/", "!", "#")):
        return

    if len(query) < 2:
        return

    # EvaMaria search query
    try:
        files, _, _ = await get_search_results(query, max_results=10)
    except Exception as e:
        logger.error(f"Search Query Error: {e}")
        return

    if not files:
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply_text("❌ സിനിമ ലഭ്യമല്ല! ദയവായി പേര് പരിശോധിച്ച് വീണ്ടും അയക്കുക.")
        return

    # ഫയലുകൾ എപ്പോഴും ഉപയോക്താവിന്റെ വ്യക്തിഗത ചാറ്റിലേക്ക് (DM) അയക്കുന്നു
    target_user_id = message.from_user.id if message.from_user else None
    if not target_user_id:
        return

    sent_count = 0
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
                chat_id=target_user_id,
                file_id=file_id,
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
            sent_count += 1
            await asyncio.sleep(1.2)
        except (UserIsBlocked, PeerIdInvalid):
            # ബോട്ട് മുൻപ് സ്റ്റാർട്ട് ചെയ്യാത്ത ഉപയോക്താവ് ആണെങ്കിൽ ഗ്രൂപ്പിൽ ബട്ടൺ നൽകുന്നു
            if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                btn = [[InlineKeyboardButton("🍿 Start Bot in PM", url=f"https://t.me/{temp.U_NAME}?start=start")]]
                await message.reply_text(
                    f"ഹലോ {message.from_user.mention}, സിനിമ നിങ്ങളുടെ ഇൻബോക്സിലേക്ക് അയക്കാൻ താഴെ കാണുന്ന ബട്ടൺ ക്ലിക്ക് ചെയ്ത് ബോട്ട് <b>Start</b> ചെയ്യുക!",
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML
                )
            return
        except Exception as e:
            logger.error(f"File send error: {e}")

    # ഗ്രൂപ്പിൽ ചോദിച്ചതാണെങ്കിൽ, ഫയലുകൾ PM-ലേക്ക് അയച്ച വിവരം ഗ്രൂപ്പിൽ മറുപടിയായി നൽകുന്നു
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and sent_count > 0:
        btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
        await message.reply_text(
            f"✅ {message.from_user.mention}, താങ്കൾ ആവശ്യപ്പെട്ട സിനിമയുടെ ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയച്ചിട്ടുണ്ട്!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )

    # ലോഗ് ചാനലിലേക്ക് അപ്ഡേറ്റ് അയക്കുന്നു
    if LOG_CHANNEL and sent_count > 0:
        try:
            user_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            chat_title = message.chat.title if message.chat.title else "PM"
            log_text = (
                f"📁 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> {chat_title}\n"
                f"👤 <b>User:</b> {user_info} (<code>{message.from_user.id}</code>)\n"
                f"🔍 <b>Query:</b> <code>{query}</code>\n"
                f"📦 <b>Files Sent:</b> {sent_count}"
            )
            await client.send_message(
                chat_id=LOG_CHANNEL,
                text=log_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass
