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

def get_pure_title(filename):
    """ഫയൽ നെയിമിൽ നിന്ന് സിനിമയുടെ പ്രധാന പേര് മാത്രം എടുക്കുന്നു"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean = []
    for w in words:
        if any(w.lower().startswith(t) for t in tags):
            break
        clean.append(w)
    title = " ".join(clean).strip()
    return title if title else "Movie"

def get_best_search_word(clean_title):
    """ഡാറ്റാബേസിൽ 100% റിസൾട്ട് വരാൻ 'The', 'A' ഒഴിവാക്കി മെയിൻ വാക്ക് എടുക്കുന്നു"""
    words = clean_title.split()
    # 'The Love Hypothesis' ആണെങ്കിൽ 'Love Hypothesis' അല്ലെങ്കിൽ 'Hypothesis'
    filtered = [w for w in words if w.lower() not in ["the", "a", "an", "movie"]]
    if filtered:
        return " ".join(filtered[:2])
    return clean_title

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
        f"📥 <i>ഫയലുകൾ ലഭിക്കാൻ താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്യുക 👇</i>"
    )
    
    bot_username = temp.U_NAME
    search_keyword = get_best_search_word(movie_title)
    
    # EvaMaria ബോട്ടിൽ സെർച്ച് ഫലങ്ങൾ നേരിട്ട് വരാൻ ഈ ഡീപ് ലിങ്ക് ഉപയോഗിക്കാം
    encoded_search = urllib.parse.quote_plus(search_keyword)
    deep_link = f"https://t.me/{bot_username}?start=search_{encoded_search}"
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Download (Get in Bot)", url=deep_link)
        ],
        [
            InlineKeyboardButton("⚡ Search Here", switch_inline_query_current_chat=search_keyword)
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
    base_title = get_pure_title(file_name)
    bot_username = temp.U_NAME

    search_keyword = get_best_search_word(base_title)
    encoded_search = urllib.parse.quote_plus(search_keyword)
    deep_link = f"https://t.me/{bot_username}?start=search_{encoded_search}"
    
    line_entry = f"🎬 <a href=\"{deep_link}\">{file_name}</a>"

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
