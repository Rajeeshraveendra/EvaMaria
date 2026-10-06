import re
import asyncio
import os
import random
import json
import urllib.request
import urllib.parse
import tempfile

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS
from database.ia_filterdb import save_file

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# CONFIG
# ============================================================

UPDATE_CHANNEL = int(
    os.environ.get("UPDATE_CHANNEL", "-1003799495012")
)

LOGO_PATH = "assets/rrk_logo.png"

POST_CACHE = {}
LOCK = asyncio.Lock()

POST_WIDTH = 1080
POST_HEIGHT = 1350


# ============================================================
# FONT
# ============================================================

def get_font(size, bold=False):
    """
    Try common Linux/Railway fonts.
    """

    font_paths = []

    if bold:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = str(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def shorten_text(text, max_chars=260):
    text = clean_text(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def extract_movie_info(filename):

    name = os.path.basename(filename)

    # Remove extension
    name = re.sub(
        r"\.[a-zA-Z0-9]{2,5}$",
        "",
        name
    )

    # Remove brackets
    name = re.sub(r"\[.*?\]", " ", name)
    name = re.sub(r"\(.*?\)", " ", name)

    # Remove channel tags
    name = re.sub(r"@\w+[_]?", " ", name)

    # Replace separators
    name = (
        name.replace(".", " ")
        .replace("_", " ")
        .replace("-", " ")
    )

    name = re.sub(r"\s+", " ", name).strip()

    # Find year
    year_match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        name
    )

    year = year_match.group(1) if year_match else None

    # Tags
    tags = [
        "hindi",
        "tamil",
        "telugu",
        "malayalam",
        "kannada",
        "english",
        "bengali",

        "hdrip",
        "web-dl",
        "webdl",
        "webrip",
        "bluray",
        "brrip",
        "dvdrip",
        "hdts",
        "camrip",
        "hdtc",

        "hevc",
        "x264",
        "x265",

        "720p",
        "1080p",
        "2160p",
        "4k",
        "480p",

        "aac",
        "dd",
        "ddp",
        "dd5",
        "5.1",

        "esub",
        "subs",
        "sub",
        "mkv",
        "mp4",

        "sps",
        "wmr",
        "proper",
        "repack",

        "amzn",
        "amazon",
        "netflix",
        "nfx",
        "hotstar",
        "disney",
        "zee5",
        "sonyliv",
        "aha",
        "jio",
    ]

    clean_words = []

    for word in name.split():

        lower = word.lower()

        if year and word == year:
            break

        if any(
            lower == tag or lower.startswith(tag)
            for tag in tags
        ):
            break

        clean_words.append(word)

    title = " ".join(clean_words).strip()

    if not title:
        title = name.split()[0] if name.split() else "Movie"

    return title, year


# ============================================================
# QUALITY / OTT EXTRACTION
# ============================================================

def extract_quality_details(filename):

    text = filename.lower()

    quality = []

    quality_patterns = [
        (r"2160p|4k", "4K"),
        (r"1080p", "1080p"),
        (r"720p", "720p"),
        (r"480p", "480p"),
    ]

    for pattern, label in quality_patterns:
        if re.search(pattern, text):
            quality.append(label)

    # Video source
    sources = [
        (r"web[-_. ]?dl", "WEB-DL"),
        (r"web[-_. ]?rip", "WEBRip"),
        (r"bluray|blu[-_. ]?ray", "BluRay"),
        (r"brrip", "BRRip"),
        (r"hdrip", "HDRip"),
        (r"dvdrip", "DVDRip"),
        (r"hdts", "HDTS"),
        (r"hdtc", "HDTC"),
        (r"camrip|cam", "CAM"),
    ]

    source = None

    for pattern, label in sources:
        if re.search(pattern, text):
            source = label
            break

    # Codec
    codec = None

    if re.search(r"x265|hevc", text):
        codec = "HEVC / x265"
    elif re.search(r"x264", text):
        codec = "x264"

    # Audio
    audio = []

    if re.search(r"ddp|eac3", text):
        audio.append("DDP")

    if re.search(r"dd5\.1|dd 5\.1|5\.1", text):
        audio.append("5.1")

    if re.search(r"aac", text):
        audio.append("AAC")

    # OTT
    ott = None

    ott_patterns = [
        (r"netflix|nfx", "Netflix"),
        (r"amazon|amzn", "Amazon Prime"),
        (r"hotstar", "Disney+ Hotstar"),
        (r"disney", "Disney+"),
        (r"zee5", "ZEE5"),
        (r"sonyliv", "SonyLIV"),
        (r"jio", "JioCinema"),
        (r"aha", "Aha"),
    ]

    for pattern, label in ott_patterns:
        if re.search(pattern, text):
            ott = label
            break

    parts = []

    if quality:
        parts.append(" / ".join(dict.fromkeys(quality)))

    if source:
        parts.append(source)

    if codec:
        parts.append(codec)

    if audio:
        parts.append(" ".join(dict.fromkeys(audio)))

    return {
        "quality": " • ".join(parts) if parts else "HD",
        "ott": ott or "OTT / Digital",
    }


# ============================================================
# IMDb
# ============================================================

async def get_imdb_details(movie_name, year=None):

    loop = asyncio.get_event_loop()

    def fetch():

        try:

            q = urllib.parse.quote(movie_name)

            url = (
                "https://www.omdbapi.com/"
                f"?t={q}"
                f"&y={year or ''}"
                "&apikey=b6636080"
            )

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=8
            ) as response:

                data = json.loads(
                    response.read().decode()
                )

            # Fallback without year
            if data.get("Response") != "True":

                fallback_url = (
                    "https://www.omdbapi.com/"
                    f"?t={q}"
                    "&apikey=b6636080"
                )

                req2 = urllib.request.Request(
                    fallback_url,
                    headers={
                        "User-Agent": "Mozilla/5.0"
                    }
                )

                with urllib.request.urlopen(
                    req2,
                    timeout=8
                ) as response:

                    data = json.loads(
                        response.read().decode()
                    )

            if data.get("Response") != "True":
                return None

            title = data.get(
                "Title",
                movie_name
            )

            movie_year = data.get(
                "Year",
                year or ""
            )

            rating = data.get(
                "imdbRating",
                "N/A"
            )

            genres = data.get(
                "Genre",
                "N/A"
            )

            story = data.get(
                "Plot",
                "No storyline available."
            )

            poster = data.get("Poster")

            if poster == "N/A":
                poster = None

            return {
                "title": title,
                "year": movie_year,
                "display_title": (
                    f"{title} ({movie_year})"
                    if movie_year
                    else title
                ),
                "search_title": title,
                "rating": rating,
                "genres": genres,
                "story": story,
                "poster": poster,
            }

        except Exception as e:

            print(
                f"IMDb API Error: {e}"
            )

            return None

    return await loop.run_in_executor(
        None,
        fetch
    )


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

