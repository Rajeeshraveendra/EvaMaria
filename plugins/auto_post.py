import re
import urllib.parse
from pyrogram import Client, filters, enums
from info import CHANNELS
from utils import temp
import os

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

def clean_movie_name(filename):
    """ഫയൽ നെയിമിൽ നിന്നുള്ള അനാവശ്യ ടാഗുകൾ മാറ്റി പേര് ക്രമീകരിക്കുന്നു"""
    filename = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    filename = filename.replace(".", " ").replace("_", " ").strip()
    words = filename.split()
    return " ".join(words[:5]) if words else filename

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
        return

    file_name = media.file_name or "New Movie"
    display_title = clean_movie_name(file_name)
    
    # സിനിമയുടെ പേര് ബോട്ടിന്റെ ഡീപ്-ലിങ്കാക്കി മാറ്റുന്നു
    search_query = urllib.parse.quote(display_title)
    bot_username = temp.U_NAME
    movie_link = f"https://t.me/{bot_username}?start={search_query}"

    post_text = (
        f"<b>Today's Movies :</b>\n"
        f"🎬 <a href=\"{movie_link}\">{file_name}</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"          <b>Released ✅</b>\n"
        f"📌 <b>Pin For Instant Updates</b>\n"
        f"       😎 <b>Check it Out</b> 😎\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await client.send_message(
            chat_id=UPDATE_CHANNEL,
            text=post_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Auto-post Error: {e}")
