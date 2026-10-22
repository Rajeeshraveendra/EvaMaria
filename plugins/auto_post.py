import re
import asyncio
import os
import random
import json
import base64
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
from database.ia_filterdb import save_file, db
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

TMDB_API_KEY = (os.environ.get("TMDB_API_KEY") or "").strip()

LANG_NAMES = {
    "ml": "Malayalam", "ta": "Tamil", "te": "Telugu", "hi": "Hindi", "kn": "Kannada",
    "en": "English", "bn": "Bengali", "mr": "Marathi", "ko": "Korean", "ja": "Japanese",
}

LOGO_PATH = "assets/rrk_logo.png"

UPDATES_CHANNEL_LINK = "https://t.me/RRK_Movies"
SUPPORT_GROUP_LINK = "https://t.me/RRK_Movies_Group"
ADMIN_LINK = "https://t.me/RajeeshRaveendra"

POST_CACHE = {}
LOCK = asyncio.Lock()
POSTED_DB = db["auto_posted"]  # posted movies stay remembered across restarts


def norm_key(text):
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


async def already_posted(*keys):
    keys = [k for k in keys if k]
    for k in keys:
        if k in POST_CACHE:
            return True
    try:
        if keys and await POSTED_DB.find_one({"_id": {"$in": keys}}):
            return True
    except Exception as e:
        print(f"Posted-check DB error: {e}")
    return False


async def mark_posted(msg_id, *keys):
    for k in [k for k in keys if k]:
        POST_CACHE[k] = msg_id
        try:
            await POSTED_DB.update_one({"_id": k}, {"$set": {"msg_id": msg_id}}, upsert=True)
        except Exception as e:
            print(f"Posted-save DB error: {e}")


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


def imdb_poster_by_id(imdb_id):
    """OMDb poster dead aanenkil IMDb-il ninnu puthiya poster edukkum"""
    try:
        d = fetch_json(f"https://v3.sg.media-imdb.com/suggestion/t/{urllib.parse.quote(imdb_id)}.json")
        for it in d.get("d", []):
            if it.get("id") == imdb_id:
                url = (it.get("i") or {}).get("imageUrl")
                if url:
                    return re.sub(r"\._V1_.*?\.", "._V1_SX1000.", url)
    except Exception as e:
        print(f"IMDb poster lookup error: {e}")
    return None


def fallback_details(movie_name, year=None, imdb_id=None, sugg=None):
    """OMDb-il illatha puthiya movies: TMDB / IMDb suggestion vazhi details"""
    info = None
    if TMDB_API_KEY:
        try:
            base = "https://api.themoviedb.org/3"
            key = urllib.parse.quote(TMDB_API_KEY)
            tmdb_id = None
            if imdb_id:
                f = fetch_json(f"{base}/find/{imdb_id}?api_key={key}&external_source=imdb_id")
                res = f.get("movie_results") or []
                if res:
                    tmdb_id = res[0].get("id")
            if not tmdb_id:
                q = f"{base}/search/movie?api_key={key}&query={urllib.parse.quote(movie_name)}"
                if year:
                    q += f"&year={year}"
                res = fetch_json(q).get("results") or []
                if res:
                    tmdb_id = res[0].get("id")
            if tmdb_id:
                m = fetch_json(f"{base}/movie/{tmdb_id}?api_key={key}&append_to_response=external_ids")
                imdb_id = imdb_id or (m.get("external_ids") or {}).get("imdb_id")
                rt = m.get("runtime")
                va = m.get("vote_average")
                poster = f"https://image.tmdb.org/t/p/w780{m['poster_path']}" if m.get("poster_path") else None
                info = {
                    "title": m.get("title") or movie_name,
                    "year": (m.get("release_date") or "")[:4] or (year or ""),
                    "type": "Movie",
                    "runtime": f"{rt} min" if rt else "N/A",
                    "language": LANG_NAMES.get(m.get("original_language"), m.get("original_language") or "N/A"),
                    "rating": f"{va:.1f}" if va else "N/A",
                    "genres": ", ".join(g["name"] for g in m.get("genres", [])) or "N/A",
                    "poster": poster,
                    "imdb_id": imdb_id,
                    "url": f"https://www.imdb.com/title/{imdb_id}" if imdb_id else f"https://www.themoviedb.org/movie/{tmdb_id}",
                }
        except Exception as e:
            print(f"TMDB fallback error: {e}")

    if not info and sugg:
        img = (sugg.get("i") or {}).get("imageUrl")
        info = {
            "title": sugg.get("l") or movie_name,
            "year": str(sugg.get("y") or year or ""),
            "type": "Movie",
            "runtime": "N/A",
            "language": "N/A",
            "rating": "N/A",
            "genres": "N/A",
            "poster": re.sub(r"\._V1_.*?\.", "._V1_SX1000.", img) if img else None,
            "imdb_id": sugg.get("id"),
            "url": f"https://www.imdb.com/title/{sugg.get('id')}",
        }

    if info and info.get("imdb_id"):
        info["poster_alt"] = imdb_poster_by_id(info["imdb_id"])
    return info


