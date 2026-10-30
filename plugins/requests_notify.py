import re
import base64
import asyncio
import logging
import datetime
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import db
from info import CHANNELS
from utils import temp

logger = logging.getLogger(__name__)

# ============================================================
# MOVIE REQUEST NOTIFY
# ഒരാൾ ചോദിച്ച സിനിമ ചാനലിൽ അപ്‌ലോഡ് ആകുമ്പോൾ ബോട്ട് അയാൾക്ക് PM അയക്കുന്നു
# ============================================================
REQ_DB = db["movie_requests"]


def req_key(name):
    name = re.sub(r"\b(19|20)\d{2}\b", " ", str(name or ""))
    return re.sub(r"[^a-z0-9]+", "", name.lower())


async def add_request(user_id, movie_name):
    """Request MongoDB-യിൽ സേവ് ചെയ്യുന്നു. True = സേവ് ആയി"""
    key = req_key(movie_name)
    if len(key) < 3 or not user_id:
        return False
    try:
        await REQ_DB.update_one(
            {"_id": f"{user_id}:{key}"},
            {"$set": {
                "user_id": int(user_id),
                "key": key,
                "name": str(movie_name)[:60],
                "at": datetime.datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"Request save error: {e}")
        return False


def search_link(name):
    q = str(name)[:40]
    token = base64.urlsafe_b64encode(q.encode()).decode().rstrip("=")
    return f"https://t.me/{temp.U_NAME or 'RRK_Movies_AutoBot'}?start=search_{token}"


# group=5: auto_post.py-യിലെ ഹാൻഡ്‌ലറിനെ ബാധിക്കാതെ കൂടെ റൺ ചെയ്യുന്നു
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video), group=5)
async def notify_requesters(client, message):
    media = message.document or message.video
    if not media:
        return
    fname = getattr(media, "file_name", None) or (message.caption or "")
    fkey = re.sub(r"[^a-z0-9]+", "", str(fname).lower())
    if not fkey:
        return

    try:
        pending = await REQ_DB.find({}).to_list(length=3000)
    except Exception as e:
        logger.error(f"Request read error: {e}")
        return

    for r in pending:
        key = r.get("key")
        if not key or key not in fkey:
            continue
        # ഒരേ സിനിമയുടെ പല ഫയലുകൾ വന്നാലും ഒരാൾക്ക് ഒരു മെസേജ് മാത്രം
        doc = await REQ_DB.find_one_and_delete({"_id": r["_id"]})
        if not doc:
            continue

        name = doc.get("name", "Movie")
        text = (
            f"🎉 <b>സന്തോഷവാർത്ത! / Good news!</b>\n\n"
            f"🎬 നിങ്ങൾ ചോദിച്ച <b>{name}</b> ഇപ്പോൾ ലഭ്യമാണ്!\n"
            f"<i>The movie you requested is now available.</i>\n\n"
            f"👇 <i>താഴെയുള്ള ബട്ടൺ അമർത്തി ഫയലുകൾ എടുക്കൂ / Tap below to get the files</i>"
        )
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Get Files", url=search_link(name))]])
        for _ in range(2):
            try:
                await client.send_message(doc["user_id"], text, reply_markup=btn,
                                          parse_mode=enums.ParseMode.HTML)
                break
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
            except Exception as e:
                # ബോട്ട് സ്റ്റാർട്ട് ചെയ്യാത്തവർ / ബ്ലോക്ക് ചെയ്തവർ
                logger.info(f"Request notify failed for {doc.get('user_id')}: {e}")
                break
        await asyncio.sleep(0.3)
