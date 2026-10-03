import re
import urllib.parse
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS
from utils import temp

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def clean_movie_title(filename):
    """സിനിമയുടെ പേര് ഗ്രൂപ്പ് പോസ്റ്റിനായി വൃത്തിയാക്കുന്നു"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean_words = []
    for w in words:
        if any(w.lower().startswith(t) for t in tags):
            break
        w_clean = re.sub(r"[^a-zA-Z0-9]", "", w)
        if w_clean:
            clean_words.append(w_clean)
            
    final_title = " ".join(clean_words).strip()
    return final_title if final_title else "Movie"

def get_caption_and_buttons(entries):
    movies_list_text = "\n".join(entries)
    caption = (
        f"<b>Today's Movies :</b>\n"
        f"{movies_list_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"          <b>Released ✅</b>\n"
        f"📌 <b>Pin For Instant Updates</b>\n"
        f"       😎 <b>Check it Out</b> 😎\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>മുകളിലുള്ള ലിങ്കുകളിൽ ക്ലിക്ക് ചെയ്ത് ഫയൽ നേരെ ഡൗൺലോഡ് ചെയ്യാം 👆</i>"
    )
    return caption

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
        return

    file_name = media.file_name or "New Movie"
    base_title = clean_movie_title(file_name)
    bot_username = temp.U_NAME

    # EvaMaria ബോട്ടിൽ ഫയൽ ഡൗൺലോഡ് ആകാൻ ഫയലിന്റെ message id ആണ് ഡീപ്പ്-ലിങ്കിൽ വേണ്ടത്
    # ചാനൽ ഐഡിയും മെസ്സേജ് ഐഡിയും ചേർത്തുള്ള EvaMaria deep-link ഫോർമാറ്റ്:
    f_channel = str(message.chat.id).replace("-100", "")
    file_deep_link = f"https://t.me/{bot_username}?start=file_{f_channel}_{message.id}"
    
    line_entry = f"🎬 <a href=\"{file_deep_link}\">{file_name}</a>"

    async with LOCK:
        # നിലവിൽ ഇതേ സിനിമയ്ക്ക് പോസ്റ്റ് ഉണ്ടെങ്കിൽ ആ പോസ്റ്റിലേക്ക് ലിങ്ക് ആഡ് ചെയ്യുന്നു
        if base_title in POST_CACHE:
            data = POST_CACHE[base_title]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                caption = get_caption_and_buttons(data["entries"])
                
                try:
                    await client.edit_message_caption(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Edit Caption Error: {e}")
            return

        entries = [line_entry]
        caption = get_caption_and_buttons(entries)

        sent_msg = None
        if PICS:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=random.choice(PICS),
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Custom Poster error: {err}")

        if not sent_msg:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=caption,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        POST_CACHE[base_title] = {
            "msg_id": sent_msg.id,
            "entries": entries
        }
