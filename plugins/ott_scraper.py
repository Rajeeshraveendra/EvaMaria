import asyncio
import os
import re
import sys
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS
from database.ia_filterdb import db

# ==============================
# SETTINGS
# ==============================

def _int_env(name, default):
    try:
        return int(str(os.environ.get(name) or default).strip())
    except Exception:
        logging.error(f"[OTT] Invalid {name} value, using default")
        return int(default)

UPDATE_CHANNEL = _int_env("UPDATE_CHANNEL", "-1001452215783")
OTT_CHAT_ID = _int_env("OTT_CHAT_ID", str(UPDATE_CHANNEL))
TMDB_API_KEY = (os.environ.get("TMDB_API_KEY") or "").strip()
OTT_MAX_PER_RUN = _int_env("OTT_MAX_PER_RUN", "10")      # ഒരു സമയം പരമാവധി 10 പോസ്റ്റ്
OTT_DAYS_BACK = _int_env("OTT_DAYS_BACK", "120")          # എത്ര ദിവസം മുമ്പുവരെ റിലീസ് ആയവ
WATCH_REGION = (os.environ.get("OTT_REGION") or "IN").strip().upper()
OTT_PAGES = _int_env("OTT_PAGES", "5")                    # ഓരോ ഭാഷയ്ക്കും TMDB pages

GROUP_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"
GROUP_NAME = "RRK Movies Group"

LANGUAGES = [
    ("ml", "Malayalam"),
    ("ta", "Tamil"),
    ("hi", "Hindi"),
    ("te", "Telugu"),
    ("kn", "Kannada"),
    ("en", "English"),
]

# Daily auto post slots (UAE time, UTC+4): രാവിലെ 9, ഉച്ച 2, രാത്രി 8
def _slots_env():
    try:
        hrs = [int(x) for x in (os.environ.get("OTT_SLOTS_UAE") or "9,14,20").split(",") if x.strip()]
        return sorted({h % 24 for h in hrs}) or [9, 14, 20]
    except Exception:
        return [9, 14, 20]
SLOTS_UAE = _slots_env()
UAE = timezone(timedelta(hours=4))

POSTED_COL = db["ott_posted"]   # posted OTT movies, survives restarts
META_COL = db["ott_meta"]       # last auto run time
OLD_HISTORY_FILE = "posted_ott_movies.txt"

_CLIENT = None
_LOOP_STARTED = False
RUN_LOCK = asyncio.Lock()

# ==============================
# HELPERS
# ==============================