# ============================================================
# OMDb DETAILS
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

            sugg_poster = None
            sugg_item = None
            if not selected:
                # Fallback: IMDb suggestion API (finds spelling variants OMDb search misses)
                try:
                    key = re.sub(r"[^a-z0-9 ]+", "", movie_name.lower()).strip().replace(" ", "_") or "x"
                    sugg = fetch_json(f"https://v3.sg.media-imdb.com/suggestion/x/{urllib.parse.quote(key)}.json")
                    items = [d for d in sugg.get("d", []) if str(d.get("id", "")).startswith("tt")]
                    if year:
                        items = sorted(items, key=lambda d: str(d.get("y")) != str(year))
                    if items:
                        selected = {"imdbID": items[0]["id"]}
                        sugg_item = items[0]
                        sugg_poster = (items[0].get("i") or {}).get("imageUrl")
                except Exception as e:
                    print(f"IMDb suggestion error: {e}")

            if not selected:
                return fallback_details(movie_name, year)

            imdb_id = selected.get("imdbID")
            if not imdb_id:
                return fallback_details(movie_name, year)

            detail_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={urllib.parse.quote(imdb_id)}&plot=full"
            details = fetch_json(detail_url)

            if details.get("Response") != "True":
                return fallback_details(movie_name, year, imdb_id, sugg_item)

            title = details.get("Title", movie_name)
            movie_year = details.get("Year", year or "")
            rating = details.get("imdbRating", "N/A")
            genres = details.get("Genre", "N/A")
            runtime = details.get("Runtime", "N/A")
            language = details.get("Language", "Malayalam")
            m_type = details.get("Type", "Movie").capitalize()
            poster = details.get("Poster")

            if poster and poster != "N/A":
                poster = re.sub(r"\._V1_.*?\.", "._V1_SX1000.", poster)  # 1000px, full-res RAM കൂട്ടും
            else:
                poster = sugg_poster

            return {
                "title": title,
                "year": movie_year,
                "type": m_type,
                "runtime": runtime,
                "language": language,
                "rating": rating,
                "genres": genres,
                "poster": poster,
                "poster_alt": imdb_poster_by_id(imdb_id),
                "imdb_id": imdb_id,
                "url": f"https://www.imdb.com/title/{imdb_id}"
            }

        except Exception as e:
            print(f"IMDb/OMDb Error: {e}")
            try:
                return fallback_details(movie_name, year)
            except Exception:
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

            from io import BytesIO
            out_temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            out_temp.close()

            with Image.open(BytesIO(data)) as src:
                src.draft("RGB", (1000, 1500))      # വലിയ JPEG RAM-ൽ ചെറുതായി തുറക്കും
                img = src.convert("RGB")
            del data
            img.thumbnail((1000, 1500), Image.Resampling.LANCZOS)

            if os.path.exists(LOGO_PATH):
                with Image.open(LOGO_PATH) as lg:
                    logo = lg.convert("RGBA")
                logo_width = int(img.width * 0.22)
                logo_height = int(logo.height * (logo_width / logo.width))
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                img.paste(logo, (int(img.width * 0.04), int(img.height * 0.03)), logo)
                logo.close()

            img.save(out_temp.name, "JPEG", quality=92, optimize=True)
            img.close()
            import gc; gc.collect()
            return out_temp.name
        except Exception as e:
            print(f"Logo processing error: {e}")
            return None

    return await loop.run_in_executor(None, process)


# ============================================================
# CAPTION & BUTTON FORMAT
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
        search_query = f"{title} {year}".strip()
    else:
        caption = (
            f"▫ <b>Title:</b> {movie_title}\n"
            f"▫ <b>Type:</b> Movie\n\n"
            f"<i>Click the button below to search files...!</i>"
        )
        search_query = movie_title

    # Base64 URL-safe encoding vazhi space issue solve cheyyunnu
    encoded_str = base64.urlsafe_b64encode(search_query.encode()).decode().rstrip("=")
    start_link = f"https://t.me/{bot_username}?start=search_{encoded_str}"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Click to Search Files", url=start_link)
            ],
            [
                InlineKeyboardButton("👤 Admin", url=ADMIN_LINK),
                InlineKeyboardButton("👥 Group", url=SUPPORT_GROUP_LINK)
            ]
        ]
    )

    return caption, buttons


# ============================================================
# AUTO POST HANDLER
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
    title_key = "t_" + norm_key(base_title) if norm_key(base_title) not in ("", "movie") else None

    async with LOCK:
        # Same movie, different quality files -> post only once
        if await already_posted(title_key):
            return

        imdb_info = await get_imdb_details(base_title, year)
        imdb_key = imdb_info.get("imdb_id") if imdb_info else None
        if imdb_key and await already_posted(imdb_key):
            await mark_posted(None, title_key)
            return
        caption, buttons = get_caption_and_buttons(base_title, imdb_info)

        candidates = []
        if imdb_info:
            candidates += [imdb_info.get("poster"), imdb_info.get("poster_alt")]
        if PICS:
            candidates.append(random.choice(PICS))
        candidates = [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]

        raw_poster_url = None
        processed_poster = None
        for cand in candidates:
            processed_poster = await prepare_hd_poster_with_logo(cand)
            if processed_poster:
                raw_poster_url = cand
                break
        if not raw_poster_url and candidates:
            raw_poster_url = candidates[-1]

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

        await mark_posted(sent_msg.id, title_key, imdb_key)

        if processed_poster and os.path.exists(processed_poster):
            try:
                os.remove(processed_poster)
            except Exception:
                pass
