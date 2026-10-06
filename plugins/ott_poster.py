import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import Client, filters
from info import ADMINS

# ==============================
# RRK OTT POSTER SETTINGS
# ==============================

LOGO_PATH = "assets/rrk_logo.png"
OUTPUT_PATH = "ott_poster.jpg"

poster_data = {}


def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def center_text(draw, text, y, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]

    draw.text(
        ((1080 - width) / 2, y),
        text,
        font=font,
        fill=fill
    )


def create_poster(
    input_file,
    output_file,
    movie_name,
    release_date,
    platform
):

    W = 1080
    H = 1350

    image = Image.open(input_file).convert("RGB")

    # ==============================
    # CROP TO 4:5
    # ==============================

    ratio = W / H
    current = image.width / image.height

    if current > ratio:
        new_width = int(image.height * ratio)
        left = (image.width - new_width) // 2

        image = image.crop(
            (
                left,
                0,
                left + new_width,
                image.height
            )
        )

    else:
        new_height = int(image.width / ratio)
        top = (image.height - new_height) // 2

        image = image.crop(
            (
                0,
                top,
                image.width,
                top + new_height
            )
        )

    image = image.resize(
        (W, H),
        Image.Resampling.LANCZOS
    )

    image = image.convert("RGBA")

    # ==============================
    # CINEMATIC DARK GRADIENT
    # ==============================

    overlay = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    for y in range(H):

        if y < 650:
            alpha = 15
        else:
            alpha = int(
                220 *
                ((y - 650) / (H - 650))
            )

        draw.line(
            [(0, y), (W, y)],
            fill=(0, 0, 0, alpha)
        )

    image = Image.alpha_composite(
        image,
        overlay
    )

    draw = ImageDraw.Draw(image)

    # ==============================
    # RRK LOGO
    # ==============================

    if os.path.exists(LOGO_PATH):

        logo = Image.open(
            LOGO_PATH
        ).convert("RGBA")

        max_width = 230

        scale = max_width / logo.width

        logo = logo.resize(
            (
                max_width,
                int(logo.height * scale)
            ),
            Image.Resampling.LANCZOS
        )

        # Small shadow
        shadow = Image.new(
            "RGBA",
            logo.size,
            (0, 0, 0, 0)
        )

        image.alpha_composite(
            shadow,
            (
                W - logo.width - 40,
                35
            )
        )

        image.alpha_composite(
            logo,
            (
                W - logo.width - 40,
                35
            )
        )

    # ==============================
    # OTT RELEASE
    # ==============================

    white = (255, 255, 255)
    gold = (255, 193, 55)

    ott_font = get_font(
        60,
        bold=True
    )

    date_font = get_font(
        125,
        bold=True
    )

    platform_font = get_font(
        55,
        bold=True
    )

    movie_font = get_font(
        42,
        bold=True
    )

    center_text(
        draw,
        "OTT RELEASE",
        850,
        ott_font,
        white
    )

    # ==============================
    # RELEASE DATE
    # ==============================

    center_text(
        draw,
        release_date.upper(),
        925,
        date_font,
        gold
    )

    # ==============================
    # PLATFORM
    # ==============================

    center_text(
        draw,
        f"ON {platform.upper()}",
        1075,
        platform_font,
        white
    )

    # ==============================
    # MOVIE NAME
    # ==============================

    center_text(
        draw,
        movie_name.upper(),
        1165,
        movie_font,
        gold
    )

    # ==============================
    # GOLD LINE
    # ==============================

    draw.line(
        (170, 1140, 910, 1140),
        fill=gold,
        width=3
    )

    draw.line(
        (170, 1240, 910, 1240),
        fill=gold,
        width=3
    )

    image.convert("RGB").save(
        output_file,
        "JPEG",
        quality=95,
        optimize=True
    )


# ==============================
# /OTT COMMAND
# ==============================

@Client.on_message(
    filters.command("ott") &
    filters.user(ADMINS)
)
async def ott_command(client, message):

    if len(message.command) < 2:

        await message.reply_text(
            "🎬 <b>OTT POSTER</b>\n\n"
            "Use:\n"
            "<code>/ott MOVIE | DATE | PLATFORM</code>\n\n"
            "Example:\n"
            "<code>/ott KHALIFA | OCT 9 | OTT</code>\n\n"
            "Then send the movie poster.",
            parse_mode="html"
        )

        return

    data = message.text.split(" ", 1)[1]

    parts = [
        x.strip()
        for x in data.split("|")
    ]

    movie_name = parts[0]

    release_date = (
        parts[1]
        if len(parts) > 1
        else "OCT 9"
    )

    platform = (
        parts[2]
        if len(parts) > 2
        else "OTT"
    )

    poster_data[message.from_user.id] = {
        "movie": movie_name,
        "date": release_date,
        "platform": platform
    }

    await message.reply_text(
        f"🎬 <b>{movie_name}</b>\n"
        f"📅 <b>{release_date}</b>\n"
        f"📺 <b>{platform}</b>\n\n"
        "✅ Details saved.\n\n"
        "ഇനി original movie poster/photo അയക്കൂ.",
        parse_mode="html"
    )


# ==============================
# RECEIVE POSTER
# ==============================

@Client.on_message(
    filters.photo &
    filters.user(ADMINS)
)
async def receive_poster(client, message):

    user_id = message.from_user.id

    if user_id not in poster_data:
        return

    data = poster_data[user_id]

    status = await message.reply_text(
        "🎬 Creating OTT poster...\n⏳ Please wait..."
    )

    try:

        downloaded = await message.download(
            file_name="input_movie_poster.jpg"
        )

        create_poster(
            downloaded,
            OUTPUT_PATH,
            data["movie"],
            data["date"],
            data["platform"]
        )

        await message.reply_photo(
            photo=OUTPUT_PATH,
            caption=(
                "🎬 <b>OTT RELEASE POSTER</b>\n\n"
                f"🎞 <b>{data['movie']}</b>\n"
                f"📅 <b>{data['date']}</b>\n"
                f"📺 <b>{data['platform']}</b>\n\n"
                "© RRK MOVIES"
            ),
            parse_mode="html"
        )

        await status.delete()

    except Exception as e:

        await status.edit(
            f"❌ Poster creation failed:\n<code>{e}</code>",
            parse_mode="html"
        )

    finally:

        poster_data.pop(
            user_id,
            None
        )

        if os.path.exists(
            "input_movie_poster.jpg"
        ):
            os.remove(
                "input_movie_poster.jpg"
            )

        if os.path.exists(
            OUTPUT_PATH
        ):
            os.remove(
                OUTPUT_PATH
            )
