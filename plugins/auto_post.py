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

# 1. ബോട്ടിലേക്ക് നേരിട്ട് ഫോർവേഡ് ചെയ്യുന്ന ഫയലുകൾ സ്വയം MongoDB-ൽ സേവ് ചെയ്യാൻ
@Client.on_message(filters.private & (filters.document | filters.video))
async def save_direct_files(client, message):
    saved = False
    try:
        saved = await save_file(client, message)
    except TypeError:
        try:
            saved = await save_file(message)
        except TypeError:
            media = message.document or message.video
            saved = await save_file(media)
    except Exception:
        saved = False

    if saved:
        media = message.document or message.video
        await message.reply_text(f"✅ <b>ഫയൽ ഡാറ്റാബേസിൽ സേവ് ചെയ്തു:</b>\n<code>{media.file_name}</code>", quote=True)

# 2. ചാനലിൽ പുതിയ ഫയലുകൾ വരുമ്പോൾ ഓട്ടോ പോസ്റ്റും ഒപ്പം MongoDB സേവും
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    try:
        await save_file(client, message)
    except TypeError:
        try:
            await save_file(message)
        except TypeError:
            media = message.document or message.video
            await save_file(media)
    except Exception as err:
        print(f"Save File Error: {err}")

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

# 3. മെസ്സേജ് ഐഡി വെച്ച് പഴയ മുഴുവൻ ഫയലുകളും സേവ് ചെയ്യാനുള്ള അഡ്മിൻ കമാൻഡ്
# ഉപയോഗിക്കേണ്ട രീതി: /index 14 306
@Client.on_message(filters.command("index") & filters.private)
async def custom_index_command(client, message):
    user_id = message.from_user.id
    admin_list = [int(admin) if str(admin).isdigit() else admin for admin in ADMINS] if isinstance(ADMINS, list) else [int(ADMINS)]
    if user_id not in admin_list:
        return

    args = message.text.split()
    if len(args) < 3:
        return await message.reply_text("ഉപയോഗിക്കേണ്ട രീതി:\n<code>/index 14 306</code>")

    try:
        start_id = int(args[1])
        end_id = int(args[2])
    except ValueError:
        return await message.reply_text("നമ്പറുകൾ കൃത്യമായി നൽകുക!")

    status_msg = await message.reply_text(f"⏳ {start_id} മുതൽ {end_id} വരെയുള്ള മെസ്സേജുകൾ സ്കാൻ ചെയ്യുന്നു...")
    saved_count = 0

    for msg_id in range(start_id, end_id + 1):
        try:
            ch_msg = await client.get_messages(DB_CHANNEL_ID, msg_id)
            if ch_msg and (ch_msg.document or ch_msg.video):
                saved = False
                try:
                    saved = await save_file(client, ch_msg)
                except TypeError:
                    try:
                        saved = await save_file(ch_msg)
                    except TypeError:
                        media = ch_msg.document or ch_msg.video
                        saved = await save_file(media)
                if saved:
                    saved_count += 1
        except Exception as e:
            print(f"Error indexing {msg_id}: {e}")

    await status_msg.edit_text(f"✅ പൂർത്തിയായി!\n📁 ആകെ സേവ് ചെയ്ത ഫയലുകൾ: <b>{saved_count}</b>")