def clean_movie_title(raw_title):
    title = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title or "")
    title = re.sub(r"[^a-zA-Z0-9\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()

def _tmdb_get(path, params=None):
    p = {"api_key": TMDB_API_KEY}
    if params:
        p.update(params)
    r = requests.get(f"https://api.themoviedb.org/3{path}", params=p, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"TMDB {path} -> HTTP {r.status_code}")
    return r.json()

def fetch_ott_releases():
    """ഇന്ത്യയിൽ OTT-ൽ (Netflix, Prime, Hotstar, ...) സ്ട്രീം ചെയ്യുന്ന പുതിയ സിനിമകൾ"""
    since = (datetime.now(timezone.utc) - timedelta(days=OTT_DAYS_BACK)).strftime("%Y-%m-%d")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    items, seen = [], set()

    for code, lang in LANGUAGES:
        for page in range(1, OTT_PAGES + 1):
            try:
                data = _tmdb_get("/discover/movie", {
                    "with_original_language": code,
                    "watch_region": WATCH_REGION,
                    "with_watch_monetization_types": "flatrate",
                    "primary_release_date.gte": since,
                    "primary_release_date.lte": today,
                    "sort_by": "primary_release_date.desc",
                    "include_adult": "false",
                    "page": page,
                })
            except Exception as e:
                logging.error(f"[OTT] discover {lang} p{page}: {e}")
                break

            results = data.get("results", [])
            for m in results:
                mid = m.get("id")
                title = (m.get("title") or m.get("original_title") or "").strip()
                if not mid or not title or mid in seen:
                    continue
                seen.add(mid)
                items.append({
                    "id": mid,
                    "title": title,
                    "lang": lang,
                    "date": m.get("release_date") or "",
                    "overview": m.get("overview") or "",
                    "poster_path": m.get("poster_path"),
                })
            if page >= data.get("total_pages", 1):
                break
    return items

def get_platforms(movie_id):
    try:
        data = _tmdb_get(f"/movie/{movie_id}/watch/providers")
        region = data.get("results", {}).get(WATCH_REGION, {})
        names = [p.get("provider_name") for p in region.get("flatrate", []) if p.get("provider_name")]
        return names
    except Exception as e:
        logging.error(f"[OTT] providers {movie_id}: {e}")
        return []

def get_trailer_url(movie_id, title, lang):
    try:
        data = _tmdb_get(f"/movie/{movie_id}/videos")
        for v in data.get("results", []):
            if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                return f"https://www.youtube.com/watch?v={v.get('key')}"
    except Exception as e:
        logging.error(f"[OTT] trailer {movie_id}: {e}")
    q = urllib.parse.quote(f"{title} {lang} official trailer")
    return f"https://www.youtube.com/results?search_query={q}"

def _old_history():
    try:
        if os.path.exists(OLD_HISTORY_FILE):
            with open(OLD_HISTORY_FILE, "r", encoding="utf-8") as f:
                return {l.strip().lower() for l in f if l.strip()}
    except Exception:
        pass
    return set()

async def _already_posted(item, clean_name):
    keys = [f"tmdb:{item['id']}", f"title:{clean_name.lower()}"]
    return await POSTED_COL.find_one({"_id": {"$in": keys}}) is not None

async def _mark_posted(item, clean_name):
    now = datetime.now(timezone.utc)
    for k in (f"tmdb:{item['id']}", f"title:{clean_name.lower()}"):
        await POSTED_COL.update_one({"_id": k}, {"$set": {"title": item["title"], "at": now}}, upsert=True)

async def ensure_baseline(movies):
    """ആദ്യമായി: ഇന്ന് വരെ OTT-ൽ ഉള്ളവ 'seen' ആയി മാർക്ക് ചെയ്യും (പോസ്റ്റ് ചെയ്യില്ല).
    ഇനി മുതൽ പുതുതായി OTT-ൽ വരുന്നവ മാത്രം പോസ്റ്റ് ചെയ്യും."""
    if await META_COL.find_one({"_id": "baseline"}):
        return False
    now = datetime.now(timezone.utc)
    for item in movies:
        clean_name = clean_movie_title(item["title"])
        if clean_name:
            await POSTED_COL.update_one({"_id": f"tmdb:{item['id']}"},
                                        {"$set": {"title": item["title"], "at": now, "baseline": True}}, upsert=True)
    await META_COL.update_one({"_id": "baseline"}, {"$set": {"at": now, "count": len(movies)}}, upsert=True)
    logging.info(f"[OTT] baseline saved: {len(movies)} existing OTT movies skipped")
    return True

# ==============================
# MAIN RUN
# ==============================

async def run_ott_scraper(client: Client, status_msg=None, limit=None):
    if not TMDB_API_KEY:
        if status_msg:
            await status_msg.edit_text("❌ TMDB_API_KEY Render-ൽ സെറ്റ് ചെയ്തിട്ടില്ല.")
        return 0

    async with RUN_LOCK:
        loop = asyncio.get_event_loop()
        movies = await loop.run_in_executor(None, fetch_ott_releases)
        if not movies:
            if status_msg:
                await status_msg.edit_text("❌ OTT റിലീസുകൾ കണ്ടെത്താനായില്ല.")
            return 0

        if await ensure_baseline(movies):
            if status_msg:
                await status_msg.edit_text(
                    f"✅ തുടങ്ങി! ഇതുവരെ OTT-ൽ ഉള്ള {len(movies)} സിനിമകൾ ഒഴിവാക്കി.\n"
                    f"ഇന്ന് മുതൽ പുതുതായി OTT-ൽ വരുന്നവ മാത്രം 9AM / 2PM / 8PM-ന് പോസ്റ്റ് ചെയ്യും."
                )
            return 0

        old = _old_history()
        max_posts = min(limit, OTT_MAX_PER_RUN) if limit else OTT_MAX_PER_RUN
        posted = 0

        for item in movies:
            if posted >= max_posts:
                break
            clean_name = clean_movie_title(item["title"])
            if not clean_name:
                continue
            if clean_name.lower() in old or await _already_posted(item, clean_name):
                continue

            platforms = await loop.run_in_executor(None, get_platforms, item["id"])
            if not platforms:
                continue  # ഇപ്പോൾ OTT-ൽ ഇല്ല

            lang = item["lang"]
            trailer_url = await loop.run_in_executor(None, get_trailer_url, item["id"], clean_name, lang)
            poster_url = f"https://image.tmdb.org/t/p/original{item['poster_path']}" if item.get("poster_path") else None
            platform_txt = ", ".join(platforms[:4])

            caption = (
                f"📢 <b>NEW {lang.upper()} OTT RELEASE</b> 🎬\n\n"
                f"🎞 <b>Movie :</b> {item['title']}\n"
                f"📺 <b>Streaming On :</b> <b>{platform_txt}</b>\n"
                f"🗓 <b>Release :</b> {item.get('date') or 'N/A'}\n"
                f"🗣 <b>Language :</b> {lang}\n\n"
            )
            if item.get("overview"):
                caption += f"📖 <b>Storyline :</b>\n<i>{item['overview'][:300]}...</i>\n\n"
            caption += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💬 <b>Discussion Group :</b> <a href='{GROUP_LINK}'>{GROUP_NAME}</a>\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Search Movie", switch_inline_query_current_chat=clean_name)],
                [InlineKeyboardButton("🎬 Watch Official Trailer 🍿", url=trailer_url)],
                [InlineKeyboardButton("👥 Join Discussion Group 👥", url=GROUP_LINK)],
            ])

            try:
                if poster_url:
                    await client.send_photo(OTT_CHAT_ID, photo=poster_url, caption=caption,
                                            reply_markup=markup, parse_mode=enums.ParseMode.HTML,
                                            disable_notification=True)
                else:
                    await client.send_message(OTT_CHAT_ID, text=caption, reply_markup=markup,
                                              parse_mode=enums.ParseMode.HTML,
                                              disable_notification=True)
                posted += 1
                await _mark_posted(item, clean_name)
                await asyncio.sleep(4)
            except Exception as err:
                logging.error(f"[OTT Send Error]: {err}")
                if status_msg:
                    try:
                        await status_msg.edit_text(f"❌ Group-ലേക്ക് അയക്കാൻ പറ്റിയില്ല: {str(err)[:300]}")
                    except Exception:
                        pass
                return posted

        if status_msg:
            await status_msg.edit_text(f"✅ പൂർത്തിയായി! {posted} പുതിയ OTT റിലീസുകൾ ഗ്രൂപ്പിലേക്ക് അയച്ചു.")
        logging.info(f"[OTT] run done, posted {posted}")
        return posted

