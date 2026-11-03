# 🎬 Similar Movies: TMDB recommendations, bot DB-yil files ullava maathram
import os
import re
import time
import asyncio
import logging
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import get_search_results

logger = logging.getLogger(__name__)
TMDB_KEY = os.environ.get("TMDB_API_KEY", "")
_CACHE = {}          # imdb_id -> (ts, [(title, year)])
MAX_SHOW = 8


def _get(url):
    try:
        r = requests.get(url, timeout=8)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def tmdb_similar(imdb_id):
    if not TMDB_KEY:
        return []
    f = _get(f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_KEY}&external_source=imdb_id")
    res = (f.get("movie_results") or [])
    kind = "movie"
    if not res:
        res = f.get("tv_results") or []
        kind = "tv"
    if not res:
        return []
    tid = res[0]["id"]
    out, seen = [], set()
    for ep in ("recommendations", "similar"):
        for page in (1, 2):
            d = _get(f"https://api.themoviedb.org/3/{kind}/{tid}/{ep}?api_key={TMDB_KEY}&page={page}")
            for m in d.get("results") or []:
                t = m.get("title") or m.get("name") or ""
                y = (m.get("release_date") or m.get("first_air_date") or "")[:4]
                k = t.lower()
                if t and k not in seen:
                    seen.add(k)
                    out.append((t, y))
            if len(out) >= 40:
                return out
    return out


def _clean(t):
    t = t.replace("&", "and")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


async def available(title):
    q = _clean(title)
    if len(q) < 2:
        return False
    try:
        r = await get_search_results(q, max_results=1)
        files = r[0] if isinstance(r, tuple) else r
        return bool(files)
    except Exception:
        return False


@Client.on_callback_query(filters.regex(r"^similar#"))
async def similar_cb(client, query: CallbackQuery):
    from plugins.auto_post import search_link
    from plugins.filters import colorize
    imdb_id = query.data.split("#", 1)[1]
    await query.answer("🎬 സമാന സിനിമകൾ തിരയുന്നു...")
    hit = _CACHE.get(imdb_id)
    if hit and time.time() - hit[0] < 86400:
        found = hit[1]
    else:
        cands = await asyncio.get_event_loop().run_in_executor(None, tmdb_similar, imdb_id)
        found = []
        for t, y in cands:
            if await available(t):
                found.append((t, y))
                if len(found) >= MAX_SHOW:
                    break
        if len(_CACHE) > 300:
            _CACHE.clear()
        _CACHE[imdb_id] = (time.time(), found)
    if not found:
        return await query.message.reply_text("🎬 ഇതുപോലെയുള്ള സിനിമകൾ ഇപ്പോൾ ബോട്ടിൽ ലഭ്യമല്ല.")
    btn = [[InlineKeyboardButton(f"🎬 {t}" + (f" ({y})" if y else ""), url=search_link(_clean(t)))]
           for t, y in found]
    text = "🎬 <b>Similar Movies</b>\n<i>ബോട്ടിൽ ലഭ്യമായവ മാത്രം. ഒരെണ്ണം തിരഞ്ഞെടുക്കൂ 👇</i>"
    m = await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn),
                                       parse_mode=enums.ParseMode.HTML)
    await colorize(m, btn)
