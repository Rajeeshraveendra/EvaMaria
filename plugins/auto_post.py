import re
import urllib.parse
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS, ADMINS
from utils import temp
from database.ia_filterdb import save_file

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def get_pure_title(filename):
    """ഫയൽ നെയിമിൽ നിന്നുള്ള ടാഗുകൾ മാറ്റി ശുദ്ധമായ സിനിമയുടെ പേര് ഉണ്ടാക്കുന്നു"""
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
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <i>സിനിമ ഡൗൺലോഡ് ചെയ്യാൻ താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്യുക 👇</i>"
    )
    
    bot_username = temp.U_NAME
    bot_chat_link = f"https://t.me/{bot_username}"

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Search Movie Here ⚡", switch_inline_query_current_chat=movie_title)
        ],
        [
            InlineKeyboardButton("🤖 Go to Bot", url=bot_chat_link)
        ]
    ])
    
    return caption, buttons

# 1. പുതിയ ഫയൽ ചാനലിൽ വരുമ്പോൾ സ്വയം സേവ് ചെയ്യുകയും ഗ്രൂപ്പിലേക്ക് പോസ്റ്റ് ചെയ്യുകയും ചെയ്യുന്നു
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    media = message.document or message.video
    if not media:
        return

    # ഫയൽ ഒരേസമയം MongoDB-യിലേക്ക് സേവ് ചെയ്യുന്നു
    try:
        await save_file(media)
    except TypeError:
        try:
            await save_file(client, message)
        except Exception:
            pass
    except Exception as err:
        print(f"Save File Error: {err}")

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


# 2. ചാനലിലെ പഴയ ഫയലുകൾ MongoDB-ലേക്ക് ഇൻഡെക്സ് ചെയ്യാനുള്ള അഡ്മിൻ കമാൻഡ്: /scan
@Client.on_message(filters.command("scan") & filters.private)
async def scan_channel_files(client, message):
    user_id = message.from_user.id
    admin_list = [int(admin) if str(admin).isdigit() else admin for admin in ADMINS] if isinstance(ADMINS, list) else [int(ADMINS)]
    
    if user_id not in admin_list:
        return await message.reply_text("⚠️ നിങ്ങൾക്ക് ഇതിനുള്ള അഡ്മിൻ അധികാരമില്ല!")

    status_msg = await message.reply_text("⏳ ചാനലിലെ പഴയ ഫയലുകൾ സ്കാൻ ചെയ്യുന്നു... ദയവായി കാത്തിരിക്കുക.")
    total_saved = 0
    scanned_count = 0

    target_channels = []
    if isinstance(CHANNELS, list):
        target_channels.extend([int(c) for c in CHANNELS])
    elif CHANNELS:
        target_channels.append(int(CHANNELS))

    for ch_id in target_channels:
        try:
            async for ch_msg in client.get_chat_history(ch_id):
                scanned_count += 1
                media = ch_msg.document or ch_msg.video
                if media:
                    try:
                        saved = await save_file(media)
                    except TypeError:
                        try:
                            saved = await save_file(client, ch_msg)
                        except TypeError:
                            saved = await save_file(ch_msg)
                        except Exception:
                            saved = False
                    except Exception:
                        saved = False
                    
                    if saved:
                        total_saved += 1
        except Exception as e:
            print(f"Scan error in {ch_id}: {e}")

    await status_msg.edit_text(
        f"✅ <b>സ്കാനിംഗ് പൂർത്തിയായി!</b>\n\n"
        f"📊 ആകെ പരിശോധിച്ച മെസ്സേജുകൾ: <b>{scanned_count}</b>\n"
        f"📁 പുതുതായി സേവ് ചെയ്ത ഫയലുകൾ: <b>{total_saved}</b>"
    )