async def download_image(url):

    if not url:
        return None

    loop = asyncio.get_event_loop()

    def fetch():

        try:

            temp = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            )

            temp.close()

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=12
            ) as response:

                data = response.read()

            with open(
                temp.name,
                "wb"
            ) as f:

                f.write(data)

            return temp.name

        except Exception as e:

            print(
                f"Poster download error: {e}"
            )

            return None

    return await loop.run_in_executor(
        None,
        fetch
    )


# ============================================================
# LOGO
# ============================================================

def load_logo():

    if not os.path.exists(LOGO_PATH):
        print(
            f"RRK logo not found: {LOGO_PATH}"
        )
        return None

    try:

        logo = Image.open(
            LOGO_PATH
        ).convert("RGBA")

        # Keep original ratio
        max_width = 250
        max_height = 100

        logo.thumbnail(
            (max_width, max_height),
            Image.Resampling.LANCZOS
        )

        return logo

    except Exception as e:

        print(
            f"Logo loading error: {e}"
        )

        return None


# ============================================================
# CREATE PROFESSIONAL POSTER
# ============================================================

def create_professional_poster(
    poster_path,
    imdb_info,
    quality_info,
    output_path
):

    try:

        canvas = Image.new(
            "RGB",
            (POST_WIDTH, POST_HEIGHT),
            (12, 12, 12)
        )

        # ----------------------------------------------------
        # Poster
        # ----------------------------------------------------

        if poster_path and os.path.exists(
            poster_path
        ):

            poster = Image.open(
                poster_path
            ).convert("RGB")

            # Crop/fill canvas
            poster_ratio = (
                poster.width / poster.height
            )

            target_ratio = (
                POST_WIDTH / POST_HEIGHT
            )

            if poster_ratio > target_ratio:

                new_height = POST_HEIGHT

                new_width = int(
                    new_height * poster_ratio
                )

            else:

                new_width = POST_WIDTH

                new_height = int(
                    new_width / poster_ratio
                )

            poster = poster.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            left = (
                new_width - POST_WIDTH
            ) // 2

            top = (
                new_height - POST_HEIGHT
            ) // 2

            poster = poster.crop(
                (
                    left,
                    top,
                    left + POST_WIDTH,
                    top + POST_HEIGHT
                )
            )

            # Dark overlay
            overlay = Image.new(
                "RGBA",
                canvas.size,
                (0, 0, 0, 0)
            )

            draw_overlay = ImageDraw.Draw(
                overlay
            )

            draw_overlay.rectangle(
                (
                    0,
                    0,
                    POST_WIDTH,
                    POST_HEIGHT
                ),
                fill=(0, 0, 0, 80)
            )

            # Bottom gradient-ish dark blocks
            draw_overlay.rectangle(
                (
                    0,
                    850,
                    POST_WIDTH,
                    POST_HEIGHT
                ),
                fill=(0, 0, 0, 185)
            )

            poster = Image.alpha_composite(
                poster.convert("RGBA"),
                overlay
            ).convert("RGB")

            canvas.paste(
                poster,
                (0, 0)
            )

        # ----------------------------------------------------
        # Drawing
        # ----------------------------------------------------

        draw = ImageDraw.Draw(
            canvas
        )

        title_font = get_font(
            66,
            bold=True
        )

        year_font = get_font(
            34,
            bold=True
        )

        normal_font = get_font(
            30,
            bold=False
        )

        small_font = get_font(
            25,
            bold=True
        )

        # ----------------------------------------------------
        # RRK LOGO
        # ----------------------------------------------------

        logo = load_logo()

        if logo:

            logo_x = 55
            logo_y = 45

            # Slight translucent background
            logo_bg = Image.new(
                "RGBA",
                (
                    logo.width + 30,
                    logo.height + 20
                ),
                (0, 0, 0, 130)
            )

            canvas.paste(
                logo_bg,
                (
                    logo_x - 15,
                    logo_y - 10
                ),
                logo_bg
            )

            canvas.paste(
                logo,
                (
                    logo_x,
                    logo_y
                ),
                logo
            )

        # ----------------------------------------------------
        # Bottom title area
        # ----------------------------------------------------

        title = imdb_info.get(
            "title",
            "Movie"
        )

        # Maximum title length
        if len(title) > 30:
            title = title[:30].rsplit(
                " ",
                1
            )[0] + "..."

        # Draw title
        title_y = 885

        draw.text(
            (55, title_y),
            title,
            font=title_font,
            fill="white",
            stroke_width=2,
            stroke_fill="black"
        )

        # Year
        movie_year = imdb_info.get(
            "year",
            ""
        )

        if movie_year:

            draw.text(
                (
                    58,
                    title_y + 82
                ),
                f"RELEASED • {movie_year}",
                font=year_font,
                fill="white"
            )

        # ----------------------------------------------------
        # Rating / Genre
        # ----------------------------------------------------

        rating = imdb_info.get(
            "rating",
            "N/A"
        )

        genres = imdb_info.get(
            "genres",
            "N/A"
        )

        info_y = 1010

        draw.text(
            (58, info_y),
            f"⭐ IMDb {rating}/10",
            font=normal_font,
            fill="white"
        )

        draw.text(
            (
                58,
                info_y + 50
            ),
            f"🎭 {genres}",
            font=normal_font,
            fill="white"
        )

        # ----------------------------------------------------
        # Quality
        # ----------------------------------------------------

        quality = quality_info.get(
            "quality",
            "HD"
        )

        ott = quality_info.get(
            "ott",
            "OTT / Digital"
        )

        quality_y = 1135

        draw.text(
            (
                58,
                quality_y
            ),
            f"🎞 {quality}",
            font=small_font,
            fill="white"
        )

        draw.text(
            (
                58,
                quality_y + 48
            ),
            f"📺 {ott}",
            font=small_font,
            fill="white"
        )

        # ----------------------------------------------------
        # Bottom RRK branding
        # ----------------------------------------------------

        brand_font = get_font(
            26,
            bold=True
        )

        brand_text = "RRK MOVIES • OFFICIAL"

        bbox = draw.textbbox(
            (0, 0),
            brand_text,
            font=brand_font
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        draw.text(
            (
                POST_WIDTH - text_width - 55,
                POST_HEIGHT - 55
            ),
            brand_text,
            font=brand_font,
            fill="white"
        )

        # Save HD
        canvas.save(
            output_path,
            "JPEG",
            quality=95,
            optimize=True
        )

        return True

    except Exception as e:

        print(
            f"Poster generation error: {e}"
        )

        return False


# ============================================================
# CAPTION + BUTTON
# ============================================================

def get_caption_and_buttons(
    movie_title,
    entries,
    imdb_info=None
):

    files_text = "\n".join(
        entries
    )

    if imdb_info:

        caption = (
            f"🎬 <b>{imdb_info['display_title']}</b>\n\n"

            f"⭐ <b>IMDb Rating :</b> "
            f"{imdb_info['rating']}/10\n"

            f"🎭 <b>Genre :</b> "
            f"{imdb_info['genres']}\n"

            f"📅 <b>Release :</b> "
            f"{imdb_info['year']}\n\n"

            f"📖 <b>Storyline :</b>\n"
            f"<i>{imdb_info['story']}</i>\n\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"

            f"🎞 <b>Available Files</b>\n"
            f"{files_text}\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"

            f"📌 <b>Released & Verified</b> ✅"
        )

        search_keyword = imdb_info.get(
            "search_title",
            movie_title
        )

    else:

        caption = (
            f"🎬 <b>{movie_title}</b>\n\n"

            f"🎞 <b>Available Files</b>\n"
            f"{files_text}\n\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Released & Verified</b> ✅\n"
            f"🔎 <b>Search & Download</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        search_keyword = movie_title

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📥  DOWNLOAD MOVIE  📥",
                    switch_inline_query_current_chat=search_keyword
                )
            ]
        ]
    )

    return caption, buttons


