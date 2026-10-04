import re
import asyncio
import os
import random
import json
import urllib.request
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS, ADMINS
from database.ia_filterdb import save_file

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def extract_movie_info(filename):
    # Bracket contents, Extension എന്നിവ ഒഴിവാക്കുന്നു
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = re.sub(r"\.[a-zA-Z0-9]{2,4}$", "", name)
    
    # ചാനൽ ടാഗുകൾ ഒഴിവാക്കുന്നു (ഉദാ: @WMR_, @ChannelName)
    name = re.sub(r"@\w+[_]?", "", name)
    
    # സ്പെഷ്യൽ ക്യാരക്ടറുകൾ മാറ്റി സ്പേസ് ആക്കുന്നു
    name = name.replace(".", " ").replace("_", " ").replace("-", " ").strip()

    # വർഷം കണ്ടെത്തുന്നു (1900 - 2099)
    year_match = re.search(r"\b(19\d\d|20\d\d)\b", name)
    year = year_match.group(1) if year_match else None

    # അനാവശ്യ ടാഗുകൾ
    tags = [
        "hindi", "tamil", "telugu", "malayalam", "kannada", "english", "bengali",
        "hdrip", "web-dl", "webrip", "hevc", "720p", "1080p", "480p", "2160p", "dvdrip",
        "aac", "x264", "x265", "esub", "sps", "mkv", "mp4", "wmr"
    ]
    
    clean_words = []
    for word in name.split():
        w_lower = word.lower()
        if year and word == year:
            break
        if any(w_lower == t or w_lower.startswith(t) for t in tags):
            break
        clean_words.append(word)

    clean_title = " ".join(clean_words).strip()
    if not clean_title:
        clean_title = name.split()[0] if name.split() else "Movie"

    return clean_title, year

async def get_imdb_details(movie_name, year=None):
    loop = asyncio.get_event_loop()
    def fetch():
        try:
            # 1. വർഷം ഉൾപ്പെടെ ആദ്യം തിരയുന്നു
            q = urllib.parse.quote(movie_name)
            url = f"https://www.omdbapi.com/?t={q}&y={year or ''}&apikey=b6636080"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            res = urllib.request.urlopen(req, timeout=6)
            data = json.loads(res.read().decode())
            
            # 2. കിട്ടിയില്ലെങ്കിൽ വർഷം ഒഴിവാക്കി പേര് മാത്രം വെച്ച് തിരയുന്നു
            if data.get("Response") != "True":
                url_fallback = f"https://www.omdbapi.com/?t={q}&apikey=b6636080"
                req_fallback = urllib.request.Request(url_fallback, headers={'User-Agent': 'Mozilla/5.0'})
                res_fallback = urllib.request.urlopen(req_fallback, timeout=6)
                data = json.loads(res_fallback.read().decode())

            if data.get("Response") == "True":
                title = data.get("Title", movie_name)
                m_year = data.get("Year", year or "")
                rating = data.get("imdbRating", "N/A")
                genres = data.get("Genre", "N/A")
                story = data.get("Plot", "No storyline available.")
                poster = data.get("Poster") if data.get("Poster") != "N/A" else None
                
                return {
                    "title": f"{title} ({m_year})" if m_year else title,
                    "search_title": title,
                    "rating": rating,
                    "genres": genres,
                    "story": story,
                    "poster": poster
                }
            return None
        except Exception as e:
            print(f"IMDb API Error: {e}")
            return None

    return await loop.run_in_executor(None, fetch)

def get_caption_and_buttons(movie_title, entries, imdb_info=None):
    files_text = "\n".join(entries)
    
    if imdb_info:
        caption = (
            f"🎬 <b>{imdb_info['title']}</b>\n\n"
            f"⭐️ <b>IMDb Rating :</b> {imdb_info['rating']}/10\n"
            f"🎭 <b>Genres :</b> {imdb_info['genres']}\n\n"
            f"📖 <b>Storyline :</b>\n<i>{imdb_info['story']}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Available Files :</b>\n"
            f"{files_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Released & Verified</b> ✅"
        )
        search_keyword = imdb_info.get("search_title", movie_title)
    else:
        caption = (
            f"<b>Today's Movies :</b>\n"
            f"{files_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"          <b>Released ✅</b>\n"
            f"📌 <b>Pin For Instant Updates</b>\n"
            f"       😎 <b>Check it Out</b> 😎\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        search_keyword = movie_title
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=search_keyword)]
    ])
    
    return caption, buttons

# 1. Direct file save handler
@Client.on_message(filters.private & (filters.document | filters.video))
async def save_direct_files(client, message):
    media = message.document or message.video
    if not media:
        return

    if not hasattr(media, 'file_type'):
        media.file_type = "video" if message.video else "document"
    if not hasattr(media, 'caption'):
        media.caption = None

    try:
        saved = await save_file(media)
        is_success = saved[0] if isinstance(saved, tuple) else saved
        if is_success:
            await message.reply_text(f"✅ <b>Database-il save cheythu!</b>\n\n📁 <code>{media.file_name}</code>", quote=True)
        else:
            await message.reply_text(f"ℹ <b>File already database-il undu:</b>\n\n📁 <code>{media.file_name}</code>", quote=True)
    except Exception as e:
        await message.reply_text(f"⚠️ <b>Save cheyyan kazhinjilla:</b>\n<code>{e}</code>", quote=True)

# 2. Channel forward auto post with IMDb storyline
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    media = message.document or message.video
    if not media:
        return

    try:
        if not hasattr(media, 'file_type'):
            media.file_type = "video" if message.video else "document"
        if not hasattr(media, 'caption'):
            media.caption = None
        await save_file(media)
    except Exception as err:
        print(f"Channel DB Save Error: {err}")

    if not UPDATE_CHANNEL:
        return

    file_name = getattr(media, 'file_name', 'New Movie')
    base_title, year = extract_movie_info(file_name)
    line_entry = f"🎬 {file_name}"

    cache_key = f"{base_title.lower()}_{year}" if year else base_title.lower()

    async with LOCK:
        if cache_key in POST_CACHE:
            data = POST_CACHE[cache_key]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                caption, buttons = get_caption_and_buttons(base_title, data["entries"], data.get("imdb_info"))
                
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

        imdb_info = await get_imdb_details(base_title, year)
        entries = [line_entry]
        caption, buttons = get_caption_and_buttons(base_title, entries, imdb_info)

        sent_msg = None
        photo_url = imdb_info.get("poster") if (imdb_info and imdb_info.get("poster")) else (random.choice(PICS) if PICS else None)

        if photo_url:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=photo_url,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Poster send error: {err}")

        if not sent_msg:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        POST_CACHE[cache_key] = {
            "msg_id": sent_msg.id,
            "entries": entries,
            "imdb_info": imdb_info
        }
