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

POSTED_OTT_MOVIES = set()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def clean_movie_title(raw_title):
    title = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title)
    title = re.sub(r"[^a-zA-Z0-9\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()

def get_highres_poster_url(clean_title):
    try:
        query = f"{clean_title} malayalam movie poster hd"
        search_url = f"https://yandex.com/images/search?text={urllib.parse.quote(query)}"
        r = requests.get(search_url, headers=HEADERS, timeout=8)
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

def fetch_live_ott_releases():
    """Nowrunning മലയാളം OTT കലണ്ടർ ശേഖരിക്കുന്നു"""
    url = "https://www.nowrunning.com/malayalam-streaming-guide/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        movie_items = []

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

            img_tag = card.find('img')
            img_url = img_tag.get('src') if img_tag else None

            movie_items.append({
                "title": name,
                "platform": platform,
                "poster": img_url
            })

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

async def run_ott_scraper(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_live_ott_releases)

    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ OTT വിവരങ്ങൾ കണ്ടെത്താനായില്ല.")
        return

    posted = 0
    for item in movies:
        movie_key = f"{item['title']}_{item['platform']}".lower()
        if movie_key in POSTED_OTT_MOVIES:
            continue

        clean_name = clean_movie_title(item['title'])
        best_poster = await loop.run_in_executor(None, get_highres_poster_url, clean_name)
        final_poster = best_poster or item.get("poster")

        caption = (
            f"📢 <b>UPCOMING / NEW OTT RELEASE</b> 🎬\n\n"
            f"🎞 <b>Movie :</b> {item['title']}\n"
            f"📺 <b>Platform :</b> <b>{item['platform']}</b>\n"
            f"🗣 <b>Audio :</b> Malayalam\n"
            f"🗓 <b>Status :</b> Streaming Soon / Out Now\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>OTT Update Added</b> ✅\n"
            f"💬 <b>Discussion Group :</b> <a href='{GROUP_LINK}'>{GROUP_NAME}</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        buttons = [
            [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=clean_name)],
            [InlineKeyboardButton("👥 Join Discussion Group 👥", url=GROUP_LINK)]
        ]
        button_markup = InlineKeyboardMarkup(buttons)

        temp_img = None
        if final_poster:
            temp_img = await loop.run_in_executor(None, download_temp_image, final_poster, f"ott_post_{posted}.jpg")

        try:
            if temp_img and os.path.exists(temp_img):
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=temp_img,
                    caption=caption,
                    reply_markup=button_markup,
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
                    reply_markup=button_markup,
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
    POSTED_OTT_MOVIES.clear()
    msg = await message.reply_text("🔍 പുതിയ OTT റിലീസുകൾ പരിശോധിക്കുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_ott_scraper(client, msg)

async def auto_ott_loop(client: Client):
    await asyncio.sleep(60)
    while True:
        try:
            await run_ott_scraper(client)
        except Exception as e:
            print(f"[OTT Loop Error]: {e}")
        # ഓരോ 2 മണിക്കൂറിലും ഓട്ടോമാറ്റിക് ആയി ചെക്ക് ചെയ്യും
        await asyncio.sleep(7200)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-2)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
