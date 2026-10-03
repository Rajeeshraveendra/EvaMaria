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

# ia_filterdb-ൽ കൃത്യമായി സേവ് ആവാൻ മീഡിയ ഒബ്ജക്റ്റ് പാക്ക് ചെയ്യുന്ന ഹെൽപ്പർ ഫംഗ്ഷൻ
async def save_media_to_db(message):
    media = message.document or message.video or message.audio
    if not media:
        return False, "No media"
    
    # EvaMaria പ്രതീക്ഷിക്കുന്ന ഫീൽഡുകൾ ചേർക്കുന്നു
    if not hasattr(media, 'file_type'):
        if message.video:
            media.file_type = "video"
        elif message.audio:
            media.file_type = "audio"
        else:
            media.file_type = "document"
            
    if not hasattr(media, 'caption'):
        media.caption = message.caption

    try:
        res = await save_file(media)
        # res എന്നത് (True, 1) അല്ലെങ്കിൽ (False, 0) ആണ്
        if isinstance(res, tuple):
            saved, code = res
            if saved:
                return True, "Saved"
            elif code == 0:
                return False, "Already in database"
            else:
                return False, "Validation error"
        return bool(res), "Done"
    except Exception as e:
        return False, str(e)


# 1. ബോട്ടിലേക്ക് നേരിട്ട് ഫോർവേഡ് ചെയ്യുന്ന ഫയലുകൾ സേവ് ചെയ്യാൻ
@Client.on_message(filters.private & (filters.document | filters.video), group=-1)
async def save_direct_files(client, message):
    saved, msg = await save_media_to_db(message)
    media = message.document or message.video
    if saved:
        await message.reply_text(f"✅ <b>ഡാറ്റാബേസിൽ സേവ് ചെയ്തു:</b>\n<code>{media.file_name}</code>", quote=True)
    elif msg == "Already in database":
        await message.reply_text(f"ℹ️ <b>ഈ ഫയൽ ഇതിനകം ഡാറ്റാബേസിൽ ഉണ്ട്:</b>\n<code>{media.file_name}</code>", quote=True)
    else:
        await message.reply_text(f"⚠️ <b>സേവ് എറർ:</b> <code>{msg}</code>", quote=True)


# 2. ചാനലിൽ പുതിയ ഫയലുകൾ വരുമ്പോൾ ഓട്ടോ പോസ്റ്റും ഒപ്പം MongoDB സേവും
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    await save_media_to_db(message)

    if not UPDATE_CHANNEL:
        return

    media = message.document or message.video
    if not media:
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
