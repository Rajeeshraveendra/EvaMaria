import asyncio
import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
GROUP_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"
GROUP_NAME = "RRK Movies Group"

POSTED_LINKS = set()
TMDB_API_KEY = "1b8826543b7431e133c9429188d3d922"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

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

def get_highres_poster_url(clean_title, year=""):
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": clean_title, "include_adult": "false"}
        if year:
            params["primary_release_date_year"] = year
        res = requests.get(url, params=params, timeout=8)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("poster_path"):
                return f"https://image.tmdb.org/t/p/original{results[0]['poster_path']}"
    except Exception as e:
        print(f"[TMDB Error]: {e}")

    try:
        query = f"{clean_title} {year} malayalam movie poster hd"
        search_url = f"https://yandex.com/images/search?text={urllib.parse.quote(query)}"
        r = requests.get(search_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            links = re.findall(r'img_url=(https?[^&]+)', r.text)
            for link in links:
                unquoted = urllib.parse.unquote(link)
                if any(ext in unquoted.lower() for ext in ['.jpg', '.jpeg', '.png']):
                    return unquoted
    except Exception as e:
        print(f"[Web Image Error]: {e}")

    return None

def download_image_clean(url, filepath):
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200 and len(res.content) > 30000:
            with open(filepath, 'wb') as f:
                f.write(res.content)
            return filepath
    except Exception as e:
        print(f"[Image Download Error]: {e}")
    return None

def fetch_movierulz_movies():
    url = "https://www.5movierulz.works/category/malayalam-featured"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('div', class_='boxed film')
        if not items:
            items = soup.select('.content ul li') or soup.find_all('div', class_='item')

        movie_list = []
        for item in items[:5]:
            a_tag = item.find('a')
            if not a_tag or not a_tag.get('href'):
                continue

            page_link = a_tag['href']
            img_tag = item.find('img')
            raw_poster = img_tag.get('src') if img_tag else None
            clean_poster = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', raw_poster) if raw_poster else None
            title = a_tag.get('title') or (img_tag.get('alt') if img_tag else "New Movie")

            movie_list.append({
                "page_url": page_link,
                "title": title.strip(),
                "poster": clean_poster
            })
        return movie_list
    except Exception as e:
        print(f"[Scraper] Listing Error: {e}")
        return []

def fetch_movie_story(page_url):
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=12)
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

async def run_scraper_process(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_movierulz_movies)
    
    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ സിനിമകൾ കണ്ടെത്താനായില്ല.")
        return

    posted_count = 0
    for movie in reversed(movies):
        link = movie["page_url"]
        if link in POSTED_LINKS:
            continue

        clean_title, year = clean_movie_title(movie["title"])

        hd_poster_url = await loop.run_in_executor(None, get_highres_poster_url, clean_title, year)
        final_img_url = hd_poster_url or movie.get("poster")
        story = await loop.run_in_executor(None, fetch_movie_story, link)

        caption = (
            f"🎬 <b>{movie['title']}</b>\n\n"
        )
        if story:
            caption += f"📖 <b>Storyline :</b>\n<i>{story[:500]}...</i>\n\n"

        caption += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>New Malayalam Release Added</b> ✅\n"
            f"💬 <b>Discussion Group :</b> <a href='{GROUP_LINK}'>{GROUP_NAME}</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=clean_title)],
            [InlineKeyboardButton(f"👥 Join {GROUP_NAME} 👥", url=GROUP_LINK)]
        ])

        downloaded_file = None
        if final_img_url:
            downloaded_file = await loop.run_in_executor(None, download_image_clean, final_img_url, f"poster_{posted_count}.jpg")

        try:
            if downloaded_file and os.path.exists(downloaded_file):
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=downloaded_file,
                    caption=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
                try:
                    os.remove(downloaded_file)
                except:
                    pass
            elif final_img_url:
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=final_img_url,
                    caption=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
            posted_count += 1
            POSTED_LINKS.add(link)
            await asyncio.sleep(4)
        except Exception as send_err:
            print(f"[Scraper] Send Error: {send_err}")

    if status_msg:
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted_count} പുതിയ HD പോസ്റ്റുകൾ അയച്ചു.")

@Client.on_message(filters.command("scrape") & filters.private)
async def manual_scrape_cmd(client: Client, message):
    msg = await message.reply_text("🔍 ഹൈ-റെസല്യൂഷൻ പോസ്റ്ററുകൾ തിരയുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_scraper_process(client, msg)

async def auto_loop(client: Client):
    await asyncio.sleep(30)
    while True:
        try:
            await run_scraper_process(client)
        except Exception as e:
            print(f"[Scraper] Loop Error: {e}")
        await asyncio.sleep(1200)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-1)
async def start_loop_trigger(client: Client, message):
    if not hasattr(client, "_scraper_loop_started"):
        client._scraper_loop_started = True
        asyncio.create_task(auto_loop(client))
