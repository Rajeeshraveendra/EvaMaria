import logging
import asyncio
import urllib.parse
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
from database.ia_filterdb import get_search_results
from utils import temp

logger = logging.getLogger(__name__)

TARGET_LOG_CHANNEL = "@rrk_temp_db_123"
TMDB_API_KEY = "2e7a02b66d8e2023cb2bcbb678b8e0b2"

async def get_hd_poster(movie_title):
    """TMDb-യിൽ നിന്ന് ഒറിജിനൽ ക്വാളിറ്റി HD പോസ്റ്റർ എടുക്കുന്നു"""
    try:
        clean_title = urllib.parse.quote(movie_title.strip())
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={clean_title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results")
                    if results and results[0].get("poster_path"):
                        return f"https://image.tmdb.org/t/p/original{results[0].get('poster_path')}"
    except Exception as e:
        logger.error(f"Error fetching HD poster: {e}")
    return None

@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template"]), group=-1)
async def pm_group_movie_search(client, message):
    if not message.text or message.text.startswith(("/", "!", "#")):
        return
    if message.from_user and message.from_user.is_bot:
        return

    query = message.text.strip()
    if len(query) < 2:
        return

    user_id = message.from_user.id
    user_name = message.from_user.mention
    chat_type = message.chat.type

    # ഡാറ്റാബേസിൽ നിന്ന് ഫയലുകൾ തിരയുന്നു
    try:
        files, offset, total_results = await get_search_results(query, max_results=10)
    except Exception as e:
        print(f"[SEARCH ERROR]: {e}")
        logger.error(f"Search Query Error: {e}")
        return

    # ഫയലുകൾ ലഭ്യമല്ലെങ്കിൽ
    if not files:
        if chat_type == enums.ChatType.PRIVATE:
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
            buttons = [
                [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_url)],
                [InlineKeyboardButton("🎬 Join Channel / Releases", url="https://t.me/+NoL3OkqPwBtiZjY0")]
            ]
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Hey {user_name},\n"
                f"📌 <b>You Searched :</b> <code>{query}</code>\n\n"
                f"💡 <b>Please check the spelling and send again.</b>\n"
                f"<i>(ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക)</i>\n\n"
                f"👉 <b>Example / ഉദാഹരണം :</b> <i>Drishyam, Manjummel Boys</i>"
            )
            try:
                await message.reply_text(
                    text=reply_text,
                    quote=True,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass
        return

    sent_count = 0
    blocked_or_not_started = False

    # 1. ആദ്യം സിനിമയുടെ HD പോസ്റ്റർ യൂസർക്ക് അയക്കുന്നു
    try:
        poster_url = await get_hd_poster(query)
        if poster_url:
            poster_caption = (
                f"🎬 <b>{query.title()}</b>\n\n"
                f"⚡ <b>Uploaded By:</b> @RRK_Movies\n"
                f"📥 ഫയലുകൾ താഴെ വരുന്നുണ്ട്, ദയവായി കാത്തിരിക്കുക..."
            )
            await client.send_photo(
                chat_id=user_id,
                photo=poster_url,
                caption=poster_caption,
                parse_mode=enums.ParseMode.HTML
            )
            await asyncio.sleep(1)
    except (UserIsBlocked, PeerIdInvalid):
        blocked_or_not_started = True
    except Exception as e:
        logger.warning(f"Could not send poster: {e}")

    # 2. തുടർന്ന് സിനിമയുടെ ഫയലുകൾ അയക്കുന്നു
    if not blocked_or_not_started:
        for doc in files:
            file_id = getattr(doc, "file_id", None) or (doc.get("file_id") if isinstance(doc, dict) else None)
            file_name = getattr(doc, "file_name", "Movie File") if hasattr(doc, "file_name") else (doc.get("file_name", "Movie File") if isinstance(doc, dict) else "Movie File")

            if not file_id:
                continue

            caption = (
                f"🎬 <b>File Name:</b> <code>{file_name}</code>\n\n"
                f"⚡ <b>Uploaded By:</b> @RRK_Movies\n\n"
                f"📥 <b>ഇപ്പോൾ തന്നെ ജോയിൻ ചെയ്യൂ:</b>\n"
                f"👉 https://t.me/+NoL3OkqPwBtiZjY0"
            )

            try:
                await client.send_cached_media(
                    chat_id=user_id,
                    file_id=file_id,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML
                )
                sent_count += 1
                await asyncio.sleep(1.2)
            except (UserIsBlocked, PeerIdInvalid):
                blocked_or_not_started = True
                break
            except Exception as e:
                logger.error(f"Send File Error: {e}")

    # യൂസർ ബോട്ട് PM-ൽ സ്റ്റാർട്ട് ചെയ്തിട്ടില്ലെങ്കിൽ
    if blocked_or_not_started:
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            btn = [[InlineKeyboardButton("🍿 Start Bot in PM", url=f"https://t.me/{temp.U_NAME}?start=start")]]
            await message.reply_text(
                f"ഹലോ {user_name}, സിനിമ നിങ്ങളുടെ ഇൻബോക്സിലേക്ക് അയക്കാൻ താഴെ കാണുന്ന ബട്ടൺ ക്ലിക്ക് ചെയ്ത് ബോട്ട് <b>Start</b> ചെയ്യുക!",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        return

    # ഗ്രൂപ്പിലാണെങ്കിൽ അറിയിപ്പ് നൽകുന്നു
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and sent_count > 0:
        btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
        await message.reply_text(
            f"✅ {user_name}, താങ്കൾ ആവശ്യപ്പെട്ട സിനിമയുടെ ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയച്ചിട്ടുണ്ട്!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )

    # ലോഗ് ചാനലിലേക്ക് കൃത്യമായി #FileSentToPM അയക്കുന്നു
    if sent_count > 0:
        try:
            req_in = message.chat.title if (message.chat and message.chat.title) else "PM"
            user_full = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
            log_text = (
                f"📁 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> {req_in}\n"
                f"👤 <b>User:</b> {user_full}\n"
                f"({user_id})\n"
                f"🔍 <b>Query:</b> <code>{query}</code>\n"
                f"📦 <b>Files Sent:</b> {sent_count}"
            )
            await client.send_message(
                chat_id=TARGET_LOG_CHANNEL,
                text=log_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            print(f"[LOG SUCCESS] Sent log to {TARGET_LOG_CHANNEL}")
        except Exception as log_err:
            print(f"[LOG ERROR DETAILED]: {repr(log_err)}")
            logger.error(f"Channel Log Sending Failed: {log_err}")
