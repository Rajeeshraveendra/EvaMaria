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
    """ഫയൽ നെയിമിൽ നിന്ന് സിനിമയുടെ പ്രധാന പേര് മാത്രം കൃത്യമായി വേർതിരിച്ചെടുക്കുന്നു"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean_words = []
    for w in words:
        if any(w.lower().startswith(t) for t in tags):
            break
        # അനാവശ്യ സ്പെഷ്യൽ ചിഹ്നങ്ങൾ മാറ്റുന്നു
        w_clean = re.sub(r"[^a-zA-Z0-9]", "", w)
        if w_clean:
            clean_words.append(w_clean)
    
    final_title = " ".join(clean_words[:4]).strip().title()
    return final_title if final_title else "Movie"

def get_caption_and_buttons(movie_title, entries):
    movies_list_text = "\n".join(entries)
    caption = (
        f"<b>Today's Movies :</b>\n"
        f"{movies_list_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"          <b>Released ✅</b>\n"
        f"📌 <b>Pin For Instant Updates</b>\n"
        f"       😎 <b>Check it Out</b> 😎\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്ത് ഫയലുകൾ എടുക്കുക 👇</i>"
    )
    
    bot_username = temp.U_NAME
    # ലിങ്കിൽ സ്പേസുകൾക്ക് പകരം '+' അല്ലെങ്കിൽ സേഫ് ഫോർമാറ്റ് നൽകുന്നു
    safe_query = re.sub(r"[^a-zA-Z0-9 ]", "", movie_title).strip()
    encoded_query = urllib.parse.quote_plus(safe_query)
    deep_link = f"https://t.me/{bot_username}?start={encoded_query}"
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Instant Files (ഇവിടെ കാണുക)", switch_inline_query_current_chat=safe_query)
        ],
        [
            InlineKeyboardButton("🤖 Open in Bot (DM)", url=deep_link)
        ]
    ])
    
    return caption, buttons

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
        return

    file_name = media.file_name or "New Movie"
    base_title = clean_movie_title(file_name)
    
    safe_query = re.sub(r"[^a-zA-Z0-9 ]", "", base_title).strip()
    search_query = urllib.parse.quote_plus(safe_query)
    bot_username = temp.U_NAME
    movie_link = f"https://t.me/{bot_username}?start={search_query}"
    
    line_entry = f"🎬 <a href=\"{movie_link}\">{file_name}</a>"

    async with LOCK:
        if base_title in POST_CACHE:
            data = POST_CACHE[base_title]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                caption, buttons = get_caption_and_buttons(base_title, data["entries"])
                
                try:
                    await client.edit_message_caption(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        caption=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Edit Caption Error: {e}")
            return

        entries = [line_entry]
        caption, buttons = get_caption_and_buttons(base_title, entries)

        sent_msg = None
        if PICS:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=random.choice(PICS),
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Custom Poster error: {err}")

        if not sent_msg:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        POST_CACHE[base_title] = {
            "msg_id": sent_msg.id,
            "entries": entries
        }
