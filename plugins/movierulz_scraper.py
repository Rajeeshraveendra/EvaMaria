import asyncio
import os
import re
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
POSTED_LINKS = set()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_title_for_search(raw_title):
    title = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title)
    tags = ["malayalam", "full movie", "watch online", "free", "download", "hdrip", "dvdrip", "hd"]
    for t in tags:
        title = re.sub(rf"\b{t}\b", "", title, flags=re.IGNORECASE)
    return title.strip()

def fetch_movierulz_movies():
    url = "https://www.5movierulz.works/category/malayalam-featured"
    print(f"[Scraper] Requesting URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print(f"[Scraper] HTTP Status: {response.status_code}")
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('div', class_='boxed film')
        if not items:
            items = soup.select('.content ul li') or soup.find_all('div', class_='item')

        print(f"[Scraper] Found {len(items)} items")
        movie_list = []
        for item in items[:5]:
            a_tag = item.find('a')
            if not a_tag or not a_tag.get('href'):
                continue

            page_link = a_tag['href']
            img_tag = item.find('img')
            poster = img_tag.get('src') if img_tag else None
            title = a_tag.get('title') or (img_tag.get('alt') if img_tag else "New Movie")

            movie_list.append({
                "page_url": page_link,
                "title": title.strip(),
                "poster": poster
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
        poster_url = None
        entry_div = soup.find('div', class_='entry-content') or soup
        img_elem = entry_div.find('img')
        if img_elem and img_elem.get('src'):
            poster_url = img_elem['src']

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

async def run_scraper_process(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_movierulz_movies)
    
    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ സിനിമകൾ കണ്ടെത്താനായില്ല അല്ലെങ്കിൽ സൈറ്റ് ബ്ലോക്ക് ആണ് (Status 403 / Cloudflare).")
        return

    posted_count = 0
    for movie in reversed(movies):
        link = movie["page_url"]
        if link in POSTED_LINKS:
            continue

        story, detailed_poster = await loop.run_in_executor(None, fetch_movie_story, link)
        final_poster = detailed_poster or movie.get("poster")
        search_query = clean_title_for_search(movie["title"])

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
            [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=search_query)]
        ])

        try:
            if final_poster:
                await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=final_poster,
                    caption=caption,
                    reply_markup=button,
                    parse_mode=enums.ParseMode.HTML
                )
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
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted_count} പുതിയ പോസ്റ്റുകൾ ചാനലിലേക്ക് അയച്ചു.")

# മാന്വൽ ആയി ടെസ്റ്റ് ചെയ്യാനുള്ള കമാൻഡ്
@Client.on_message(filters.command("scrape"))
async def manual_scrape_cmd(client: Client, message):
    msg = await message.reply_text("🔍 Movierulz പരിശോധിക്കുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_scraper_process(client, msg)

# ബാക്ക്ഗ്രൗണ്ട് ഓട്ടോ ലൂപ്പ്
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
