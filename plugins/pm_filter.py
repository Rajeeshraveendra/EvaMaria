import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, AUTH_USERS, CUSTOM_FILE_CAPTION, LOG_CHANNEL
from database.ia_filterdb import get_search_results

@Client.on_message(filters.text & filters.private & filters.incoming)
async def auto_pm_search(client, message):
    text = (message.text or "").strip()

    # കമാൻഡുകൾ ഒഴിവാക്കുന്നു
    if text.startswith(("/", "!", "#")):
        message.continue_propagation()
        return

    # ഗ്രൂപ്പിലെ വിവരങ്ങൾ ഒഴിവാക്കുന്നു
    if len(text) < 2:
        return

    query = re.sub(r"[:_#\.\-]", " ", text).strip()
    
    # ഡാറ്റാബേസിൽ നിന്ന് ഫയലുകൾ തിരയുന്നു
    files, _, _ = await get_search_results(query, max_results=10)

    if not files:
        await message.reply_text("❌ സിനിമ അല്ലെങ്കിൽ ഫയൽ ലഭ്യമല്ല! ദയവായി സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.")
        return

    # യൂസർക്ക് നേരിട്ട് ഓരോ ഫയലുകളും സെൻഡ് ചെയ്യുന്നു
    for file in files:
        file_id = file.file_id
        file_name = getattr(file, "file_name", "Movie File")
        caption = CUSTOM_FILE_CAPTION.format(file_name=file_name) if CUSTOM_FILE_CAPTION else f"📁 **{file_name}**"

        try:
            # ഫയൽ പ്രൈവറ്റ് ചാറ്റിലേക്ക് അയക്കുന്നു
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id,
                caption=caption
            )

            # ലോഗ് ചാനലിലേക്ക് ഫയൽ സെൻഡ് ലോഗ് നൽകുന്നു
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

            await asyncio.sleep(1) # ഫ്ലഡ് വരാതിരിക്കാൻ ചെറിയ ഗ്യാപ്പ്
        except Exception as e:
            print(f"Error sending file: {e}")