# ============================================================
# 1. PRIVATE FILE SAVE
# ============================================================

@Client.on_message(
    filters.private &
    (filters.document | filters.video)
)
async def save_direct_files(
    client,
    message
):

    media = (
        message.document
        or message.video
    )

    if not media:
        return

    if not hasattr(
        media,
        "file_type"
    ):
        media.file_type = (
            "video"
            if message.video
            else "document"
        )

    if not hasattr(
        media,
        "caption"
    ):
        media.caption = None

    try:

        saved = await save_file(
            media
        )

        is_success = (
            saved[0]
            if isinstance(
                saved,
                tuple
            )
            else saved
        )

        file_name = getattr(
            media,
            "file_name",
            "Unknown File"
        )

        if is_success:

            await message.reply_text(
                "✅ <b>Database-il save cheythu!</b>\n\n"
                f"📁 <code>{file_name}</code>",
                quote=True
            )

        else:

            await message.reply_text(
                "ℹ️ <b>File already database-il undu:</b>\n\n"
                f"📁 <code>{file_name}</code>",
                quote=True
            )

    except Exception as e:

        await message.reply_text(
            "⚠️ <b>Save cheyyan kazhinjilla:</b>\n"
            f"<code>{e}</code>",
            quote=True
        )


# ============================================================
# 2. CHANNEL AUTO POST
# ============================================================

