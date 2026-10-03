import re
import urllib.parse
import asyncio
from pyrogram import Client, filters, enums
from info import CHANNELS
from utils import temp
import os

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

# സിനിമയുടെ മെസ്സേജ് ഐഡികളും ലിസ്റ്റുകളും താൽക്കാലികമായി സൂക്ഷിക്കാൻ
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
        # നിലവിൽ ഈ സിനിമയ്ക്കായി പോസ്റ്റ് ഗ്രൂപ്പിൽ അയച്ചിട്ടുണ്ടെങ്കിൽ അത് എഡിറ്റ് ചെയ്യുന്നു
        if base_title in POST_CACHE:
            data = POST_CACHE[base_title]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                
                movies_list_text = "\n".join(data["entries"])
                updated_text = (
                    f"<b>Today's Movies :</b>\n"
                    f"{movies_list_text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"          <b>Released ✅</b>\n"
                    f"📌 <b>Pin For Instant Updates</b>\n"
                    f"       😎 <b>Check it Out</b> 😎\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                try:
                    await client.edit_message_text(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        text=updated_text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"Edit Post Error: {e}")
            return

        # പുതിയൊരു സിനിമയാണെങ്കിൽ പുതിയ മെസ്സേജ് അയക്കുന്നു
        initial_text = (
            f"<b>Today's Movies :</b>\n"
            f"{line_entry}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"          <b>Released ✅</b>\n"
            f"📌 <b>Pin For Instant Updates</b>\n"
            f"       😎 <b>Check it Out</b> 😎\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        try:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=initial_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            # ഭാവിയിലെ എഡിറ്റുകൾക്കായി മെസ്സേജ് ഐഡി സേവ് ചെയ്യുന്നു
            POST_CACHE[base_title] = {
                "msg_id": sent_msg.id,
                "entries": [line_entry]
            }
        except Exception as e:
            print(f"Send New Post Error: {e}")
