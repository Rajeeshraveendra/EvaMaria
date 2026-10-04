import asyncio
import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
POSTED_OTT_MOVIES = set()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

def clean_title(title_raw):
    cleaned = re.sub(r"\(.*?\)|\[.*?\]", "", title_raw)
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

def get_ott_poster(movie_title):
    try:
        query = f"{movie_title} malayalam movie poster hd"
        search_url = f"https://yandex.com/images/search?text={urllib.parse.quote(query)}"
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            links = re.findall(r'img_url=(https?[^&]+)', r.text)
            for link in links:
                unquoted = urllib.parse.unquote(link)
                if any(ext in unquoted.lower() for ext in ['.jpg', '.jpeg', '.png']):
                    return unquoted
    except Exception as e:
        print(f"[OTT Poster Search Error]: {e}")
    return None

def download_temp_image(url, filename):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200 and len(r.content) > 25000:
            with open(filename, 'wb') as f:
                f.write(r.content)
            return filename
    except Exception as e:
        print(f"[OTT Download Error]: {e}")
    return None

def fetch_upcoming_malayalam_ott():
    """Filmibeat / OTT കലണ്ടറിൽ നിന്ന് മലയാളം റിലീസുകൾ ശേഖരിക്കുന്നു"""
    url = "https://www.filmibeat.com/malayalam/ott-releases.html"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            # ബാക്കപ്പ് എൻഡ്‌പോയിന്റ്
            url = "https://www.binged.com/streaming-premiere-dates/malayalam/"
            res = requests.get(url, headers=HEADERS, timeout=15)

        soup = BeautifulSoup(res.text, 'html.parser')
        releases = []

        # Filmibeat ഘടന
        items = soup.select('.ott-movie-list li, .movie-list-item, tr')
        for item in items[:15]:
            title_elem = item.find(['h3', 'h4', 'a', 'strong'])
            if not title_elem:
                continue

            movie_name = title_elem.get_text().strip()
            if not movie_name or len(movie_name) < 2 or "movie" in movie_name.lower():
                continue

            # പ്ലാറ്റ്‌ഫോം
            text_all = item.get_text()
            platform = "OTT Platform"
            for p in ["Netflix", "Amazon Prime", "SonyLIV", "Disney+ Hotstar", "Manorama Max", "Zee5", "Saina Play", "JioCinema"]:
                if p.lower() in text_all.lower():
                    platform = p
                    break

            # തീയതി
            date_match = re.search(r'(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:\s+\d{4})?|Coming Soon)', text_all, re.IGNORECASE)
            release_date = date_match.group(1) if date_match else "Coming Soon"

            releases.append({
                "title": movie_name,
                "platform": platform,
                "date": release_date
            })

        return releases
    except Exception as e:
        print(f"[OTT Fetch Error]: {e}")
        return []

async def run_ott_scraper(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_upcoming_malayalam_ott)

    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ നിലവിൽ പുതിയ OTT വിവരങ്ങൾ ലഭ്യമല്ല. അല്പം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക.")
        return

    posted = 0
    for item in movies[:6]:
        movie_key = f"{item['title']}_{item['platform']}".lower()
        if movie_key in POSTED_OTT_MOVIES:
            continue

        clean_name = clean_title(item['title'])
        poster_url = await loop.run_in_executor(None, get_ott_poster, clean_name)

        caption = (
            f"📢 <b>UPCOMING OTT RELEASE</b> 🎬\n\n"
            f"🎞 <b>Movie :</b> {item['title']}\n"
            f"📺 <b>Platform :</b> <b>{item['platform']}</b>\n"
            f"🗓 <b>Release Date :</b> {item['date']}\n"
            f"🗣 <b>Audio :</b> Malayalam\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 <i>Stay tuned to RRK Movies for instant updates!</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=clean_name)]
        ])

        temp_img = None
        if poster_url:
            temp_img = await loop.run_in_executor(None, download_temp_image, poster_url, f"ott_{posted}.jpg")

        try:
            if temp_img and os.path.exists(temp_img):
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=temp_img,
                    caption=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
                try:
                    os.remove(temp_img)
                except:
                    pass
            else:
                await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
            posted += 1
            POSTED_OTT_MOVIES.add(movie_key)
            await asyncio.sleep(4)
        except Exception as err:
            print(f"[OTT Send Error]: {err}")

    if status_msg:
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted} പുതിയ OTT അപ്‌ഡേറ്റുകൾ ചാനലിൽ പോസ്റ്റ് ചെയ്തു.")

@Client.on_message(filters.command("ott") & filters.private)
async def manual_ott_cmd(client: Client, message):
    msg = await message.reply_text("🔍 പുതിയ OTT റിലീസുകൾ പരിശോധിക്കുന്നു...")
    await run_ott_scraper(client, msg)

async def auto_ott_loop(client: Client):
    await asyncio.sleep(60)
    while True:
        try:
            await run_ott_scraper(client)
        except Exception as e:
            print(f"[OTT Loop Error]: {e}")
        await asyncio.sleep(7200)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-2)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
