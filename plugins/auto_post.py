import re
import asyncio
import os
import random
import json
import urllib.request
import urllib.parse
import tempfile

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from info import CHANNELS, PICS
from database.ia_filterdb import save_file

# ============================================================
# CONFIG
# ============================================================

UPDATE_CHANNEL = int(
    os.environ.get(
        "UPDATE_CHANNEL",
        "-1003799495012"
    )
)

OMDB_API_KEY = os.environ.get(
    "OMDB_API_KEY",
    "97960898"
)

POST_CACHE = {}
LOCK = asyncio.Lock()


# ============================================================
# BASIC TEXT CLEANING
# ============================================================

def clean_text(text):
    if not text:
        return ""
    text = str(text).replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# MOVIE TITLE EXTRACTION
# ============================================================

def extract_movie_info(filename):
    name = os.path.basename(filename)
    name = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", name)
    name = re.sub(r"\[[^\]]*\]", " ", name)
    name = re.sub(r"\([^)]*\)", " ", name)
    name = re.sub(r"@\w+", " ", name)
    name = name.replace("_", " ").replace(".", " ").replace("-", " ")
    name = re.sub(r"([A-Za-z])(\d{4})", r"\1 \2", name)
    name = re.sub(r"(\d{4})([A-Za-z])", r"\1 \2", name)
    name = re.sub(r"\s+", " ", name).strip()

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name)
    year = year_match.group(1) if year_match else None

    stop_words = {
        "hindi", "tamil", "telugu", "malayalam", "kannada", "english", "bengali", "marathi",
        "hq", "hd", "fullhd", "hdrip", "webdl", "web-dl", "web", "webrip", "web-rip",
        "bluray", "blu-ray", "brrip", "dvdrip", "dvd", "tvrip", "tv-rip", "hdts", "hdtc", "cam", "camrip",
        "hevc", "x264", "x265", "480p", "720p", "1080p", "2160p", "4k", "aac", "dd", "ddp", "eac3", "ac3", "5.1",
        "esub", "subs", "subtitle", "subtitles", "mkv", "mp4", "avi", "proper", "repack",
        "amzn", "amazon", "netflix", "nfx", "hotstar", "disney", "zee5", "sonyliv", "aha", "jio",
        "gb", "mb", "dvdwo", "wmr", "sps", "mollywooddaires", "mallumovies", "cinemavilla"
    }

    title_words = []
    for word in name.split():
        lower = word.lower()
        if year and word == year:
            break
        if re.fullmatch(r"\d+(?:\.\d+)?(?:gb|mb)", lower):
            break
        if lower in stop_words:
            break
        if re.fullmatch(r"\d+", lower):
            continue
        title_words.append(word)

    title = " ".join(title_words).strip()
    title = re.sub(r"^(dvdwo|wmr|sps|mollywooddaires)\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()

    if not title:
        title = "Movie"

    return title, year


# ============================================================
# HTTP JSON HELPER
# ============================================================

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# ============================================================
# IMDb / OMDb SEARCH (WITH 4K POSTER URL RESOLVER)
# ============================================================

async def get_imdb_details(movie_name, year=None):
    loop = asyncio.get_event_loop()

    def fetch():
        try:
            query = urllib.parse.quote(movie_name)
            search_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={query}&type=movie"
            if year:
                search_url += f"&y={year}"

            search_data = fetch_json(search_url)
            results = search_data.get("Search", [])
            selected = None

            wanted = re.sub(r"[^a-z0-9]+", "", movie_name.lower())
            for item in results:
                item_title = item.get("Title", "")
                normalized = re.sub(r"[^a-z0-9]+", "", item_title.lower())
                item_year = str(item.get("Year", ""))

                if normalized == wanted and (not year or item_year.startswith(str(year))):
                    selected = item
                    break

            if not selected and year:
                for item in results:
                    if str(item.get("Year", "")).startswith(str(year)):
                        selected = item
                        break

            if not selected and results:
                selected = results[0]

            if not selected:
                fallback_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={query}&type=movie"
                fallback_data = fetch_json(fallback_url)
                fallback_results = fallback_data.get("Search", [])
                if fallback_results:
                    selected = fallback_results[0]

            if not selected:
                return None

            imdb_id = selected.get("imdbID")
            if not imdb_id:
                return None

            detail_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={urllib.parse.quote(imdb_id)}&plot=full"
            details = fetch_json(detail_url)

            if details.get("Response") != "True":
                return None

            title = details.get("Title", movie_name)
            movie_year = details.get("Year", year or "")
            rating = details.get("imdbRating", "N/A")
            genres = details.get("Genre", "N/A")
            story = details.get("Plot", "No storyline available.")
            poster = details.get("Poster")

            # 4K / Full HD റെസല്യൂഷനിലേക്ക് പോസ്റ്റർ URL മാറ്റുന്നു
            if poster and poster != "N/A":
                poster = re.sub(r"_SX\d+|_SY\d+|_CR\d+,\d+,\d+,\d+_|_AL_", "_SX1600_", poster)
            else:
                poster = None

            return {
                "title": title,
                "year": movie_year,
                "display_title": f"{title} ({movie_year})" if movie_year else title,
                "search_title": title,
                "rating": rating,
                "genres": genres,
                "story": story,
                "poster": poster,
                "imdb_id": imdb_id
            }

        except Exception as e:
            print(f"IMDb/OMDb Error: {e}")
            return None

    return await loop.run_in_executor(None, fetch)


# ============================================================
# CAPTION & BUTTONS
# ============================================================

def get_caption_and_buttons(movie_title, entries, imdb_info=None):
    files_text = "\n".join(entries)

    if imdb_info:
        caption = (
            f"🎬 <b>{imdb_info['display_title']}</b>\n\n"
            f"⭐ <b>IMDb Rating :</b> {imdb_info['rating']}/10\n"
            f"🎭 <b>Genre :</b> {imdb_info['genres']}\n"
            f"📅 <b>Release :</b> {imdb_info['year']}\n\n"
            f"📖 <b>Storyline :</b>\n<i>{imdb_info['story']}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎞 <b>Available Files</b>\n"
            f"{files_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Released & Verified</b> ✅\n"
            f"🔎 <b>Search & Download</b>"
        )
        search_keyword = imdb_info.get("search_title", movie_title)
    else:
        caption = (
            f"🎬 <b>{movie_title}</b>\n\n"
            f"🎞 <b>Available Files</b>\n"
            f"{files_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Released & Verified</b> ✅"
        )
        search_keyword = movie_title

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📥 DOWNLOAD MOVIE 📥",
                    switch_inline_query_current_chat=search_keyword
                )
            ]
        ]
    )

    return caption, buttons


