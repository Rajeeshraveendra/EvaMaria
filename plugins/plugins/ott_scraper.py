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
    'Accept-Language': 'en-US,en;q=0.9',
}

def clean_title(title_raw):
    cleaned = re.sub(r"\(.*?\)|\[.*?\]", "", title_raw)
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

def get_ott_poster(movie_title):
    """യാൻഡെക്സ് വഴി ഒഫീഷ്യൽ ഹൈ-റെസല്യൂഷൻ OTT റിലീസ് പോസ്റ്റർ കണ്ടെത്തുന്നു"""
    try:
        query = f"{movie_title} malayalam movie ott release poster hd"
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
    """Binged / OTT റിലീസ് കലണ്ടറിൽ നിന്ന് വിവരങ്ങൾ ശേഖരിക്കുന്നു"""
    url = "https://www.binged.com/streaming-premiere-dates/malayalam/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        if not rows:
            rows = soup.select('.table tbody tr')

        releases = []
        for row in rows[:12]:
            cols = row.find_all('td')
            if len(cols) >= 3:
                # മൂവി ടൈറ്റിൽ
                title_elem = cols[0].find('a') or cols[0]
                movie_name = title_elem.get_text().strip()
                if not movie_name or "movie" in movie_name.lower():
                    continue

                # സ്ട്രീമിംഗ് പ്ലാറ്റ്‌ഫോം
                platform_elem = cols[1].find('img')
                platform = platform_elem.get('alt', '').strip() if platform_elem else cols[1].get_text().strip()
                if not platform:
                    platform = "OTT Platform"

                # റിലീസ് തീയതി
                release_date = cols[2].get_text().strip()

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
            await status_msg.edit_text("❌ OTT വിവരങ്ങൾ കണ്ടെത്താനായില്ല.")
        return

    posted = 0
    for item in movies:
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
            f"🔔 <i>Stay tuned for instant download links!</i>\n"
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
        # ഓരോ 2 മണിക്കൂറിലും പരിശോധിക്കുന്നു
        await asyncio.sleep(7200)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-2)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
