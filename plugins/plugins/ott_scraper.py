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
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def clean_title(title_raw):
    cleaned = re.sub(r"\(.*?\)|\[.*?\]", "", title_raw)
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

def get_ott_hd_poster(movie_title):
    """ഒറിജിനൽ ഹൈ-റെസല്യൂഷൻ OTT റിലീസ് പോസ്റ്റർ കണ്ടെത്തുന്നു"""
    try:
        query = f"{movie_title} malayalam movie poster hd"
        search_url = f"https://yandex.com/images/search?text={urllib.parse.quote(query)}"
        r = requests.get(search_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            links = re.findall(r'img_url=(https?[^&]+)', r.text)
            for link in links:
                unquoted = urllib.parse.unquote(link)
                if any(ext in unquoted.lower() for ext in ['.jpg', '.jpeg', '.png']):
                    return unquoted
    except Exception as e:
        print(f"[Poster Search Error]: {e}")
    return None

def fetch_live_ott_releases():
    """Nowrunning മലയാളം OTT ലൈവ് കലണ്ടർ സ്ക്രാപ്പ് ചെയ്യുന്നു"""
    url = "https://www.nowrunning.com/malayalam-streaming-guide/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        movie_items = []

        # Nowrunning മൂവി കാർഡുകൾ
        cards = soup.select('.col-sm-6, .col-md-4, .col-lg-3, .movie-listing, .stream-card')
        for card in cards:
            title_tag = card.find(['h3', 'h4', 'h5', 'a', 'strong'])
            if not title_tag:
                continue

            name = title_tag.get_text().strip()
            if not name or len(name) < 3 or "streaming" in name.lower():
                continue

            card_text = card.get_text()
            platform = "Digital OTT"
            for p in ["JioHotstar", "Hotstar", "SonyLIV", "Sony LIV", "Manorama MAX", "ManoramaMax", "Netflix", "Amazon Prime", "Prime Video", "Zee5", "Saina Play"]:
                if p.lower() in card_text.lower():
                    platform = p
                    break

            # ചിത്രം
            img_tag = card.find('img')
            img_url = img_tag.get('src') if img_tag else None

            movie_items.append({
                "title": name,
                "platform": platform,
                "poster": img_url
            })

        # വെബ്സൈറ്റ് ഘടന മാറിയാൽ നേരിട്ടുള്ള ലിസ്റ്റ് ബാക്കപ്പ്
        if not movie_items:
            for a in soup.find_all('a'):
                href = a.get('href', '')
                text = a.get_text().strip()
                if '/movie/' in href and len(text) > 3:
                    movie_items.append({
                        "title": text,
                        "platform": "OTT Premiere",
                        "poster": None
                    })

        return movie_items[:6]
    except Exception as e:
        print(f"[Nowrunning Fetch Error]: {e}")
        return []

def download_image(url, path):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
    except Exception as e:
        print(f"[Image Download Error]: {e}")
    return None

async def run_ott_scraper(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_live_ott_releases)

    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ റിലീസ് വിവരങ്ങൾ ലഭ്യമായില്ല. ദയവായി അല്പം കഴിഞ്ഞ് ശ്രമിക്കുക.")
        return

    posted = 0
    for item in movies:
        movie_key = f"{item['title']}_{item['platform']}".lower()
        if movie_key in POSTED_OTT_MOVIES:
            continue

        clean_name = clean_title(item['title'])
        best_poster = await loop.run_in_executor(None, get_ott_hd_poster, clean_name)
        final_poster = best_poster or item.get("poster")

        caption = (
            f"📢 <b>UPCOMING / NEW OTT RELEASE</b> 🎬\n\n"
            f"🎞 <b>Movie :</b> {item['title']}\n"
            f"📺 <b>Platform :</b> <b>{item['platform']}</b>\n"
            f"🗣 <b>Audio :</b> Malayalam\n"
            f"🗓 <b>Status :</b> Streaming Soon / Out Now\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 <i>Stay tuned to RRK Movies for updates!</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=clean_name)]
        ])

        temp_img = None
        if final_poster:
            temp_img = await loop.run_in_executor(None, download_image, final_poster, f"ott_post_{posted}.jpg")

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
    msg = await message.reply_text("🔍 പുതിയ OTT റിലീസുകൾ പരിശോധിക്കുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_ott_scraper(client, msg)

async def auto_ott_loop(client: Client):
    await asyncio.sleep(60)
    while True:
        try:
            await run_ott_scraper(client)
        except Exception as e:
            print(f"[OTT Loop Error]: {e}")
        await asyncio.sleep(14400)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-2)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
