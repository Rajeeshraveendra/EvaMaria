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

HISTORY_FILE = "posted_movierulz.txt"
TMDB_API_KEY = "1b8826543b7431e133c9429188d3d922"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def load_posted_links():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_posted_link(link):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{link}\n")

def is_sleep_time():
    now_utc = datetime.now(timezone.utc)
    gst_hour = (now_utc + timedelta(hours=4)).hour
    return 22 <= gst_hour or gst_hour < 7

def clean_movie_title(raw_title):
    year_match = re.search(r'\b(20\d\d|19\d\d)\b', raw_title)
    year = year_match.group(1) if year_match else ""

    title = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title)
    tags = [
        "malayalam", "tamil", "telugu", "hindi", "kannada", "english",
        "full movie", "watch online", "free", "download", "hdrip", "dvdrip", 
        "hd", "hq", "predvd", "pre-dvd", "proper", "true", "web-dl", "esub"
    ]
    for tag in tags:
        title = re.sub(rf"\b{tag}\b", "", title, flags=re.IGNORECASE)

    title = re.sub(r"[^a-zA-Z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title, year

def get_pure_hd_poster(clean_title, year=""):
    """Apple iTunes & TMDB വഴി 2000x2000 Ultra HD ഒറിജിനൽ പോസ്റ്റർ കണ്ടെത്തുന്നു"""
    # 1. Apple iTunes HD Search (ക്രിസ്റ്റൽ ക്ലിയർ പോസ്റ്ററുകൾ ലഭിക്കും)
    try:
        itunes_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(clean_title)}&entity=movie&limit=3"
        r = requests.get(itunes_url, timeout=5).json()
        if r.get("resultCount", 0) > 0:
            for item in r.get("results", []):
                raw_art = item.get("artworkUrl100")
                if raw_art:
                    # 100x100 മാറ്റി 2000x2000 Ultra HD ആക്കുന്നു
                    return re.sub(r'\d+x\d+bb', '2000x2000bb', raw_art)
    except Exception as e:
        print(f"[iTunes Poster Error]: {e}")

    # 2. TMDB Original 4K Poster
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": clean_title, "include_adult": "false"}
        if year:
            params["primary_release_date_year"] = year
        res = requests.get(url, params=params, timeout=5).json()
        results = res.get("results", [])
        if results and results[0].get("poster_path"):
            return f"https://image.tmdb.org/t/p/original{results[0]['poster_path']}"
    except Exception as e:
        print(f"[TMDB Poster Error]: {e}")

    return None

def get_trailer_url(clean_title, year="", lang="Movie"):
    trailer_url = None
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": clean_title, "include_adult": "false"}
        if year:
            params["primary_release_date_year"] = year
        res = requests.get(url, params=params, timeout=5).json()
        results = res.get("results", [])
        if results:
            movie_id = results[0].get("id")
            if movie_id:
                v_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
                v_res = requests.get(v_url, params={"api_key": TMDB_API_KEY}, timeout=5).json()
                for v in v_res.get("results", []):
                    if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                        trailer_url = f"https://www.youtube.com/watch?v={v.get('key')}"
                        break
    except Exception as e:
        print(f"[Trailer Error]: {e}")

    if not trailer_url:
        search_query = urllib.parse.quote(f"{clean_title} {year} {lang} movie official trailer")
        trailer_url = f"https://www.youtube.com/results?search_query={search_query}"

    return trailer_url

def fetch_movierulz_movies():
    categories = [
        {"url": "https://www.5movierulz.works/category/malayalam-featured", "lang": "Malayalam"},
        {"url": "https://www.5movierulz.works/category/tamil-featured", "lang": "Tamil"},
        {"url": "https://www.5movierulz.works/category/telugu-featured", "lang": "Telugu"},
        {"url": "https://www.5movierulz.works/category/bollywood-featured", "lang": "Hindi"},
        {"url": "https://www.5movierulz.works/category/hollywood-movie-free", "lang": "English"}
    ]
    movie_list = []

    for cat in categories:
        try:
            response = requests.get(cat["url"], headers=HEADERS, timeout=8)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('div', class_='boxed film')
            if not items:
                items = soup.select('.content ul li') or soup.find_all('div', class_='item')

            for item in items[:2]:
                a_tag = item.find('a')
                if not a_tag or not a_tag.get('href'):
                    continue

                page_link = a_tag['href']
                img_tag = item.find('img')
                raw_poster = img_tag.get('src') if img_tag else None
                
                clean_site_poster = None
                if raw_poster:
                    clean_site_poster = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', raw_poster)
                    if not clean_site_poster.startswith("http"):
                        clean_site_poster = "https:" + clean_site_poster

                title = a_tag.get('title') or (img_tag.get('alt') if img_tag else "New Movie")

                movie_list.append({
                    "page_url": page_link,
                    "title": title.strip(),
                    "site_poster": clean_site_poster,
                    "lang": cat["lang"]
                })
        except Exception as e:
            print(f"[Scraper] Error in {cat['lang']}: {e}")

    return movie_list

