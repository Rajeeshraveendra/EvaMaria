import re
import urllib.parse
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import CHANNELS, PICS
from utils import temp

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1001452215783"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def clean_movie_title(filename):
    """Filename-il ninnu movie name maathram edukkunnu"""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean_words = []
    for w in words:
        if w.lower() in tags:
            break
        clean_words.append(w)
    
    final_title = " ".join(clean_words).strip().title()
    return final_title if final_title else name[:15]

def get_caption_and_buttons(movie_title, entries):
    """Post caption-um inline buttons-um tayyaaraakkunnu"""
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
    
    # Direct DM delivery button & Start link button
    search_query = urllib.parse.quote(movie_title)
    bot_username = temp.U_NAME
    deep_link = f"https://t.me/{bot_username}?start={search_query}"
    
    # Callback query data length kuravaayirikkan safe aayi slice cheyyunnu
    cb_data = f"getfile#{movie_title[:40]}"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Get Movie Files (DM)", callback_data=cb_data)],
        [InlineKeyboardButton("🤖 Open in Bot", url=deep_link)]
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
    
    search_query = urllib.parse.quote(base_title)
    bot_username = temp.U_NAME
    movie_link = f"https://t.me/{bot_username}?start={search_query}"
    
    line_entry = f"🎬 <a href=\"{movie_link}\">{file_name}</a>"

    async with LOCK:
        # Existing movie post update cheyyunnu
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

        # Puthiya post ayakkunnu
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


# Member group-il "Get Movie Files" button click cheyyumbol ulla action
@Client.on_callback_query(filters.regex(r"^getfile#"))
async def send_files_to_user_dm(client, query: CallbackQuery):
    movie_name = query.data.split("#", 1)[1]
    user_id = query.from_user.id
    bot_username = temp.U_NAME

    # Database query search EvaMaria logic vazhi
    from database.ia_filterdb import get_search_results
    
    files, total = await get_search_results(chat_id=user_id, query=movie_name, max_results=10)
    
    if not files:
        return await query.answer("Kshamikkuka, ee cinimayude files ippol labhyamalla!", show_alert=True)

    try:
        # User-nte private chat-ilekku files ayakkunnu
        await client.send_message(
            chat_id=user_id,
            text=f"🎬 <b>{movie_name}</b> - Files thaazhe nalkunnu:"
        )
        for file in files:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file.file_id,
                caption=f"📁 <code>{file.file_name}</code>"
            )
        await query.answer("✅ Files ningalude Inbox (PM)-lekku ayachittundu! Check cheyyuka.", show_alert=True)
    except Exception as e:
        # User munpu bot start cheythittillengil alert kaanikkunnu
        start_url = f"https://t.me/{bot_username}?start={urllib.parse.quote(movie_name)}"
        await query.answer(
            "⚠️ Ningalude PM-lekku message ayakkan kazhiyunilla!\n\nAadyam thazheyulla 'Open in Bot' click cheythu START adikkuka.",
            show_alert=True
        )
