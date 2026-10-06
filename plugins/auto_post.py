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

from PIL import Image, ImageDraw, ImageFont


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
    "b6636080"
)

LOGO_PATH = "assets/rrk_logo.png"

POST_CACHE = {}

LOCK = asyncio.Lock()

POST_WIDTH = 1080
POST_HEIGHT = 1350


# ============================================================
# FONTS
# ============================================================

def get_font(size, bold=False):

    if bold:

        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]

    else:

        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in paths:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


# ============================================================
# BASIC TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace(
        "\n",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# MOVIE TITLE EXTRACTION
# ============================================================

def extract_movie_info(filename):

    """
    Example:

    DVDWO_Vadakkumnadhan2006_Malayalam_HQ_HD_TVRip_720p_X264_AAC_1_7GB.mp4

    Returns:

    Vadakkumnadhan
    2006
    """

    name = os.path.basename(
        filename
    )

    # --------------------------------------------------------
    # Remove extension
    # --------------------------------------------------------

    name = re.sub(
        r"\.[A-Za-z0-9]{2,5}$",
        "",
        name
    )

    # --------------------------------------------------------
    # Remove [tags] and (tags)
    # --------------------------------------------------------

    name = re.sub(
        r"\[[^\]]*\]",
        " ",
        name
    )

    name = re.sub(
        r"\([^)]*\)",
        " ",
        name
    )

    # --------------------------------------------------------
    # Remove Telegram/channel tags
    # --------------------------------------------------------

    name = re.sub(
        r"@\w+",
        " ",
        name
    )

    # --------------------------------------------------------
    # Normalize separators
    # --------------------------------------------------------

    name = (
        name
        .replace("_", " ")
        .replace(".", " ")
        .replace("-", " ")
    )

    # --------------------------------------------------------
    # Separate letters and numbers
    #
    # Vadakkumnadhan2006
    # ->
    # Vadakkumnadhan 2006
    # --------------------------------------------------------

    name = re.sub(
        r"([A-Za-z])(\d{4})",
        r"\1 \2",
        name
    )

    name = re.sub(
        r"(\d{4})([A-Za-z])",
        r"\1 \2",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    # --------------------------------------------------------
    # Find year
    # --------------------------------------------------------

    year_match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        name
    )

    year = (
        year_match.group(1)
        if year_match
        else None
    )

    # --------------------------------------------------------
    # Words that indicate filename metadata
    # --------------------------------------------------------

    stop_words = {
        "hindi",
        "tamil",
        "telugu",
        "malayalam",
        "kannada",
        "english",
        "bengali",
        "marathi",

        "hq",
        "hd",
        "fullhd",

        "hdrip",
        "webdl",
        "web-dl",
        "web",
        "webrip",
        "web-rip",

        "bluray",
        "blu-ray",
        "brrip",
        "dvdrip",
        "dvd",

        "tvrip",
        "tv-rip",

        "hdts",
        "hdtc",
        "cam",
        "camrip",

        "hevc",
        "x264",
        "x265",

        "480p",
        "720p",
        "1080p",
        "2160p",
        "4k",

        "aac",
        "dd",
        "ddp",
        "eac3",
        "ac3",
        "5.1",

        "esub",
        "subs",
        "subtitle",
        "subtitles",

        "mkv",
        "mp4",
        "avi",

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

        "gb",
        "mb",

        "dvdwo",
        "wmr",
        "sps",
    }

    # --------------------------------------------------------
    # Clean title words
    # --------------------------------------------------------

    title_words = []

    for word in name.split():

        lower = word.lower()

        # Year marks end of movie title
        if year and word == year:
            break

        # Remove numeric size values
        if re.fullmatch(
            r"\d+(?:\.\d+)?(?:gb|mb)",
            lower
        ):
            break

        # Stop at known release metadata
        if lower in stop_words:
            break

        # Ignore standalone numbers
        if re.fullmatch(
            r"\d+",
            lower
        ):
            continue

        title_words.append(
            word
        )

    title = " ".join(
        title_words
    ).strip()

    # --------------------------------------------------------
    # Remove leading junk tags
    # --------------------------------------------------------

    title = re.sub(
        r"^(dvdwo|wmr|sps)\s+",
        "",
        title,
        flags=re.IGNORECASE
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not title:

        title = "Movie"

    return title, year


# ============================================================
# QUALITY / SOURCE EXTRACTION
# ============================================================

def extract_quality_details(filename):

    text = filename.lower()

    qualities = []

    if re.search(
        r"2160p|4k",
        text
    ):
        qualities.append(
            "4K"
        )

    elif re.search(
        r"1080p",
        text
    ):
        qualities.append(
            "1080p"
        )

    elif re.search(
        r"720p",
        text
    ):
        qualities.append(
            "720p"
        )

    elif re.search(
        r"480p",
        text
    ):
        qualities.append(
            "480p"
        )

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    source = None

    source_patterns = [
        (
            r"web[-_. ]?dl",
            "WEB-DL"
        ),
        (
            r"web[-_. ]?rip",
            "WEBRip"
        ),
        (
            r"bluray|blu[-_. ]?ray",
            "BluRay"
        ),
        (
            r"brrip",
            "BRRip"
        ),
        (
            r"hdrip",
            "HDRip"
        ),
        (
            r"tvrip|tv[-_. ]?rip",
            "TVRip"
        ),
        (
            r"dvdrip",
            "DVDRip"
        ),
        (
            r"hdts",
            "HDTS"
        ),
        (
            r"hdtc",
            "HDTC"
        ),
        (
            r"camrip|cam",
            "CAM"
        ),
    ]

    for pattern, label in source_patterns:

        if re.search(
            pattern,
            text
        ):

            source = label
            break

    # --------------------------------------------------------
    # Codec
    # --------------------------------------------------------

    codec = None

    if re.search(
        r"x265|hevc",
        text
    ):

        codec = "HEVC / x265"

    elif re.search(
        r"x264",
        text
    ):

        codec = "x264"

    # --------------------------------------------------------
    # Audio
    # --------------------------------------------------------

    audio = []

    if re.search(
        r"eac3|ddp",
        text
    ):

        audio.append(
            "DDP"
        )

    elif re.search(
        r"ac3|dd",
        text
    ):

        audio.append(
            "DD"
        )

    if re.search(
        r"5[._ ]?1",
        text
    ):

        audio.append(
            "5.1"
        )

    if re.search(
        r"aac",
        text
    ):

        audio.append(
            "AAC"
        )

    # --------------------------------------------------------
    # OTT
    # --------------------------------------------------------

    ott = None

    ott_patterns = [
        (
            r"netflix|nfx",
            "Netflix"
        ),
        (
            r"amazon|amzn",
            "Amazon Prime"
        ),
        (
            r"hotstar",
            "Disney+ Hotstar"
        ),
        (
            r"disney",
            "Disney+"
        ),
        (
            r"zee5",
            "ZEE5"
        ),
        (
            r"sonyliv",
            "SonyLIV"
        ),
        (
            r"jio",
            "JioCinema"
        ),
        (
            r"aha",
            "Aha"
        ),
    ]

    for pattern, label in ott_patterns:

        if re.search(
            pattern,
            text
        ):

            ott = label
            break

    parts = []

    if qualities:
        parts.extend(
            list(dict.fromkeys(qualities))
        )

    if source:
        parts.append(
            source
        )

    if codec:
        parts.append(
            codec
        )

    if audio:
        parts.extend(
            list(dict.fromkeys(audio))
        )

    return {
        "quality": (
            " • ".join(parts)
            if parts
            else "HD"
        ),
        "ott": (
            ott
            if ott
            else "Digital"
        )
    }


# ============================================================
# HTTP JSON HELPER
# ============================================================

def fetch_json(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=10
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


# ============================================================
# IMDb / OMDb SEARCH
# ============================================================

async def get_imdb_details(
    movie_name,
    year=None
):

    loop = asyncio.get_event_loop()

    def fetch():

        try:

            # =================================================
            # SEARCH 1
            # =================================================

            query = urllib.parse.quote(
                movie_name
            )

            search_url = (
                "https://www.omdbapi.com/"
                f"?apikey={OMDB_API_KEY}"
                f"&s={query}"
                "&type=movie"
            )

            if year:
                search_url += (
                    f"&y={year}"
                )

            search_data = fetch_json(
                search_url
            )

            # =================================================
            # SEARCH RESULTS
            # =================================================

            results = search_data.get(
                "Search",
                []
            )

            selected = None

            # Exact normalized title
            wanted = re.sub(
                r"[^a-z0-9]+",
                "",
                movie_name.lower()
            )

            for item in results:

                item_title = item.get(
                    "Title",
                    ""
                )

                normalized = re.sub(
                    r"[^a-z0-9]+",
                    "",
                    item_title.lower()
                )

                item_year = str(
                    item.get(
                        "Year",
                        ""
                    )
                )

                # Exact title + year
                if (
                    normalized == wanted
                    and (
                        not year
                        or item_year.startswith(
                            str(year)
                        )
                    )
                ):

                    selected = item
                    break

            # =================================================
            # Year match
            # =================================================

            if not selected and year:

                for item in results:

                    item_year = str(
                        item.get(
                            "Year",
                            ""
                        )
                    )

                    if item_year.startswith(
                        str(year)
                    ):

                        selected = item
                        break

            # =================================================
            # First movie fallback
            # =================================================

            if not selected and results:

                selected = results[0]

            # =================================================
            # Search without year if necessary
            # =================================================

            if not selected:

                fallback_url = (
                    "https://www.omdbapi.com/"
                    f"?apikey={OMDB_API_KEY}"
                    f"&s={query}"
                    "&type=movie"
                )

                fallback_data = fetch_json(
                    fallback_url
                )

                fallback_results = (
                    fallback_data.get(
                        "Search",
                        []
                    )
                )

                if fallback_results:

                    selected = fallback_results[0]

            if not selected:

                print(
                    f"IMDb search failed: "
                    f"{movie_name} {year}"
                )

                return None

            imdb_id = selected.get(
                "imdbID"
            )

            if not imdb_id:
                return None

            # =================================================
            # Get FULL IMDb details
            # =================================================

            detail_url = (
                "https://www.omdbapi.com/"
                f"?apikey={OMDB_API_KEY}"
                f"&i={urllib.parse.quote(imdb_id)}"
                "&plot=full"
            )

            details = fetch_json(
                detail_url
            )

            if details.get(
                "Response"
            ) != "True":

                return None

            title = details.get(
                "Title",
                movie_name
            )

            movie_year = details.get(
                "Year",
                year or ""
            )

            rating = details.get(
                "imdbRating",
                "N/A"
            )

            genres = details.get(
                "Genre",
                "N/A"
            )

            story = details.get(
                "Plot",
                "No storyline available."
            )

            poster = details.get(
                "Poster"
            )

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
                "imdb_id": imdb_id
            }

        except Exception as e:

            print(
                f"IMDb/OMDb Error: {e}"
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

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent":
                    "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=15
            ) as response:

                data = response.read()

            with open(
                temp.name,
                "wb"
            ) as file:

                file.write(data)

            return temp.name

        except Exception as e:

            print(
                f"Image download error: {e}"
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

    if not os.path.exists(
        LOGO_PATH
    ):

        print(
            f"Logo not found: {LOGO_PATH}"
        )

        return None

    try:

        logo = Image.open(
            LOGO_PATH
        ).convert(
            "RGBA"
        )

        logo.thumbnail(
            (240, 100),
            Image.Resampling.LANCZOS
        )

        return logo

    except Exception as e:

        print(
            f"Logo error: {e}"
        )

        return None


# ============================================================
# PROFESSIONAL POSTER
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
            (
                POST_WIDTH,
                POST_HEIGHT
            ),
            (12, 12, 12)
        )

        # ====================================================
        # POSTER IMAGE
        # ====================================================

        if poster_path and os.path.exists(
            poster_path
        ):

            poster = Image.open(
                poster_path
            ).convert(
                "RGB"
            )

            target_ratio = (
                POST_WIDTH /
                POST_HEIGHT
            )

            poster_ratio = (
                poster.width /
                poster.height
            )

            if poster_ratio > target_ratio:

                new_height = POST_HEIGHT

                new_width = int(
                    new_height *
                    poster_ratio
                )

            else:

                new_width = POST_WIDTH

                new_height = int(
                    new_width /
                    poster_ratio
                )

            poster = poster.resize(
                (
                    new_width,
                    new_height
                ),
                Image.Resampling.LANCZOS
            )

            left = (
                new_width -
                POST_WIDTH
            ) // 2

            top = (
                new_height -
                POST_HEIGHT
            ) // 2

            poster = poster.crop(
                (
                    left,
                    top,
                    left + POST_WIDTH,
                    top + POST_HEIGHT
                )
            )

            canvas.paste(
                poster,
                (0, 0)
            )

        # ====================================================
        # DRAW
        # ====================================================

        draw = ImageDraw.Draw(
            canvas
        )

        # Bottom dark area
        draw.rectangle(
            (
                0,
                820,
                POST_WIDTH,
                POST_HEIGHT
            ),
            fill=(0, 0, 0)
        )

        # ====================================================
        # LOGO
        # ====================================================

        logo = load_logo()

        if logo:

            canvas.paste(
                logo,
                (
                    50,
                    40
                ),
                logo
            )

        # ====================================================
        # FONTS
        # ====================================================

        title_font = get_font(
            62,
            True
        )

        year_font = get_font(
            31,
            True
        )

        info_font = get_font(
            28,
            False
        )

        small_font = get_font(
            24,
            True
        )

        # ====================================================
        # TITLE
        # ====================================================

        title = imdb_info.get(
            "title",
            "Movie"
        )

        if len(title) > 30:

            title = (
                title[:30]
                .rsplit(" ", 1)[0]
                + "..."
            )

        draw.text(
            (
                55,
                855
            ),
            title,
            font=title_font,
            fill="white"
        )

        # ====================================================
        # YEAR
        # ====================================================

        year = imdb_info.get(
            "year",
            ""
        )

        if year:

            draw.text(
                (
                    58,
                    935
                ),
                f"RELEASED • {year}",
                font=year_font,
                fill="white"
            )

        # ====================================================
        # RATING
        # ====================================================

        rating = imdb_info.get(
            "rating",
            "N/A"
        )

        draw.text(
            (
                58,
                1000
            ),
            f"⭐ IMDb {rating}/10",
            font=info_font,
            fill="white"
        )

        # ====================================================
        # GENRE
        # ====================================================

        genres = imdb_info.get(
            "genres",
            "N/A"
        )

        if len(genres) > 48:

            genres = (
                genres[:48]
                .rsplit(" ", 1)[0]
                + "..."
            )

        draw.text(
            (
                58,
                1050
            ),
            f"🎭 {genres}",
            font=info_font,
            fill="white"
        )

        # ====================================================
        # QUALITY
        # ====================================================

        quality = quality_info.get(
            "quality",
            "HD"
        )

        draw.text(
            (
                58,
                1110
            ),
            f"🎞 {quality}",
            font=small_font,
            fill="white"
        )

        # ====================================================
        # OTT
        # ====================================================

        ott = quality_info.get(
            "ott",
            "Digital"
        )

        draw.text(
            (
                58,
                1155
            ),
            f"📺 {ott}",
            font=small_font,
            fill="white"
        )

        # ====================================================
        # BRAND
        # ====================================================

        brand = "RRK MOVIES • OFFICIAL"

        bbox = draw.textbbox(
            (0, 0),
            brand,
            font=small_font
        )

        brand_width = (
            bbox[2] -
            bbox[0]
        )

        draw.text(
            (
                POST_WIDTH -
                brand_width -
                50,
                POST_HEIGHT -
                55
            ),
            brand,
            font=small_font,
            fill="white"
        )

        # ====================================================
        # SAVE
        # ====================================================

        canvas.save(
            output_path,
            "JPEG",
            quality=95,
            optimize=True
        )

        return True

    except Exception as e:

        print(
            f"Poster creation error: {e}"
        )

        return False


# ============================================================
# CAPTION
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

            f"📌 <b>Released & Verified</b> ✅\n"
            f"🔎 <b>Search & Download</b>"
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
            f"📌 <b>Released & Verified</b> ✅"
        )

        search_keyword = movie_title

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📥 DOWNLOAD MOVIE 📥",
                    switch_inline_query_current_chat=
                    search_keyword
                )
            ]
        ]
    )

    return (
        caption,
        buttons
    )


