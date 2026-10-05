import logging
import asyncio
import urllib.parse
import difflib
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, UserNotParticipant, FloodWait, InputUserDeactivated
from database.ia_filterdb import get_search_results, Media
from database.users_chats_db import db
from utils import temp
from info import ADMINS

logger = logging.getLogger(__name__)

TARGET_LOG_CHANNEL = "@rrk_temp_db_123"

FORCE_SUB_CHAT = -1001452215783
FORCE_SUB_INVITE_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"

def get_readable_file_size(size_in_bytes):
    """File size MB / GB format-ilekku maattunnu"""
    if not size_in_bytes:
        return "N/A"
    try:
        size = float(size_in_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    except Exception:
        return "N/A"

async def auto_delete_pair(user_msg, bot_msg, delay=5):
    """Groupil privacy urappakkaan nishchitha samayathil delete cheyyunnu"""
    await asyncio.sleep(delay)
    if bot_msg:
        try:
            await bot_msg.delete()
        except Exception:
            pass
    if user_msg:
        try:
            await user_msg.delete()
        except Exception:
            pass

async def get_db_spelling_suggestion(query):
    """Database-il ninnu cinemayude peru thirayunnu"""
    try:
        first_char = query.strip()[0]
        cursor = Media.find({"file_name": {"$regex": f"^{first_char}", "$options": "i"}}).limit(50)
        file_list = await cursor.to_list(length=50)
        
        movie_titles = []
        for f in file_list:
            name = f.get("file_name", "")
            clean = name.replace(".", " ").replace("_", " ").split()[0:3]
            movie_titles.append(" ".join(clean))
            
        if movie_titles:
            matches = difflib.get_close_matches(query, movie_titles, n=1, cutoff=0.4)
            if matches:
                return matches[0]
    except Exception as e:
        logger.warning(f"Suggestion DB Error: {e}")
    return None

async def is_subscribed(client, user_id):
    """User main groupil join cheythittundo ennu nokkunnu"""
    try:
        member = await client.get_chat_member(chat_id=FORCE_SUB_CHAT, user_id=user_id)
        if member.status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER
        ]:
            return True
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.warning(f"Force Sub Error: {e}")
        return True
    return False

