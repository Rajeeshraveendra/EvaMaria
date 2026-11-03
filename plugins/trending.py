# 🔥 Trending: ഏറ്റവും കൂടുതൽ തിരഞ്ഞ സിനിമകൾ (കഴിഞ്ഞ 7 ദിവസം)
import re
import asyncio
import logging
import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import db
from plugins.requests_notify import search_link

logger = logging.getLogger(__name__)
STATS = db["search_stats"]


def _key(q):
    q = re.sub(r"\b(19|20)\d{2}\b", " ", str(q or ""))
    return re.sub(r"[^a-z0-9]+", "", q.lower())


async def record_search(query):
    """Files kandethiya search maathram count cheyyunnu"""
    k = _key(query)
    if len(k) < 3:
        return
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    name = re.sub(r"\s+", " ", str(query)).strip().title()[:40]
    try:
        await STATS.update_one({"_id": f"{day}:{k}"},
                               {"$inc": {"n": 1}, "$set": {"k": k, "name": name, "day": day}},
                               upsert=True)
    except Exception as e:
        logger.error(f"trending save: {e}")


async def top_searches(days=7, limit=10):
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=days - 1)).strftime("%Y-%m-%d")
    pipe = [
        {"$match": {"day": {"$gte": since}}},
        {"$group": {"_id": "$k", "n": {"$sum": "$n"}, "name": {"$last": "$name"}}},
        {"$sort": {"n": -1}},
        {"$limit": limit},
    ]
    try:
        return [d async for d in STATS.aggregate(pipe)]
    except Exception as e:
        logger.error(f"trending read: {e}")
        return []


async def trending_text():
    rows = await top_searches()
    if not rows:
        return "🔥 <b>Trending</b>\n\nഇതുവരെ ഡാറ്റ ഇല്ല. കുറച്ച് കഴിഞ്ഞ് നോക്കൂ.", None
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🔥 <b>ഈ ആഴ്ച ഏറ്റവും കൂടുതൽ തിരഞ്ഞ സിനിമകൾ</b>\n<i>Trending this week</i>\n"]
    btn = []
    for i, r in enumerate(rows):
        m = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{m} <b>{r['name']}</b>  —  🔍 {r['n']}")
        btn.append([InlineKeyboardButton(f"{m} {r['name']}", url=search_link(r["name"]))])
    return "\n".join(lines), btn


@Client.on_message(filters.command("trending") & filters.incoming)
async def trending_cmd(client, message):
    from plugins.filters import colorize
    text, btn = await trending_text()
    m = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn) if btn else None,
                                 parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    if btn:
        await colorize(m, btn)


@Client.on_callback_query(filters.regex(r"^trending$"))
async def trending_cb(client, query: CallbackQuery):
    from plugins.filters import colorize
    text, btn = await trending_text()
    await query.answer()
    m = await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn) if btn else None,
                                       parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    if btn:
        await colorize(m, btn)