@Client.on_message(
    filters.chat(CHANNELS) &
    (filters.document | filters.video)
)
async def auto_post_to_group(
    client,
    message
):

    media = (
        message.document
        or message.video
    )

    if not media:
        return

    # --------------------------------------------------------
    # Save to database
    # --------------------------------------------------------

    try:

        if not hasattr(
            media,
            "file_type"
        ):
            media.file_type = (
                "video"
                if message.video
                else "document"
            )

        if not hasattr(
            media,
            "caption"
        ):
            media.caption = None

        await save_file(
            media
        )

    except Exception as err:

        print(
            f"Channel DB Save Error: {err}"
        )

    if not UPDATE_CHANNEL:
        return

    # --------------------------------------------------------
    # Movie information
    # --------------------------------------------------------

    file_name = getattr(
        media,
        "file_name",
        "New Movie"
    )

    base_title, year = extract_movie_info(
        file_name
    )

    quality_info = extract_quality_details(
        file_name
    )

    line_entry = (
        f"🎬 <code>{file_name}</code>"
    )

    cache_key = (
        f"{base_title.lower()}_{year}"
        if year
        else base_title.lower()
    )

    # --------------------------------------------------------
    # Lock
    # --------------------------------------------------------

    async with LOCK:

        # ====================================================
        # EXISTING MOVIE
        # ====================================================

        if cache_key in POST_CACHE:

            data = POST_CACHE[
                cache_key
            ]

            if line_entry not in data["entries"]:

                data["entries"].append(
                    line_entry
                )

                caption, buttons = (
                    get_caption_and_buttons(
                        base_title,
                        data["entries"],
                        data.get(
                            "imdb_info"
                        )
                    )
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

                    print(
                        f"Edit Caption Error: {e}"
                    )

            return

        # ====================================================
        # NEW MOVIE
        # ====================================================

        imdb_info = await get_imdb_details(
            base_title,
            year
        )

        entries = [
            line_entry
        ]

        caption, buttons = (
            get_caption_and_buttons(
                base_title,
                entries,
                imdb_info
            )
        )

        # ----------------------------------------------------
        # Get poster
        # ----------------------------------------------------

        poster_url = None

        if imdb_info:

            poster_url = imdb_info.get(
                "poster"
            )

        poster_source = (
            await download_image(
                poster_url
            )
            if poster_url
            else None
        )

        # ----------------------------------------------------
        # Fallback poster
        # ----------------------------------------------------

        if not poster_source and PICS:

            try:

                fallback_url = random.choice(
                    PICS
                )

                poster_source = (
                    await download_image(
                        fallback_url
                    )
                )

            except Exception as e:

                print(
                    f"Fallback poster error: {e}"
                )

        # ----------------------------------------------------
        # Generate professional poster
        # ----------------------------------------------------

        generated_poster = None

        if poster_source:

            try:

                temp_file = tempfile.NamedTemporaryFile(
                    suffix=".jpg",
                    delete=False
                )

                generated_poster = (
                    temp_file.name
                )

                temp_file.close()

                if not imdb_info:

                    imdb_info = {
                        "title": base_title,
                        "year": year or "",
                        "display_title": (
                            f"{base_title} ({year})"
                            if year
                            else base_title
                        ),
                        "search_title": base_title,
                        "rating": "N/A",
                        "genres": "N/A",
                        "story": (
                            "No storyline available."
                        ),
                        "poster": poster_url,
                    }

                created = (
                    create_professional_poster(
                        poster_source,
                        imdb_info,
                        quality_info,
                        generated_poster
                    )
                )

                if not created:

                    generated_poster = None

            except Exception as e:

                print(
                    f"Poster creation error: {e}"
                )

        # ----------------------------------------------------
        # Send
        # ----------------------------------------------------

        sent_msg = None

        if generated_poster and os.path.exists(
            generated_poster
        ):

            try:

                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=generated_poster,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )

            except Exception as err:

                print(
                    f"Generated poster send error: {err}"
                )

        # ----------------------------------------------------
        # If generated poster failed
        # ----------------------------------------------------

        if not sent_msg and poster_source:

            try:

                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=poster_source,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )

            except Exception as err:

                print(
                    f"Original poster send error: {err}"
                )

        # ----------------------------------------------------
        # Text fallback
        # ----------------------------------------------------

        if not sent_msg:

            try:

                sent_msg = await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )

            except Exception as err:

                print(
                    f"Text post error: {err}"
                )

                return

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

        POST_CACHE[
            cache_key
        ] = {
            "msg_id": sent_msg.id,
            "entries": entries,
            "imdb_info": imdb_info,
            "quality_info": quality_info
        }

        # ----------------------------------------------------
        # Cleanup temporary files
        # ----------------------------------------------------

        for temp_file in [
            poster_source,
            generated_poster
        ]:

            if temp_file:

                try:

                    if os.path.exists(
                        temp_file
                    ):
                        os.remove(
                            temp_file
                        )

                except Exception:
                    pass
