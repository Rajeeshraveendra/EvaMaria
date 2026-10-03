import re
import urllib.parse
import asyncio
import os
from pyrogram import Client, filters, enums
from info import CHANNELS, PICS
from utils import temp

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def clean_movie_title(filename):
    """സിനിമയുടെ പ്രധാന പേര് മാത്രം കണ്ടെത്തുന്നു"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    words = name.split()
    return " ".join(words[:4]).strip().title() if words else filename

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
        return

    file_name = media.file_name or "New Movie"
    base_title = clean_movie_title(file_name)
    
    # സിനിമയുടെ ഡീപ് ലിങ്ക്
    search_query = urllib.parse.quote(base_title)
    bot_username = temp.U_NAME
    movie_link = f"https://t.me/{bot_username}?start={search_query}"
    
    line_entry = f"🎬 <a href=\"{movie_link}\">{file_name}</a>"

    async with LOCK:
        # നിലവിൽ ഈ സിനിമയ്ക്കായി പോസ്റ്റ് ഉണ്ടെങ്കിൽ കാപ്ഷൻ എഡിറ്റ് ചെയ്യുന്നു
        if base_title in POST_CACHE:
            data = POST_CACHE[base_title]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                
                movies_list_text = "\n".join(data["entries"])
                updated_caption = (
                    f"<b>Today's Movies :</b>\n"
                    f"{movies_list_text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"          <b>Released ✅</b>\n"
                    f"📌 <b>Pin For Instant Updates</b>\n"
                    f"       😎 <b>Check it Out</b> 😎\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                try:
                    await client.edit_message_caption(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        caption=updated_caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Edit Caption Error: {e}")
            return

        # പുതിയ പോസ്റ്റിനായുള്ള കാപ്ഷൻ
        initial_caption = (
            f"<b>Today's Movies :</b>\n"
            f"{line_entry}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"          <b>Released ✅</b>\n"
            f"📌 <b>Pin For Instant Updates</b>\n"
            f"       😎 <b>Check it Out</b> 😎\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        sent_msg = None
        thumb_path = None

        # 1. ഫയലിൽ തമ്പ്‌നെയിൽ ഉണ്ടെങ്കിൽ അത് ലോക്കലായി ഡൗൺലോഡ് ചെയ്ത് ഫോട്ടോയായി അയക്കുന്നു
        if media.thumbs and len(media.thumbs) > 0:
            try:
                thumb_path = await client.download_media(media.thumbs[0].file_id)
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=thumb_path,
                    caption=initial_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Thumb upload error: {err}")
            finally:
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)

        # 2. തമ്പ്‌നെയിൽ ഇല്ലെങ്കിലോ പരാജയപ്പെട്ടാലോ PICS ലിങ്ക് ഉപയോഗിക്കുന്നു
        if not sent_msg and PICS:
            try:
                import random
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=random.choice(PICS),
                    caption=initial_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"PICS upload error: {err}")

        # 3. മുകളിൽ രണ്ടും നടന്നില്ലെങ്കിൽ മാത്രം ടെക്സ്റ്റ് അയക്കുന്നു
        if not sent_msg:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=initial_caption,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        POST_CACHE[base_title] = {
            "msg_id": sent_msg.id,
            "entries": [line_entry]
        }
