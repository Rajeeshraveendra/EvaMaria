"""Search notices: a fixed reply for searches of a film that is not out yet.

Mongo `search_notices`: {_id, pattern (regex), text (HTML)}.
A notice shows only while no file in the DB matches its pattern,
so it stops by itself once the real file is uploaded.

Admin:
  /setnotice <regex> | <message>
  /delnotice <regex>
  /notices
"""
import re
import time
from pyrogram import Client, filters, enums
from database.ia_filterdb import db
from info import ADMINS, COLLECTION_NAME

NOTICE_DB = db["search_notices"]
FILES_DB = db[COLLECTION_NAME]
_cache = {"t": 0, "items": []}

DEFAULTS = [{
    "_id": r"jailer[\s._-]*2",
    "pattern": r"jailer[\s._-]*2",
    "text": (
        "🎬 <b>Jailer 2</b>\n\n"
        "ജയിലർ 2-ന്റെ നല്ല പ്രിന്റ് <b>നവംബർ 12</b>-ന് മാത്രമേ ലഭ്യമാകൂ. ദയവായി കാത്തിരിക്കുക 🙏\n\n"
        "Jailer 2 good quality print will be available only on <b>November 12</b>. Please wait 🙏"
    ),
}]


async def _items():
    if time.time() - _cache["t"] < 60:
        return _cache["items"]
    try:
        if not _cache["t"]:
            for d in DEFAULTS:
                await NOTICE_DB.update_one({"_id": d["_id"]}, {"$setOnInsert": d}, upsert=True)
        _cache["items"] = [n async for n in NOTICE_DB.find({})]
    except Exception as e:
        print(f"Notice DB error: {e}")
    _cache["t"] = time.time()
    return _cache["items"]


async def get_notice(query):
    """Return notice HTML if the query matches one and no file for it exists yet."""
    q = str(query or "")
    for n in await _items():
        try:
            if not re.search(n["pattern"], q, re.I):
                continue
            if await FILES_DB.count_documents({"file_name": {"$regex": n["pattern"], "$options": "i"}}, limit=1):
                continue
            return n["text"]
        except Exception as e:
            print(f"Notice check error: {e}")
    return None


@Client.on_message(filters.command("setnotice") & filters.user(ADMINS))
async def set_notice(bot, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return await message.reply_text("Usage: <code>/setnotice regex | message</code>", parse_mode=enums.ParseMode.HTML)
    pat, text = [x.strip() for x in parts[1].split("|", 1)]
    try:
        re.compile(pat)
    except re.error as e:
        return await message.reply_text(f"❌ Bad pattern: {e}")
    await NOTICE_DB.update_one({"_id": pat}, {"$set": {"pattern": pat, "text": text}}, upsert=True)
    _cache["t"] = 0
    await message.reply_text(f"✅ Notice saved for <code>{pat}</code>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("delnotice") & filters.user(ADMINS))
async def del_notice(bot, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: <code>/delnotice regex</code>", parse_mode=enums.ParseMode.HTML)
    r = await NOTICE_DB.delete_one({"_id": parts[1].strip()})
    _cache["t"] = 0
    await message.reply_text("✅ Removed" if r.deleted_count else "❌ Not found")


@Client.on_message(filters.command("notices") & filters.user(ADMINS))
async def list_notices(bot, message):
    items = [n async for n in NOTICE_DB.find({})]
    if not items:
        return await message.reply_text("No notices.")
    await message.reply_text("\n".join(f"• <code>{n['pattern']}</code>" for n in items), parse_mode=enums.ParseMode.HTML)