# ==============================
# DAILY 3-SLOT LOOP (10 each)
# ==============================

def _last_scheduled_slot(now):
    local = now.astimezone(UAE)
    cands = []
    for d in (0, 1):
        day = (local - timedelta(days=d)).date()
        for h in SLOTS_UAE:
            t = datetime(day.year, day.month, day.day, h, 0, tzinfo=UAE)
            if t <= local:
                cands.append(t)
    return max(cands).astimezone(timezone.utc)

def _get_client():
    if _CLIENT:
        return _CLIENT
    main = sys.modules.get("__main__")
    return getattr(main, "app", None)

async def daily_ott_loop():
    await asyncio.sleep(90)
    while True:
        try:
            client = _get_client()
            if client and not await META_COL.find_one({"_id": "baseline"}):
                await run_ott_scraper(client)   # baseline only, no posts
            now = datetime.now(timezone.utc)
            slot = _last_scheduled_slot(now)
            meta = await META_COL.find_one({"_id": "daily"}) or {}
            last = meta.get("last_run")
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if client and (last is None or last < slot):
                await META_COL.update_one({"_id": "daily"}, {"$set": {"last_run": now}}, upsert=True)
                # slot-ന് 2 മണിക്കൂറിനുള്ളിൽ മാത്രം പോസ്റ്റ് (restart-ൽ പഴയ slot വീണ്ടും ഓടില്ല)
                if now - slot <= timedelta(hours=2):
                    await run_ott_scraper(client, limit=OTT_MAX_PER_RUN)
        except Exception as e:
            logging.error(f"[OTT Loop Error]: {e}")
        await asyncio.sleep(600)  # every 10 min check

