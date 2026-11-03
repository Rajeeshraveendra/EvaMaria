import logging
from pyrogram import Client, emoji, filters
from pyrogram.errors.exceptions.bad_request_400 import QueryIdInvalid
import asyncio
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery, InlineQueryResultPhoto
from database.ia_filterdb import get_search_results
from utils import is_subscribed, get_size, temp
from info import CACHE_TIME, AUTH_USERS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION

logger = logging.getLogger(__name__)
cache_time = 0 if AUTH_USERS or AUTH_CHANNEL else CACHE_TIME

async def inline_users(query: InlineQuery):
    if AUTH_USERS:
        if query.from_user and query.from_user.id in AUTH_USERS:
            return True
        else:
            return False
    if query.from_user and query.from_user.id not in temp.BANNED_USERS:
        return True
    return False

@Client.on_inline_query()
async def answer(bot, query):
    """Show search results for given inline query"""
    
    if not await inline_users(query):
        await query.answer(results=[],
                           cache_time=0,
                           switch_pm_text='okDa',
                           switch_pm_parameter="hehe")
        return

    if AUTH_CHANNEL and not await is_subscribed(bot, query):
        await query.answer(results=[],
                           cache_time=0,
                           switch_pm_text='🔒 ആദ്യം ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്യൂ',
                           switch_pm_parameter="subscribe")
        return

    results = []
    if '|' in query.query:
        string, file_type = query.query.split('|', maxsplit=1)
        string = string.strip()
        file_type = file_type.strip().lower()
    else:
        string = query.query.strip()
        file_type = None

    offset = int(query.offset or 0)
    reply_markup = get_reply_markup(query=string)
    files, next_offset, total = await get_search_results(string,
                                                  file_type=file_type,
                                                  max_results=10,
                                                  offset=offset)

    # 🎬 Aadya result: poster + IMDb details (cache-il ninnu vegam; 5 sec-il kittiyillenkil ozhivakkum)
    if offset == 0 and files and len(string) >= 2:
        try:
            from plugins.filters import get_search_details, details_block
            from plugins.requests_notify import search_link
            info = await asyncio.wait_for(get_search_details(string, files), timeout=5)
            poster = (info or {}).get("poster")
            if poster and str(poster).startswith("http"):
                cap = details_block(info) + f"📂 <b>{total}</b> files"
                yr = f" ({info.get('year')})" if info.get("year") and info.get("year") != "N/A" else ""
                rt = info.get("rating")
                desc = " · ".join(x for x in [f"⭐ {rt}" if rt and rt != "N/A" else "", info.get("genres") or "", f"{total} files"] if x and x != "N/A")
                results.append(InlineQueryResultPhoto(
                    photo_url=poster, thumb_url=poster, id=f"poster_{offset}",
                    title=f"🎬 {info.get('title')}{yr}", description=desc,
                    caption=cap[:1024], parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Get Files", url=search_link(string))]])))
        except Exception as e:
            logger.error(f"inline poster: {e}")

    try:
        from plugins.filters import btn_name
    except Exception:
        btn_name = lambda n: n

    for file in files:
        title=file.file_name
        size=get_size(file.file_size)
        f_caption=file.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption=f_caption
        if f_caption is None:
            f_caption = f"{file.file_name}"
        results.append(
            InlineQueryResultCachedDocument(
                title=btn_name(file.file_name),
                document_file_id=file.file_id,
                caption=f_caption,
                description=f'《{get_size(file.file_size)}》 {"🔥 " if any(q in (file.file_name or "").lower() for q in ("1080p","2160p","4k")) else ""}{file.file_type or ""}',
                reply_markup=reply_markup))

    if results:
        switch_pm_text = f"{emoji.FILE_FOLDER} Results "
        if string:
            switch_pm_text += f" for {string}"
        try:
            await query.answer(results=results,
                           is_personal = True,
                           cache_time=cache_time,
                           switch_pm_text=switch_pm_text,
                           switch_pm_parameter="start",
                           next_offset=str(next_offset))
        except QueryIdInvalid:
            pass
        except Exception as e:
            logging.exception(str(e))
    else:
        switch_pm_text = f'{emoji.CROSS_MARK} No results'
        if string:
            switch_pm_text += f' for "{string}"'

        await query.answer(results=[],
                           is_personal = True,
                           cache_time=cache_time,
                           switch_pm_text=switch_pm_text,
                           switch_pm_parameter="okay")


def get_reply_markup(query):
    buttons = [
        [
            InlineKeyboardButton('Search again', switch_inline_query_current_chat=query)
        ]
        ]
    return InlineKeyboardMarkup(buttons)