# ============================================================
# PRIVATE FILE SAVE
# ============================================================

@Client.on_message(filters.private & (filters.document | filters.video))
async def save_direct_files(client, message):
    media = message.document or message.video
    if not media:
        return

    if not hasattr(media, "file_type"):
        media.file_type = "video" if message.video else "document"

    if not hasattr(media, "caption"):
        media.caption = None

    try:
        saved = await save_file(media)
        success = saved[0] if isinstance(saved, tuple) else saved
        file_name = getattr(media, "file_name", "Unknown File")

        if success:
            await message.reply_text(
                f"✅ <b>Database-il save cheythu!</b>\n\n📁 <code>{file_name}</code>",
                quote=True
            )
        else:
            await message.reply_text(
                f"ℹ️ <b>File already database-il undu.</b>\n\n📁 <code>{file_name}</code>",
                quote=True
            )
    except Exception as e:
        await message.reply_text(
            f"⚠️ <b>Save cheyyan kazhinjilla:</b>\n<code>{e}</code>",
            quote=True
        )


# ============================================================
# CHANNEL AUTO POST
# ============================================================

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    media = message.document or message.video
    if not media:
        return

    try:
        if not hasattr(media, "file_type"):
            media.file_type = "video" if message.video else "document"
        if not hasattr(media, "caption"):
            media.caption = None
        await save_file(media)
    except Exception as e:
        print(f"Database save error: {e}")

    if not UPDATE_CHANNEL:
        return

    file_name = getattr(media, "file_name", "New Movie")
    base_title, year = extract_movie_info(file_name)
    line_entry = f"🎬 <code>{file_name}</code>"
    cache_key = f"{base_title.lower()}_{year}" if year else base_title.lower()

    async with LOCK:
        if cache_key in POST_CACHE:
            data = POST_CACHE[cache_key]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                caption, buttons = get_caption_and_buttons(
                    base_title,
                    data["entries"],
                    data.get("imdb_info")
                )
                try:
                    await client.edit_message_caption(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        caption=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Caption update error: {e}")
            return

        imdb_info = await get_imdb_details(base_title, year)

        if not imdb_info:
            imdb_info = {
                "title": base_title,
                "year": year or "",
                "display_title": f"{base_title} ({year})" if year else base_title,
                "search_title": base_title,
                "rating": "N/A",
                "genres": "N/A",
                "story": "Movie information is currently unavailable.",
                "poster": None
            }

        entries = [line_entry]
        caption, buttons = get_caption_and_buttons(base_title, entries, imdb_info)

        # യഥാർത്ഥ പോസ്റ്റർ URL അല്ലെങ്കിൽ ബാക്കപ്പ് ചിത്രം നേരിട്ട് എടുക്കുന്നു
        poster_to_send = imdb_info.get("poster")
        if not poster_to_send and PICS:
            poster_to_send = random.choice(PICS)

        sent_msg = None

        # 1. ഒറിജിനൽ ഫുൾ സൈസ് HD/4K പോസ്റ്റർ നേരിട്ട് അയക്കുന്നു (ബ്ലാക്ക് ബോക്സ് ഇല്ലാതെ)
        if poster_to_send:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=poster_to_send,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"Poster send error: {e}")

        # 2. ഫോട്ടോ പരാജയപ്പെട്ടാൽ മാത്രം ടെക്സ്റ്റ് ആയി അയക്കുന്നു
        if not sent_msg:
            try:
                sent_msg = await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"Text post error: {e}")
                return

        POST_CACHE[cache_key] = {
            "msg_id": sent_msg.id,
            "entries": entries,
            "imdb_info": imdb_info
        }

        print(f"[AUTO POST] Successfully posted: {imdb_info.get('display_title')}")
