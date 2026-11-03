# 🎲 Surprise Me (random movie) + 📊 admin daily status report
import re
import sys
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from info import ADMINS, COLLECTION_NAME
from database.ia_filterdb import db, get_search_results
from database.users_chats_db import db as udb

logger = logging.getLogger(__name__)
FILES = db[COLLECTION_NAME]
DSTATS = db["daily_stats"]
SEARCH = db["search_stats"]
UAE = timezone(timedelta(hours=4))
REPORT_HOUR_UAE = 22          # ella divasavum 10 PM UAE
_CLIENT = None
_STARTED = False


# ============================================================
# 🎲 SURPRISE ME
# ============================================================
async def pick_random_title():
    from plugins.auto_post import extract_movie_info, SERIES_RE
    try:
        docs = await FILES.aggregate([{"$sample": {"size": 25}}]).to_list(25)
    except Exception as e:
        logger.error(f"surprise sample: {e}")
        return None
    random.shuffle(docs)
    for d in docs:
        name = d.get("file_name") or ""
        if SERIES_RE.search(name):
            continue
        title, year = extract_movie_info(name)
        if title and title != "Movie" and len(title) >= 2:
            return f"{title} {year}" if year else title
    return None


async def send_surprise(client, message):
    from plugins.filters import build_file_buttons, send_result, filter_row, cbd
    for _ in range(3):
        q = await pick_random_title()
        if not q:
            continue
        files, offset, total = await get_search_results(q, offset=0, filter=True)
        if not files:
            files, offset, total = await get_search_results(re.sub(r"\s(19|20)\d{2}$", "", q), offset=0, filter=True)
        if not files:
            continue
        pat = re.escape(q).replace("\\ ", " ")
        btn = build_file_buttons(files)
        if offset != "":
            pages = (total + 9) // 10
            btn.append([InlineKeyboardButton(f"📚 Page 1/{pages}", callback_data="pages_info"),
                        InlineKeyboardButton("Next ⏩", callback_data=cbd("next_", pat, f"_{offset}_1"))])
        if total > 1:
            btn.append([InlineKeyboardButton("📤 Send All Files", callback_data=cbd("sendall#", pat))])
        btn.append([InlineKeyboardButton("🎲 Surprise Again", callback_data="surprise")])
        return await send_result(message, q, files, total, btn)
    await message.reply_text("🎲 ഇപ്പോൾ ഒരു സിനിമ കണ്ടെത്താനായില്ല, ഒന്നുകൂടി ശ്രമിക്കൂ.")


@Client.on_message(filters.command(["surprise", "random"]) & filters.incoming)
async def surprise_cmd(client, message):
    _remember(client)
    await send_surprise(client, message)


@Client.on_callback_query(filters.regex(r"^surprise$"))
async def surprise_cb(client, query: CallbackQuery):
    _remember(client)
    await query.answer("🎲 ഒരു സിനിമ തിരഞ്ഞെടുക്കുന്നു...")
    await send_surprise(client, query.message)


# ============================================================
# 📊 STATUS REPORT
# ============================================================
async def collect_stats():
    now = datetime.now(UAE)
    today = now.strftime("%Y-%m-%d")
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    users = await udb.total_users_count()
    chats = await udb.total_chat_count()
    files = await FILES.estimated_document_count()
    utc_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    searches = 0
    try:
        async for r in SEARCH.find({"day": utc_day}):
            searches += int(r.get("n", 0))
    except Exception:
        pass
    await DSTATS.update_one({"_id": today}, {"$set": {"users": users, "files": files, "chats": chats}}, upsert=True)
    prev = await DSTATS.find_one({"_id": yday}) or {}
    new_u = users - prev["users"] if "users" in prev else None
    new_f = files - prev["files"] if "files" in prev else None
    top = []
    try:
        from plugins.trending import top_searches
        top = await top_searches(days=1, limit=3)
    except Exception:
        pass
    f = lambda v: f"+{v}" if v is not None and v >= 0 else ("—" if v is None else str(v))
    t = (f"📊 <b>RRK Movies Status</b> — {now.strftime('%d %b %Y, %I:%M %p')} UAE\n\n"
         f"👥 Users: <b>{users}</b> (ഇന്ന് {f(new_u)})\n"
         f"💬 Groups: <b>{chats}</b>\n"
         f"🎬 Files: <b>{files}</b> (ഇന്ന് {f(new_f)})\n"
         f"🔍 ഇന്നത്തെ searches: <b>{searches}</b>\n")
    if top:
        t += "\n🔥 Top ഇന്ന്: " + ", ".join(f"{x.get('name')} ({x.get('n')})" for x in top)
    return t


@Client.on_message(filters.command("status") & filters.user(ADMINS))
async def status_cmd(client, message):
    _remember(client)
    try:
        await message.reply_text(await collect_stats(), parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"Status error: {e}")


def _get_client():
    if _CLIENT:
        return _CLIENT
    return getattr(sys.modules.get("__main__"), "app", None)


def _remember(client):
    global _CLIENT
    _CLIENT = client
    _start_once()


async def daily_report_loop():
    await asyncio.sleep(120)
    while True:
        try:
            now = datetime.now(UAE)
            today = now.strftime("%Y-%m-%d")
            meta = await DSTATS.find_one({"_id": "report_meta"}) or {}
            client = _get_client()
            if client and now.hour >= REPORT_HOUR_UAE and meta.get("last") != today:
                await DSTATS.update_one({"_id": "report_meta"}, {"$set": {"last": today}}, upsert=True)
                text = await collect_stats()
                for a in ADMINS:
                    try:
                        await client.send_message(a, text, parse_mode=enums.ParseMode.HTML)
                    except Exception as e:
                        logger.error(f"status report to {a}: {e}")
            elif now.hour < REPORT_HOUR_UAE and now.minute < 10:
                await collect_stats()   # snapshot for tomorrow's diff (silent)
        except Exception as e:
            logger.error(f"daily report loop: {e}")
        await asyncio.sleep(600)


def _start_once():
    global _STARTED
    if _STARTED:
        return
    try:
        asyncio.get_event_loop().create_task(daily_report_loop())
        _STARTED = True
    except Exception as e:
        logger.error(f"report loop start: {e}")


_start_once()