# ============================================================
# PRIVATE FILE SAVE
# ============================================================

@Client.on_message(
    filters.private &
    (
        filters.document |
        filters.video
    )
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

        success = (
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

        if success:

            await message.reply_text(
                "✅ <b>Database-il save cheythu!</b>\n\n"
                f"📁 <code>{file_name}</code>",
                quote=True
            )

        else:

            await message.reply_text(
                "ℹ️ <b>File already database-il undu.</b>\n\n"
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
# CHANNEL AUTO POST
# ============================================================

@Client.on_message(
    filters.chat(CHANNELS) &
    (
        filters.document |
        filters.video
    )
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

    # ========================================================
    # SAVE DATABASE
    # ========================================================

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

    except Exception as e:

        print(
            f"Database save error: {e}"
        )

    if not UPDATE_CHANNEL:
        return

    # ========================================================
    # FILE NAME
    # ========================================================

    file_name = getattr(
        media,
        "file_name",
        "New Movie"
    )

    # ========================================================
    # EXTRACT TITLE
    # ========================================================

    base_title, year = (
        extract_movie_info(
            file_name
        )
    )

    print(
        f"[AUTO POST] "
        f"Filename: {file_name}"
    )

    print(
        f"[AUTO POST] "
        f"Title: {base_title}"
    )

    print(
        f"[AUTO POST] "
        f"Year: {year}"
    )

    # ========================================================
    # QUALITY
    # ========================================================

    quality_info = (
        extract_quality_details(
            file_name
        )
    )

    line_entry = (
        f"🎬 <code>{file_name}</code>"
    )

    cache_key = (
        f"{base_title.lower()}_{year}"
        if year
        else base_title.lower()
    )

    # ========================================================
    # LOCK
    # ========================================================

    async with LOCK:

        # ====================================================
        # EXISTING MOVIE
        # ====================================================

        if cache_key in POST_CACHE:

            data = POST_CACHE[
                cache_key
            ]

            if line_entry not in data[
                "entries"
            ]:

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
                        f"Caption update error: {e}"
                    )

            return

        # ====================================================
        # IMDb
        # ====================================================

        imdb_info = await get_imdb_details(
            base_title,
            year
        )

        # ====================================================
        # FALLBACK DATA
        # ====================================================

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
                    "Movie information "
                    "is currently unavailable."
                ),
                "poster": None
            }

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

        # ====================================================
        # POSTER URL
        # ====================================================

        poster_url = imdb_info.get(
            "poster"
        )

        poster_source = None

        if poster_url:

            poster_source = (
                await download_image(
                    poster_url
                )
            )

        # ====================================================
        # FALLBACK PICS
        # ====================================================

        if not poster_source and PICS:

            try:

                fallback_url = (
                    random.choice(PICS)
                )

                poster_source = (
                    await download_image(
                        fallback_url
                    )
                )

            except Exception as e:

                print(
                    f"Fallback image error: {e}"
                )

        # ====================================================
        # CREATE POSTER
        # ====================================================

        generated_poster = None

        if poster_source:

            try:

                temp = tempfile.NamedTemporaryFile(
                    suffix=".jpg",
                    delete=False
                )

                temp.close()

                generated_poster = (
                    temp.name
                )

                success = (
                    create_professional_poster(
                        poster_source,
                        imdb_info,
                        quality_info,
                        generated_poster
                    )
                )

                if not success:

                    generated_poster = None

            except Exception as e:

                print(
                    f"Poster generation error: {e}"
                )

        # ====================================================
        # SEND GENERATED POSTER
        # ====================================================

        sent_msg = None

        if generated_poster:

            try:

                sent_msg = (
                    await client.send_photo(
                        chat_id=UPDATE_CHANNEL,
                        photo=generated_poster,
                        caption=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                )

            except Exception as e:

                print(
                    f"Generated poster send error: {e}"
                )

        # ====================================================
        # ORIGINAL POSTER FALLBACK
        # ====================================================

        if not sent_msg and poster_source:

            try:

                sent_msg = (
                    await client.send_photo(
                        chat_id=UPDATE_CHANNEL,
                        photo=poster_source,
                        caption=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                )

            except Exception as e:

                print(
                    f"Original poster send error: {e}"
                )

        # ====================================================
        # TEXT FALLBACK
        # ====================================================

        if not sent_msg:

            try:

                sent_msg = (
                    await client.send_message(
                        chat_id=UPDATE_CHANNEL,
                        text=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                )

            except Exception as e:

                print(
                    f"Text post error: {e}"
                )

                return

        # ====================================================
        # CACHE
        # ====================================================

        POST_CACHE[
            cache_key
        ] = {
            "msg_id": sent_msg.id,
            "entries": entries,
            "imdb_info": imdb_info,
            "quality_info": quality_info
        }

        # ====================================================
        # CLEAN TEMP FILES
        # ====================================================

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

        print(
            f"[AUTO POST] "
            f"Successfully posted: "
            f"{imdb_info.get('display_title')}"
        )
