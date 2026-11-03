# 🎁 Invite friends: referral link, count, Top Inviters + share helpers
import logging
import urllib.parse
from datetime import datetime, timezone
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import db
from utils import temp

logger = logging.getLogger(__name__)
REFS = db["referrals"]          # {_id: new_user_id, by: inviter_id, ts}
GROUP_LINK = "https://t.me/+Z_FD__rQ7bc3NDQ8"


def share_url(text=None, link=None):
    link = link or f"https://t.me/{temp.U_NAME or 'RRK_Movies_AutoBot'}"
    text = text or "🎬 പുതിയ മലയാളം സിനിമകൾ HD-യിൽ, സൗജന്യമായി! ഈ ബോട്ട് ഒന്ന് നോക്കൂ 👇"
    return "https://t.me/share/url?" + urllib.parse.urlencode({"url": link, "text": text})


def share_row():
    return [InlineKeyboardButton("📤 Friends-നു Share ചെയ്യൂ", url=share_url()),
            InlineKeyboardButton("🎁 Invite", callback_data="invite")]


def ref_link(uid):
    return f"https://t.me/{temp.U_NAME or 'RRK_Movies_AutoBot'}?start=ref_{uid}"


async def credit_referral(client, new_uid, param):
    """Puthiya user ref_ link vazhi vannal inviter-nu credit"""
    global _CLIENT
    _CLIENT = client
    try:
        if not param or not param.startswith("ref_"):
            return
        by = int(param[4:])
        if by == new_uid:
            return
        await REFS.update_one({"_id": new_uid},
                              {"$setOnInsert": {"by": by, "ts": datetime.now(timezone.utc)}}, upsert=True)
        n = await REFS.count_documents({"by": by})
        try:
            await temp_client_send(by, f"🎉 താങ്കളുടെ invite link വഴി ഒരു പുതിയ സുഹൃത്ത് ജോയിൻ ചെയ്തു! ആകെ: <b>{n}</b>")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"referral credit: {e}")


_CLIENT = None


async def temp_client_send(uid, text):
    if _CLIENT:
        await _CLIENT.send_message(uid, text, parse_mode=enums.ParseMode.HTML)


async def top_inviters(limit=10):
    pipe = [{"$group": {"_id": "$by", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": limit}]
    return await REFS.aggregate(pipe).to_list(limit)


async def invite_text(client, uid):
    n = await REFS.count_documents({"by": uid})
    link = ref_link(uid)
    t = (f"🎁 <b>സുഹൃത്തുക്കളെ ക്ഷണിക്കൂ!</b>\n\n"
         f"താങ്കളുടെ invite link:\n<code>{link}</code>\n\n"
         f"👥 താങ്കൾ ക്ഷണിച്ചവർ: <b>{n}</b>\n\n")
    top = await top_inviters(5)
    if top:
        t += "🏆 <b>Top Inviters</b>\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(top):
            name = str(r["_id"])
            try:
                u = await client.get_users(r["_id"])
                name = u.first_name or name
            except Exception:
                pass
            t += f"{medals[i]} {name} — {r['n']}\n"
    btn = [[InlineKeyboardButton("📤 Link Share ചെയ്യൂ",
                                 url=share_url("🎬 മലയാളം സിനിമകൾ HD-യിൽ! ഈ ബോട്ട് ഉപയോഗിക്കൂ 👇", link))],
           [InlineKeyboardButton("🎬 Movies Group", url=GROUP_LINK)]]
    return t, btn


@Client.on_message(filters.command(["invite", "refer"]) & filters.incoming)
async def invite_cmd(client, message):
    global _CLIENT
    _CLIENT = client
    if not message.from_user:
        return
    from plugins.filters import colorize
    t, btn = await invite_text(client, message.from_user.id)
    m = await message.reply_text(t, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML,
                                 disable_web_page_preview=True)
    await colorize(m, btn)


@Client.on_callback_query(filters.regex(r"^invite$"))
async def invite_cb(client, query: CallbackQuery):
    global _CLIENT
    _CLIENT = client
    from plugins.filters import colorize
    await query.answer()
    t, btn = await invite_text(client, query.from_user.id)
    m = await query.message.reply_text(t, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML,
                                       disable_web_page_preview=True)
    await colorize(m, btn)
