import asyncio
import os
import re
import requests
from bs4 import BeautifulSoup
from imdb import Cinemagoer
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
POSTED_LINKS = set()

# Cinemagoer (IMDb) ഒറിജിനൽ HD പോസ്റ്റർ ലഭ്യമാക്കാൻ
ia = Cinemagoer()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def clean_movie_title(raw_title):
    year_match = re.search(r'\b(20\d\d|19\d\d)\b', raw_title)
    year = year_match.group(1) if year_match else None

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

def get_imdb_hd_poster(title, year=None):
    """IMDb-യിൽ നിന്ന് ഒറിജിനൽ ഹൈ-റെസല്യൂഷൻ പോസ്റ്റർ ഫെച്ച് ചെയ്യുന്നു"""
    try:
        search_query = f"{title} {year}" if year else title
        results = ia.search_movie(search_query)
        if not results and year:
            results = ia.search_movie(title)
            
        if results:
            movie = results[0]
            ia.update(movie, ['main'])
            # 'full-size cover url' ഒറിജിനൽ HD ക്വാളിറ്റി നൽകുന്നു
            cover = movie.get('full-size cover url') or movie.get('cover url')
            if cover:
                # ആമസോൺ/IMDb ഇമേജ് ലിങ്കിലെ ക്രോപ്പിംഗ് ടാഗുകൾ ഒഴിവാക്കി അൺകംപ്രസ്സ്ഡ് ഫയലാക്കുന്നു
                hd_url = re.sub(r'UX\d+.*?\.', '', cover)
                hd_url = re.sub(r'UY\d+.*?\.', '', hd_url)
                hd_url = re.sub(r'CR\d+.*?\.', '', hd_url)
                return hd_url
    except Exception as e:
        print(f"[IMDb HD Poster] Error: {e}")
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
            return None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_img = soup.find('meta', property='og:image')
        poster_url = meta_img['content'] if (meta_img and meta_img.get('content')) else None

        if poster_url:
            poster_url = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', poster_url)

        story_text = ""
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 80 and not text.lower().startswith(("download", "watch", "torrent")):
                story_text = text
                break

        return story_text, poster_url
    except Exception as e:
        print(f"[Scraper] Detail Error: {e}")
        return None, None

def download_temp_image(url, path):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
    except Exception as e:
        print(f"[Download Error]: {e}")
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

        # 1. IMDb വഴി ഒറിജിനൽ ഹൈ-റെസല്യൂഷൻ പോസ്റ്റർ
        best_poster = await loop.run_in_executor(None, get_imdb_hd_poster, clean_title, year)

        # 2. ബാക്കപ്പായി കഥയും Movierulz ചിത്രവും
        story, fallback_poster = await loop.run_in_executor(None, fetch_movie_story, link)
        final_poster_url = best_poster or fallback_poster or movie.get("poster")

        caption = (
            f"🎬 <b>{movie['title']}</b>\n\n"
        )
        if story:
            caption += f"📖 <b>Storyline :</b>\n<i>{story[:500]}...</i>\n\n"

        caption += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>New Malayalam Release Added</b> ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=clean_title)]
        ])

        temp_file = None
        if final_poster_url:
            temp_file = await loop.run_in_executor(None, download_temp_image, final_poster_url, f"imdb_{posted_count}.jpg")

        try:
            if temp_file and os.path.exists(temp_file):
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=temp_file,
                    caption=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
                try:
                    os.remove(temp_file)
                except:
                    pass
            else:
                await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
            posted_count += 1
            POSTED_LINKS.add(link)
            await asyncio.sleep(4)
        except Exception as send_err:
            print(f"[Scraper] Send Error: {send_err}")

    if status_msg:
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted_count} പുതിയ IMDb HD പോസ്റ്റുകൾ അയച്ചു.")

@Client.on_message(filters.command("scrape"))
async def manual_scrape_cmd(client: Client, message):
    msg = await message.reply_text("🔍 IMDb-യിൽ നിന്ന് HD പോസ്റ്ററുകൾ തിരയുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_scraper_process(client, msg)

async def auto_loop(client: Client):
    await asyncio.sleep(30)
    while True:
        try:
            await run_scraper_process(client)
        except Exception as e:
            print(f"[Scraper] Loop Error: {e}")
        await asyncio.sleep(1200)

@Client.on_message(filters.incoming, group=-1)
async def start_loop_trigger(client: Client, message):
    if not hasattr(client, "_scraper_loop_started"):
        client._scraper_loop_started = True
        asyncio.create_task(auto_loop(client))