# Group=-100 nalki priority kootunnu, mattu files interfere cheyyilla
@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template", "broadcast"]), group=-100)
async def pm_group_movie_search(client, message):
    if not message.text or message.text.startswith(("/", "!", "#")):
        return
    if message.from_user and message.from_user.is_bot:
        return

    query = message.text.strip()
    if len(query) < 2:
        return

    # Matte filter plugins execute aakathirikkan propagation stop cheyyunnu
    message.stop_propagation()

    chat_type = message.chat.type

    if not message.from_user:
        return

    user_id = message.from_user.id
    user_name = message.from_user.mention

    # 1. FORCE SUBSCRIBE PARISHODHANA
    subscribed = await is_subscribed(client, user_id)

    if not subscribed:
        btn = [
            [InlineKeyboardButton("📢 Join Main Group / ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്യുക", url=FORCE_SUB_INVITE_LINK)],
            [InlineKeyboardButton("🔄 Try Again / വീണ്ടും ശ്രമിക്കുക", url=f"https://t.me/{temp.U_NAME}?start=start")]
        ]
        fsub_text = (
            f"👋 Hello {user_name},\n\n"
            f"⚠ <b>Cinemakal download cheyyunnathinaayi aadyam njangalude Main Groupil join cheyyendathaannu!</b>\n\n"
            f"Thaazheyulla button click cheythu groupil join cheytha shesham veendum cinemayude peru ayakkuka."
        )
        try:
            fsub_msg = await message.reply_text(
                text=fsub_text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                asyncio.create_task(auto_delete_pair(message, fsub_msg, delay=10))
        except Exception:
            pass
        return

    # 2. DATABASE SEARCH
    try:
        files, offset, total_results = await get_search_results(query, max_results=10)
    except Exception as e:
        print(f"[SEARCH ERROR]: {e}")
        logger.error(f"Search Query Error: {e}")
        return

    # Files illatha avastha
    if not files:
        suggestion = await get_db_spelling_suggestion(query)
        buttons = []
        req_data = f"req_{query[:40]}"

        if suggestion and suggestion.lower() != query.lower():
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Thaankal thiranju: <code>{query}</code>\n\n"
                f"🤔 <b>Ningal uddheshichathu ithano? (Did you mean):</b>\n"
                f"👉 <b>{suggestion}</b>\n\n"
                f"⏳ <i>Ee message thaniye delete aakunna thaanu.</i>"
            )
            buttons.append([InlineKeyboardButton(f"🎬 Search: {suggestion}", switch_inline_query_current_chat=suggestion)])
        else:
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Hey {user_name},\n"
                f"📌 <b>You Searched :</b> <code>{query}</code>\n\n"
                f"💡 <b>Please check the spelling and send again.</b>\n\n"
                f"⏳ <i>Ee message thaniye delete aakunna thaanu.</i>"
            )
            buttons.append([InlineKeyboardButton("🔍 Check Spelling on Google", url=google_url)])

        buttons.append([InlineKeyboardButton("📩 Request to Admin / റിക്വസ്റ്റ് ചെയ്യുക", callback_data=req_data)])
        buttons.append([InlineKeyboardButton("📢 Main Channel / Updates", url=FORCE_SUB_INVITE_LINK)])

        try:
            not_found_msg = await message.reply_text(
                text=reply_text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            del_time = 5 if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else 60
            asyncio.create_task(auto_delete_pair(message, not_found_msg, delay=del_time))
        except Exception:
            pass
        return

    sent_count = 0
    blocked_or_not_started = False

    # 3. USER-KKU PM-IL FILES AYAKKUNNU
    for doc in files:
        file_id = getattr(doc, "file_id", None) or (doc.get("file_id") if isinstance(doc, dict) else None)
        file_name = getattr(doc, "file_name", "Movie File") if hasattr(doc, "file_name") else (doc.get("file_name", "Movie File") if isinstance(doc, dict) else "Movie File")
        file_size_raw = getattr(doc, "file_size", None) or (doc.get("file_size") if isinstance(doc, dict) else None)
        readable_size = get_readable_file_size(file_size_raw)

        if not file_id:
            continue

        caption = (
            f"🎬 <b>Title:</b> <code>{file_name}</code>\n\n"
            f"💾 <b>Size:</b> <code>{readable_size}</code>\n"
            f"⚡ <b>Uploaded By:</b> @RRK_Movies\n\n"
            f"📥 <b>Kooduthal movies-naayi join cheyyuu:</b>\n"
            f"👉 {FORCE_SUB_INVITE_LINK}"
        )

        try:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file_id,
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
            sent_count += 1
            await asyncio.sleep(1.0)
        except (UserIsBlocked, PeerIdInvalid):
            blocked_or_not_started = True
            break
        except Exception as e:
            logger.error(f"Send File Error: {e}")

    # User bot start cheythittillaenkil
    if blocked_or_not_started:
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            btn = [[InlineKeyboardButton("🍿 Start Bot in PM", url=f"https://t.me/{temp.U_NAME}?start=start")]]
            warn_msg = await message.reply_text(
                f"Hello {user_name}, cinema inbox-ilekku ethikkaan thaazhe kaanunna button click cheythu bot <b>Start</b> cheyyuka!",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            asyncio.create_task(auto_delete_pair(message, warn_msg, delay=10))
        return

    # 4. PM-LEKKU THANK YOU MESSAGE
    if sent_count > 0:
        thanks_text = (
            f"🍿 <b>Thaankal thiranja fayalukal vijayakaramaayi ayachittundu!</b>\n"
            f"🎉 <i>Ningal chodicha cinemayude fayalukal tharan kazhinjathil valare santhosham.</i>\n\n"
            f"💡 <i>Ningalude vilayeriya nirdheshangalum thettukalum (Suggestions & Mistakes) undenkil admin-e ariyikkuka.</i>\n\n"
            f"💖 <i>RRK Movies AutoBot upayogichathinu nandi. Happy Watching!</i>\n\n"
            f"Kooduthal puthiya cinemakalkkum updates-numaayi njangalude channel-il join cheyyuka."
        )
        thanks_buttons = [
            [
                InlineKeyboardButton("📢 Main Channel", url=FORCE_SUB_INVITE_LINK),
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519")
            ],
            [
                InlineKeyboardButton("🔍 Search More Movies", switch_inline_query_current_chat="")
            ]
        ]
        try:
            await client.send_message(
                chat_id=user_id,
                text=thanks_text,
                reply_markup=InlineKeyboardMarkup(thanks_buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as err:
            logger.warning(f"Thanks msg error: {err}")

    # 5. GROUP-IL CONFIRMATION + 5 SECOND-IL AUTO DELETE
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and sent_count > 0:
        btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
        grp_confirm_msg = await message.reply_text(
            f"✅ {user_name}, thaankal aavashyappetta cinemayude files inboxilekku (PM) ayachittundu!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        asyncio.create_task(auto_delete_pair(message, grp_confirm_msg, delay=5))

    # Log channel-ilekku details
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
        except Exception as log_err:
            logger.error(f"Channel Log Sending Failed: {log_err}")

# Movie Request callback handler
@Client.on_callback_query(filters.regex(r"^req_"))
async def movie_request_handler(client, query):
    user = query.from_user
    movie_name = query.data.split("req_", 1)[1]

    try:
        user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        username_str = f"(@{user.username})" if user.username else ""
        log_text = (
            f"📩 <b>#MovieRequest</b>\n\n"
            f"🎬 <b>Movie:</b> <code>{movie_name}</code>\n"
            f"👤 <b>User:</b> {user_link} {username_str}\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>"
        )
        await client.send_message(
            chat_id=TARGET_LOG_CHANNEL,
            text=log_text,
            parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Request Log Error: {e}")

    await query.answer("✅ Thaankalude request admin-u labhichittundu! Cinema udan upload cheyyunnathaanu.", show_alert=True)

    try:
        new_buttons = []
        for row in query.message.reply_markup.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("req_"):
                    new_row.append(InlineKeyboardButton("✅ Requested / റിക്വസ്റ്റ് ചെയ്തു", callback_data="already_requested"))
                else:
                    new_row.append(btn)
            new_buttons.append(new_row)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex("^already_requested$"))
async def already_requested_handler(client, query):
    await query.answer("Ee cinema ithinakam adminodu request cheythittundu!", show_alert=False)
