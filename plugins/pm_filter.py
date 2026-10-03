import asyncio
import re
from pyrogram import Client, filters, enums
from info import ADMINS, AUTH_USERS, CUSTOM_FILE_CAPTION, LOG_CHANNEL
from database.ia_filterdb import get_search_results

@Client.on_message(filters.text & filters.private & filters.incoming, group=-1)
async def auto_pm_search(client, message):
    text = (message.text or "").strip()

    if text.startswith(("/", "!", "#")):
        message.continue_propagation()
        return

    if len(text) < 2:
        return

    query = re.sub(r"[:_#\.\-]", " ", text).strip()
    
    try:
        files, _, _ = await get_search_results(message.chat.id, query, max_results=10)
    except TypeError:
        files, _, _ = await get_search_results(query, max_results=10)
    except Exception as e:
        print(f"Search Error: {e}")
        return

    if not files:
        await message.reply_text("❌ സിനിമ അല്ലെങ്കിൽ ഫയൽ ലഭ്യമല്ല! ദയവായി സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.")
        return

    for file in files:
        file_id = getattr(file, "file_id", None) or (file.get("file_id") if isinstance(file, dict) else None)
        file_name = getattr(file, "file_name", None) or (file.get("file_name") if isinstance(file, dict) else "Movie File")

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

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"Error sending file: {e}")
