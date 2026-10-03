import re
import asyncio
import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from info import CUSTOM_FILE_CAPTION, LOG_CHANNEL

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template"]))
async def pm_movie_sender(client, message):
    text = (message.text or "").strip()
    
    if text.startswith(("/", "!", "#")):
        return

    if len(text) < 2:
        return

    # User Query Regex Search
    raw_pattern = ".*".join([re.escape(w) for w in text.split()])
    find_query = {"file_name": {"$regex": raw_pattern, "$options": "i"}}

    try:
        cursor = Media.collection.find(find_query).limit(10)
        files = await cursor.to_list(length=10)
    except Exception as e:
        logger.error(f"Search DB Query Error: {e}")
        return

    if not files:
        await message.reply_text("❌ സിനിമ ലഭ്യമല്ല! ദയവായി പേര് പരിശോധിച്ച് വീണ്ടും അയക്കുക.")
        return

    for doc in files:
        file_id = doc.get("file_id")
        file_name = doc.get("file_name", "Movie File")

        if not file_id:
            continue

        caption = CUSTOM_FILE_CAPTION.format(file_name=file_name) if CUSTOM_FILE_CAPTION else f"📁 **{file_name}**"

        try:
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id,
                caption=caption
            )

            if LOG_CHANNEL:
                try:
                    user_info = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
                    log_text = (
                        f"📁 **#FileSent**\n\n"
                        f"👤 **User:** {user_info} (`{message.from_user.id}`)\n"
                        f"🎬 **Film/File:** `{file_name}`"
                    )
                    await client.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_text,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.2)
        except Exception as e:
            logger.error(f"File send error: {e}")