def fetch_movie_story(page_url):
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=6)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 80 and not text.lower().startswith(("download", "watch", "torrent")):
                return text
        return None
    except Exception as e:
        print(f"[Scraper] Detail Error: {e}")
        return None

async def run_scraper_process(client: Client, status_msg=None, force=False):
    if not force and is_sleep_time():
        return

    posted_links = load_posted_links()
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_movierulz_movies)
    
    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ സിനിമകൾ കണ്ടെത്താനായില്ല.")
        return

    posted_count = 0
    for movie in reversed(movies):
        link = movie["page_url"]
        if not force and link in posted_links:
            continue

        clean_title, year = clean_movie_title(movie["title"])
        lang = movie.get("lang", "Movie")

        # Apple iTunes / TMDB വഴി 2000x2000 ക്രിസ്റ്റൽ ക്ലിയർ ഫോട്ടോ ഉറപ്പാക്കുന്നു
        hd_poster = await loop.run_in_executor(None, get_pure_hd_poster, clean_title, year)
        final_img = hd_poster or movie.get("site_poster")

        trailer_url = await loop.run_in_executor(None, get_trailer_url, clean_title, year, lang)
        story = await loop.run_in_executor(None, fetch_movie_story, link)

        caption = f"🎬 <b>{movie['title']}</b>\n\n"
        if story:
            caption += f"📖 <b>Storyline :</b>\n<i>{story[:400]}...</i>\n\n"

        caption += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>New {lang} Release Added</b> ✅\n"
            f"💬 <b>Discussion Group :</b> <a href='{GROUP_LINK}'>{GROUP_NAME}</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        buttons = [
            [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=clean_title)],
            [InlineKeyboardButton("🎬 Watch Official Trailer 🍿", url=trailer_url)],
            [InlineKeyboardButton("👥 Join Discussion Group 👥", url=GROUP_LINK)]
        ]
        button_markup = InlineKeyboardMarkup(buttons)

        try:
            if final_img:
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=final_img,
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
            posted_count += 1
            save_posted_link(link)
            posted_links.add(link)
            await asyncio.sleep(3)
        except Exception as send_err:
            print(f"[Scraper] Send Error: {send_err}")

    if status_msg:
        if posted_count > 0:
            await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted_count} പുതിയ സിനിമകൾ അൾട്രാ HD ക്വാളിറ്റിയിൽ അയച്ചു.")
        else:
            await status_msg.edit_text("ℹ️️ പുതിയ സിനിമകൾ ലഭ്യമല്ല (ലിസ്റ്റിലുള്ള എല്ലാം ഇതിനകം ചാനലിൽ പോസ്റ്റ് ചെയ്തിട്ടുണ്ട്).")

@Client.on_message(filters.command("scrape") & filters.private)
async def manual_scrape_cmd(client: Client, message):
    msg = await message.reply_text("🔍 പുതിയ സിനിമകൾ അൾട്രാ HD ക്വാളിറ്റിയിൽ പരിശോധിക്കുന്നു...")
    await run_scraper_process(client, msg, force=True)

async def auto_loop(client: Client):
    await asyncio.sleep(30)
    while True:
        try:
            await run_scraper_process(client)
        except Exception as e:
            print(f"[Scraper] Loop Error: {e}")
        await asyncio.sleep(1200)

@Client.on_message(filters.command("start") & filters.private)
async def start_loop_trigger(client: Client, message):
    if not hasattr(client, "_scraper_loop_started"):
        client._scraper_loop_started = True
        asyncio.create_task(auto_loop(client))