def _start_loop_once():
    global _LOOP_STARTED
    if _LOOP_STARTED:
        return
    try:
        asyncio.get_event_loop().create_task(daily_ott_loop())
        _LOOP_STARTED = True
        logging.info(f"[OTT] daily loop started, slots UAE: {SLOTS_UAE}")
    except Exception as e:
        logging.error(f"[OTT] could not start loop: {e}")

# ==============================
# COMMANDS
# ==============================

@Client.on_message(filters.incoming, group=-2)
async def _capture_client(client, message):
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = client
        _start_loop_once()

def _is_admin(message):
    if not message.from_user:
        return False
    ids = {str(a).lstrip("@").lower() for a in ADMINS}
    return str(message.from_user.id) in ids or (message.from_user.username or "").lower() in ids

@Client.on_message(filters.command(["ottnow", "ottping"]), group=-1)
async def manual_ott_cmd(client: Client, message):
    try:
        if not _is_admin(message):
            uid = message.from_user.id if message.from_user else 0
            await message.reply_text(f"⛔ Admin മാത്രം. നിങ്ങളുടെ ID: {uid}")
            return
        if message.command[0].lower() == "ottping":
            meta = await META_COL.find_one({"_id": "daily"}) or {}
            await message.reply_text(
                f"✅ OTT plugin ലോഡ് ആയി.\n"
                f"TMDB key: {'ഉണ്ട്' if TMDB_API_KEY else 'ഇല്ല'}\n"
                f"Post chat: {OTT_CHAT_ID}\n"
                f"Auto loop: {'ON' if _LOOP_STARTED else 'OFF'} (ദിവസവും {', '.join(str(h)+':00' for h in SLOTS_UAE)} UAE, ഓരോ തവണയും {OTT_MAX_PER_RUN})\n"
                f"Last auto run: {meta.get('last_run', '—')}\n"
                f"Baseline: {'ഉണ്ട്' if await META_COL.find_one({'_id': 'baseline'}) else 'ഇല്ല'}"
            )
            return
        msg = await message.reply_text("🔍 പുതിയ OTT റിലീസുകൾ തിരയുന്നു...")
        limit = int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None
        await run_ott_scraper(client, msg, limit=limit)
    except Exception as e:
        logging.exception("[OTT] command failed")
        try:
            await message.reply_text(f"❌ OTT Error: {type(e).__name__}: {str(e)[:300]}")
        except Exception:
            pass
    finally:
        message.stop_propagation()

_start_loop_once()
logging.info(f"[OTT] ott_scraper plugin loaded. TMDB key set: {bool(TMDB_API_KEY)}")
