import re
import asyncio
import os
import random
import json
import urllib.request
import urllib.parse
import tempfile
from PIL import Image

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from info import CHANNELS, PICS
from database.ia_filterdb import save_file
from utils import temp

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

LOGO_PATH = "assets/rrk_logo.png"

# നിങ്ങളുടെ ചാനൽ, ഗ്രൂപ്പ് ലിങ്കുകൾ
UPDATES_CHANNEL_LINK = "https://t.me/RRK_Movies"
SUPPORT_GROUP_LINK = "https://t.me/RRK_Movies_Group"

POST_CACHE = {}
LOCK = asyncio.Lock()


# ============================================================
# BASIC TEXT CLEANING & EXTRACTION
# ============================================================

def clean_text(text):
    if not text:
        return ""
    text = str(text).replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()

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

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# ============================================================
# OMDb DETAILS (INCLUDING RUNTIME, LANGUAGE ETC.)
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
            runtime = details.get("Runtime", "N/A")
            language = details.get("Language", "Malayalam")
            m_type = details.get("Type", "Movie").capitalize()
            poster = details.get("Poster")

            # ഒറിജിനൽ അൺകംപ്രസ്സ്ഡ് പോസ്റ്റർ എടുക്കുന്നു
            if poster and poster != "N/A":
                poster = re.sub(r"\._V1_.*?\.", "._V1_.", poster)
            else:
                poster = None

            return {
                "title": title,
                "year": movie_year,
                "type": m_type,
                "runtime": runtime,
                "language": language,
                "rating": rating,
                "genres": genres,
                "poster": poster,
                "imdb_id": imdb_id,
                "url": f"https://www.imdb.com/title/{imdb_id}"
            }

        except Exception as e:
            print(f"IMDb/OMDb Error: {e}")
            return None

    return await loop.run_in_executor(None, fetch)


# ============================================================
# LOGO WATERMARK
# ============================================================

async def prepare_hd_poster_with_logo(url):
    if not url:
        return None

    loop = asyncio.get_event_loop()

    def process():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()

            temp_in = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            temp_in.write(data)
            temp_in.close()

            img = Image.open(temp_in.name).convert("RGBA")
            
            if os.path.exists(LOGO_PATH):
                logo = Image.open(LOGO_PATH).convert("RGBA")
                logo_width = int(img.width * 0.22)
                logo_height = int(logo.height * (logo_width / logo.width))
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                img.paste(logo, (int(img.width * 0.04), int(img.height * 0.03)), logo)

            out_temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            out_temp.close()
            img.convert("RGB").save(out_temp.name, "JPEG", quality=98, optimize=True)

            try:
                os.remove(temp_in.name)
            except Exception:
                pass

            return out_temp.name
        except Exception as e:
            print(f"Logo processing error: {e}")
            return None

    return await loop.run_in_executor(None, process)


# ============================================================
# CAPTION & BUTTON FORMAT (SG_SEARCH STYLED)
# ============================================================

def get_caption_and_buttons(movie_title, imdb_info=None):
    bot_username = temp.U_NAME or "RRK_Movies_AutoBot"

    if imdb_info:
        title = imdb_info.get("title", movie_title)
        m_type = imdb_info.get("type", "Movie")
        year = imdb_info.get("year", "")
        runtime = imdb_info.get("runtime", "N/A")
        language = imdb_info.get("language", "Malayalam")
        genres = imdb_info.get("genres", "N/A")
        rating = imdb_info.get("rating", "N/A")
        imdb_url = imdb_info.get("url", f"https://www.google.com/search?q={urllib.parse.quote(movie_title)}")

        caption = (
            f"▫ <b>Title:</b> {title}\n"
            f"▫ <b>Type:</b> {m_type}\n"
            f"▫ <b>Year:</b> {year}\n"
            f"▫ <b>Runtime:</b> {runtime}\n"
            f"▫ <b>Language:</b> {language}\n"
            f"▫ <b>Genre:</b> {genres}\n"
            f"▫ <b>Rating:</b> {rating}/10\n"
            f"▫ <b>More Details:</b> <a href='{imdb_url}'>read here</a>\n\n"
            f"<i>Click the button below to search files...!</i>"
        )
        search_param = f"{title} {year}".strip()
    else:
        caption = (
            f"▫ <b>Title:</b> {movie_title}\n"
            f"▫ <b>Type:</b> Movie\n\n"
            f"<i>Click the button below to search files...!</i>"
        )
        search_param = movie_title

    start_link = f"https://t.me/{bot_username}?start={urllib.parse.quote(search_param)}"
    
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Click to Search Files", url=start_link)
            ],
            [
                InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL_LINK),
                InlineKeyboardButton("👥 Group", url=SUPPORT_GROUP_LINK)
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
    cache_key = f"{base_title.lower()}_{year}" if year else base_title.lower()

    async with LOCK:
        # ഒരു സിനിമയ്ക്ക് ചാനലിൽ ഒറ്റ പോസ്റ്റ് മാത്രം നൽകുന്നു
        if cache_key in POST_CACHE:
            return

        imdb_info = await get_imdb_details(base_title, year)
        caption, buttons = get_caption_and_buttons(base_title, imdb_info)

        raw_poster_url = imdb_info.get("poster") if imdb_info else None
        if not raw_poster_url and PICS:
            raw_poster_url = random.choice(PICS)

        processed_poster = None
        if raw_poster_url:
            processed_poster = await prepare_hd_poster_with_logo(raw_poster_url)

        sent_msg = None
        if processed_poster:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=processed_poster,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"Post send error: {e}")

        if not sent_msg and raw_poster_url:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=raw_poster_url,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"Direct poster error: {e}")

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
                print(f"Text send error: {e}")
                return

        POST_CACHE[cache_key] = sent_msg.id

        if processed_poster and os.path.exists(processed_poster):
            try:
                os.remove(processed_poster)
            except Exception:
                pass
