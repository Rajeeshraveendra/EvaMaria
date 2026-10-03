import logging
import asyncio
from pyrogram import Client, filters, enums
from database.ia_filterdb import get_search_results
from info import LOG_CHANNEL

logger = logging.getLogger(__name__)

@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template"]), group=1)
async def pm_movie_sender(client, message):
    query = (message.text or "").strip()

    if query.startswith(("/", "!", "#")):
        return

    if len(query) < 2:
        return

    # EvaMaria search query without chat_id parameter
    try:
        files, _, _ = await get_search_results(query, max_results=10)
    except Exception as e:
        logger.error(f"Search Query Error: {e}")
        return

    if not files:
        # ഗ്രൂപ്പുകളിൽ വെറുതെ വരുന്ന ചാറ്റുകൾക്ക് ഇടയിൽ "സിനിമ ലഭ്യമല്ല" എന്ന് മെസ്സേജ് അയക്കാതിരിക്കാൻ:
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply_text("❌ സിനിമ ലഭ്യമല്ല! ദയവായി പേര് പരിശോധിച്ച് വീണ്ടും അയക്കുക.")
        return

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
                chat_id=message.chat.id,
                file_id=file_id,
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )

            if LOG_CHANNEL:
                try:
                    user_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>" if message.from_user else "Anonymous"
                    chat_title = message.chat.title if message.chat.title else "PM"
                    log_text = (
                        f"📁 <b>#FileSent</b>\n\n"
                        f"👥 <b>Chat:</b> {chat_title}\n"
                        f"👤 <b>User:</b> {user_info}\n"
                        f"🎬 <b>Film/File:</b> <code>{file_name}</code>"
                    )
                    await client.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.2)
        except Exception as e:
            logger.error(f"File send error: {e}")
