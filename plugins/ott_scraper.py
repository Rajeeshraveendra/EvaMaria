import asyncio
import os
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
GROUP_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"
GROUP_NAME = "RRK Movies Group"

HISTORY_FILE = "posted_ott_movies.txt"
TMDB_API_KEY = "1b8826543b7431e133c9429188d3d922"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def load_posted_ott():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    return set()

def save_posted_ott(title):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{title.strip().lower()}\n")

def is_sleep_time():
    """UAE & India time 10 PM to 7 AM sleep mode"""
    now_utc = datetime.now(timezone.utc)
    gst_hour = (now_utc + timedelta(hours=4)).hour
    ist_hour = (now_utc + timedelta(hours=5, minutes=30)).hour
    return (gst_hour >= 22 or gst_hour < 7) or (ist_hour >= 22 or ist_hour < 7)

def clean_movie_title(raw_title):
    title = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title)
    title = re.sub(r"[^a-zA-Z0-9\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()

def fetch_upcoming_malayalam():
    items = []
    try:
        url = "https://www.nowrunning.com/movie-release-dates/malayalam/"
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.select('a[href*="/movie/"]'):
                text = a.get_text().strip()
                if len(text) > 2 and not any(x in text.lower() for x in ['review', 'trailer', 'photos', 'news', 'cast']):
                    clean_t = clean_movie_title(text)
                    if clean_t and clean_t not in [i['title'] for i in items]:
                        items.append({
                            "title": clean_t,
                            "type": "Theatrical / OTT Release",
                            "date": "Releasing Soon / Next Week"
                        })
                if len(items) >= 5:
                    break
    except Exception as e:
        print(f"[NowRunning Fetch Error]: {e}")

    if len(items) < 3:
        try:
            tmdb_url = "https://api.themoviedb.org/3/discover/movie"
            params = {
                "api_key": TMDB_API_KEY,
                "with_original_language": "ml",
                "sort_by": "popularity.desc",
                "primary_release_date.gte": "2026-01-01"
            }
            r = requests.get(tmdb_url, params=params, timeout=10)
            if r.status_code == 200:
                for m in r.json().get("results", []):
                    t = clean_movie_title(m.get("title", ""))
                    if t and t not in [i['title'] for i in items]:
                        items.append({
                            "title": t,
                            "type": "New / Upcoming Release",
                            "date": m.get("release_date") or "Next Week / Soon"
                        })
                    if len(items) >= 5:
                        break
        except Exception as e:
            print(f"[TMDB Discover Error]: {e}")

    return items[:5]

def get_movie_meta(title):
    poster_url = None
    trailer_url = None
    overview = None

    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": title, "include_adult": "false"}
        res = requests.get(url, params=params, timeout=8)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                m = results[0]
                overview = m.get("overview")
                if m.get("poster_path"):
                    poster_url = f"https://image.tmdb.org/t/p/original{m['poster_path']}"
                
                movie_id = m.get("id")
                if movie_id:
                    v_res = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos", params={"api_key": TMDB_API_KEY}, timeout=8)
                    if v_res.status_code == 200:
                        for v in v_res.json().get("results", []):
                            if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                                trailer_url = f"https://www.youtube.com/watch?v={v.get('key')}"
                                break
    except Exception as e:
        print(f"[Meta Error]: {e}")

    if not trailer_url:
        q = urllib.parse.quote(f"{title} malayalam movie trailer")
        trailer_url = f"https://www.youtube.com/results?search_query={q}"

    return poster_url, trailer_url, overview

async def run_ott_scraper(client: Client, status_msg=None, force=False):
    if not force and is_sleep_time():
        print("[Upcoming/OTT] Sleep mode active.")
        return

    posted_set = load_posted_ott()
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_upcoming_malayalam)

    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ വരാനിരിക്കുന്ന ചിത്രങ്ങൾ കണ്ടെത്താനായില്ല.")
        return

    posted = 0
    for item in movies:
        clean_name = item['title']
        if not clean_name:
            continue

        if not force and clean_name.lower() in posted_set:
            continue

        poster_url, trailer_url, story = await loop.run_in_executor(None, get_movie_meta, clean_name)

        caption = (
            f"📢 <b>NEXT WEEK / UPCOMING RELEASES</b> 🎬\n\n"
            f"🎞 <b>Movie :</b> {item['title']}\n"
            f"🗓 <b>Status / Date :</b> <b>{item['date']}</b>\n"
            f"📺 <b>Type :</b> {item['type']}\n"
            f"🗣 <b>Audio :</b> Malayalam\n\n"
        )
        if story:
            caption += f"📖 <b>Storyline :</b>\n<i>{story[:300]}...</i>\n\n"

        caption += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Upcoming Movie Alert</b> ✅\n"
            f"💬 <b>Discussion Group :</b> <a href='{GROUP_LINK}'>{GROUP_NAME}</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        buttons = [
            [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=clean_name)],
            [InlineKeyboardButton("🎬 Watch Official Trailer 🍿", url=trailer_url)],
            [InlineKeyboardButton("👥 Join Discussion Group 👥", url=GROUP_LINK)]
        ]
        button_markup = InlineKeyboardMarkup(buttons)

        try:
            if poster_url:
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=poster_url,
                    caption=caption,
                    reply_markup=button_markup,
                    parse_mode=enums.ParseMode.HTML,
                    disable_notification=True
                )
            else:
                await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=caption,
                    reply_markup=button_markup,
                    parse_mode=enums.ParseMode.HTML,
                    disable_notification=True
                )
            posted += 1
            save_posted_ott(clean_name)
            posted_set.add(clean_name.lower())
            await asyncio.sleep(4)
        except Exception as err:
            print(f"[Upcoming Send Error]: {err}")

    if status_msg:
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted} പുതിയ ചിത്രങ്ങൾ ചാനലിലേക്ക് അയച്ചു.")

@Client.on_message(filters.command("ott") & filters.private)
async def manual_ott_cmd(client: Client, message):
    msg = await message.reply_text("🔍 പുതിയ ചിത്രങ്ങൾ തിരയുന്നു...")
    await run_ott_scraper(client, msg, force=True)

async def auto_ott_loop(client: Client):
    await asyncio.sleep(60)
    while True:
        try:
            await run_ott_scraper(client)
        except Exception as e:
            print(f"[Upcoming Loop Error]: {e}")
        await asyncio.sleep(7200)

# Bot start aavumbol loop start cheyyunnu (Message loop trigger ozhivakki)
@Client.on_message(filters.command("start") & filters.private)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
