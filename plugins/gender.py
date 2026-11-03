# മോനെ / മോളെ വിളി - user ഒരിക്കൽ തിരഞ്ഞെടുക്കും, Mongo-യിൽ സൂക്ഷിക്കും
import logging
import motor.motor_asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, CallbackQuery
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)
GENDER_DB = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)[DATABASE_NAME]["user_gender"]
_CACHE = {}

WORDS = {
    #      വിളി (vocative), കർത്താവ് (nominative), ന്റെ (possessive)
    "m": ("മോനെ", "", ""),
    "f": ("മോളെ", "", ""),
    None: ("ചങ്ങാതീ", "", ""),
}


async def get_gender(uid):
    if not uid:
        return None
    if uid in _CACHE:
        return _CACHE[uid]
    try:
        d = await GENDER_DB.find_one({"_id": uid})
        g = d.get("g") if d else None
    except Exception as e:
        logger.error(f"gender read: {e}")
        return None
    _CACHE[uid] = g
    return g


async def words(uid):
    """(vili, karthavu, possessive) tuple"""
    return WORDS.get(await get_gender(uid), WORDS[None])


async def gender_row(uid):
    """Gender ariyillenkil chodikkan oru button row; ariyamenkil None"""
    if await get_gender(uid):
        return None
    return [InlineKeyboardButton("👦 Male", callback_data="setg#m"),
            InlineKeyboardButton("👧 Female", callback_data="setg#f")]


@Client.on_callback_query(filters.regex(r"^setg#[mf]$"))
async def set_gender(client, query: CallbackQuery):
    g = query.data.split("#")[1]
    uid = query.from_user.id
    try:
        await GENDER_DB.update_one({"_id": uid}, {"$set": {"g": g}}, upsert=True)
    except Exception as e:
        logger.error(f"gender save: {e}")
        return await query.answer("⚠️ Error, try again", show_alert=True)
    _CACHE[uid] = g
    await query.answer(f"ശരി {WORDS[g][0]} 😊 ഇനി അങ്ങനെ വിളിക്കാം!", show_alert=True)
    # gender button row മാറ്റുന്നു
    try:
        rows = query.message.reply_markup.inline_keyboard if query.message.reply_markup else []
        rows = [r for r in rows if not any((b.callback_data or "").startswith("setg#") for b in r)]
        from pyrogram.types import InlineKeyboardMarkup
        from plugins.filters import colorize
        await query.message.edit_reply_markup(InlineKeyboardMarkup(rows) if rows else None)
        if rows:
            await colorize(query.message, rows)
    except Exception:
        pass
