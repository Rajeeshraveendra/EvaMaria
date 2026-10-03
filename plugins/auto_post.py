import re
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS, ADMINS
from utils import temp
from database.ia_filterdb import save_file

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))
DB_CHANNEL_ID = -1003799495012

POST_CACHE = {}
LOCK = asyncio.Lock()

def get_pure_title(filename):
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
    return title if title else (words[0] if words else "Movie")

def get_caption_and_buttons(movie_title, entries):
    movies_list_text = "\n".join(entries)
    caption = (
        f"<b>Today's Movies :</b>\n"
        f"{movies_list_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"          <b>Released ✅</b>\n"
        f"📌 <b>Pin For Instant Updates</b>\n"
        f"       😎 <b>Check it Out</b> 😎\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=movie_title)]
    ])
    
    return caption, buttons

# 1. ബോട്ടിലേക്ക് അയക്കുന്ന അല്ലെങ്കിൽ ഫോർവേഡ് ചെയ്യുന്ന ഫയലുകൾ സേവ് ചെയ്യാനും എറർ കൃത്യമായി കാണിക്കാനും
@Client.on_message(filters.private & (filters.document | filters.video), group=-1)
async def save_direct_files(client, message):
    media = message.document or message.video
    if not media:
        return

    saved = False
    err_info = ""

    # പല രീതിയിലുള്ള save_file കോളിംഗുകൾ പരീക്ഷിക്കുന്നു
    try:
        saved = await save_file(client, message)
    except Exception as e1:
        try:
            saved = await save_file(message)
        except Exception as e2:
            try:
                saved = await save_file(media)
            except Exception as e3:
                err_info = f"E1: {e1} | E2: {e2} | E3: {e3}"

    if saved:
        await message.reply_text(f"✅ <b>ഫയൽ സേവ് ചെയ്തു:</b>\n<code>{media.file_name}</code>", quote=True)
    else:
        await message.reply_text(f"⚠️ <b>സേവ് ചെയ്യാൻ കഴിഞ്ഞില്ല:</b>\n<code>{err_info}</code>", quote=True)

# 2. ചാനലിൽ പുതിയ ഫയലുകൾ വരുമ്പോൾ ഓട്ടോ പോസ്റ്റും ഒപ്പം MongoDB സേവും
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    media = message.document or message.video
    if not media:
        return

    try:
        await save_file(client, message)
    except Exception:
        try:
            await save_file(message)
        except Exception:
            pass

    if not UPDATE_CHANNEL:
        return

    file_name = media.file_name or "New Movie"
    base_title = get_pure_title(file_name)
    line_entry = f"🎬 {file_name}"

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
