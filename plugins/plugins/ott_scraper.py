import asyncio
import os
import requests
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))
POSTED_OTT_MOVIES = set()

# TMDB ഒഫീഷ്യൽ റീഡ് API (ബ്ലോക്ക് ഇല്ലാതെ ലൈവ് ആയി ലഭിക്കാൻ)
TMDB_API_KEY = "1b8826543b7431e133c9429188d3d922"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
}

def fetch_upcoming_malayalam_movies():
    """TMDB API വഴി വരാനിരിക്കുന്ന മലയാളം റിലീസുകൾ ഫെച്ച് ചെയ്യുന്നു"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        next_month = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

        url = "https://api.themoviedb.org/3/discover/movie"
        params = {
            "api_key": TMDB_API_KEY,
            "with_original_language": "ml",
            "primary_release_date.gte": today,
            "primary_release_date.lte": next_month,
            "sort_by": "primary_release_date.asc",
            "include_adult": "false"
        }
        res = requests.get(url, params=params, timeout=12)
        if res.status_code == 200:
            results = res.json().get("results", [])
            # വരാനിരിക്കുന്ന മലയാളം സിനിമകൾ ഇല്ലെങ്കിൽ ഏറ്റവും പുതിയ റിലീസുകൾ എടുക്കുന്നു
            if not results:
                params["sort_by"] = "release_date.desc"
                del params["primary_release_date.gte"]
                del params["primary_release_date.lte"]
                res = requests.get(url, params=params, timeout=12)
                results = res.json().get("results", [])

            movie_list = []
            for m in results[:6]:
                title = m.get("title") or m.get("original_title")
                rel_date = m.get("release_date") or "Coming Soon"
                poster_path = m.get("poster_path")
                overview = m.get("overview") or ""
                
                poster_url = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else None

                movie_list.append({
                    "id": m.get("id"),
                    "title": title,
                    "date": rel_date,
                    "poster": poster_url,
                    "story": overview
                })
            return movie_list
    except Exception as e:
        print(f"[TMDB OTT Error]: {e}")
    return []

def download_temp_image(url, filename):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
            return filename
    except Exception as e:
        print(f"[Download Error]: {e}")
    return None

async def run_ott_scraper(client: Client, status_msg=None):
    loop = asyncio.get_event_loop()
    movies = await loop.run_in_executor(None, fetch_upcoming_malayalam_movies)

    if not movies:
        if status_msg:
            await status_msg.edit_text("❌ റിലീസ് വിവരങ്ങൾ ലഭ്യമായില്ല. ദയവായി അല്പം കഴിഞ്ഞ് ശ്രമിക്കുക.")
        return

    posted = 0
    for item in movies:
        movie_key = f"{item['title']}_{item['date']}".lower()
        if movie_key in POSTED_OTT_MOVIES:
            continue

        caption = (
            f"📢 <b>UPCOMING / NEW RELEASE</b> 🎬\n\n"
            f"🎞 <b>Movie :</b> {item['title']}\n"
            f"🗓 <b>Release Date :</b> {item['date']}\n"
            f"🗣 <b>Audio :</b> Malayalam\n"
        )
        if item.get("story"):
            caption += f"\n📖 <b>Storyline :</b>\n<i>{item['story'][:350]}...</i>\n"

        caption += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 <i>Stay tuned to RRK Movies for updates!</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=item['title'])]
        ])

        temp_img = None
        if item.get("poster"):
            temp_img = await loop.run_in_executor(None, download_temp_image, item["poster"], f"rel_{posted}.jpg")

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
        await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted} പുതിയ റിലീസ് വിവരങ്ങൾ ചാനലിൽ പോസ്റ്റ് ചെയ്തു.")

@Client.on_message(filters.command("ott") & filters.private)
async def manual_ott_cmd(client: Client, message):
    msg = await message.reply_text("🔍 പുതിയ റിലീസുകൾ പരിശോധിക്കുന്നു, ദയവായി കാത്തിരിക്കുക...")
    await run_ott_scraper(client, msg)

async def auto_ott_loop(client: Client):
    await asyncio.sleep(60)
    while True:
        try:
            await run_ott_scraper(client)
        except Exception as e:
            print(f"[OTT Loop Error]: {e}")
        # ഓരോ 4 മണിക്കൂറിലും പരിശോധിക്കുന്നു
        await asyncio.sleep(14400)

@Client.on_message(filters.private & ~filters.command(["scrape", "ott", "start", "help"]), group=-2)
async def start_ott_loop_trigger(client: Client, message):
    if not hasattr(client, "_ott_loop_started"):
        client._ott_loop_started = True
        asyncio.create_task(auto_ott_loop(client))
