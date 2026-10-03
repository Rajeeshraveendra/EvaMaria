import re
import urllib.parse
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from info import CHANNELS, PICS
from utils import temp

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def clean_movie_title(filename):
    """ഫയൽ നെയിമിൽ നിന്ന് സിനിമയുടെ പ്രധാന പേര് മാത്രം കൃത്യമായി വേർതിരിച്ചെടുക്കുന്നു"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    # ക്വാളിറ്റികളും ഭാഷകളും മാറ്റി പേര് മാത്രം കണ്ടെത്തുന്നു
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean_words = []
    for w in words:
        if w.lower() in tags:
            break
        clean_words.append(w)
    
    final_title = " ".join(clean_words).strip().title()
    return final_title if final_title else name[:15]

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
        return

    file_name = media.file_name or "New Movie"
    base_title = clean_movie_title(file_name)
    
    search_query = urllib.parse.quote(base_title)
    bot_username = temp.U_NAME
    movie_link = f"https://t.me/{bot_username}?start={search_query}"
    
    line_entry = f"🎬 <a href=\"{movie_link}\">{file_name}</a>"

    async with LOCK:
        # നിലവിൽ ഇതേ സിനിമയ്ക്ക് പോസ്റ്റ് ഉണ്ടെങ്കിൽ ആ പോസ്റ്റിലേക്ക് എഡിറ്റ് ചെയ്ത് ചേർക്കുന്നു
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
        # മറ്റുള്ളവരുടെ തമ്പ്‌നെയിൽ ഒഴിവാക്കി നിങ്ങളുടെ ബോട്ടിന്റെ സ്വന്തം ഇമേജ് (PICS) നൽകുന്നു
        if PICS:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=random.choice(PICS),
                    caption=initial_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Custom Poster error: {err}")

        # ഇമേജ് വന്നില്ലെങ്കിൽ സാധാരണ ടെക്സ്റ്റ് ആയി അയക്കുന്നു
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
