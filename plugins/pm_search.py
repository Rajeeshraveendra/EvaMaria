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
    """ഫയൽ സൈസ് MB / GB ഫോർമാറ്റിലേക്ക് മാറ്റുന്നു"""
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

async def auto_delete_messages(user_msg, bot_msg, delay=60):
    """നിശ്ചിത സമയത്തിന് ശേഷം തെറ്റായ റിക്വസ്റ്റും ബോട്ടിന്റെ മറുപടിയും തനിയെ ഡിലീറ്റ് ചെയ്യുന്നു"""
    await asyncio.sleep(delay)
    try:
        await bot_msg.delete()
    except Exception:
        pass
    try:
        await user_msg.delete()
    except Exception:
        pass

async def get_db_spelling_suggestion(query):
    """ഡാറ്റാബേസിൽ നിന്ന് ഏറ്റവും അനുയോജ്യമായ സിനിമയുടെ പേര് കണ്ടെത്തുന്നു"""
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
    """യൂസർ മെയിൻ ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്തിട്ടുണ്ടോ എന്ന് പരിശോധിക്കുന്നു"""
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

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def admin_broadcast_handler(client, message):
    """അഡ്മിന് എല്ലാ ബോട്ട് ഉപയോക്താക്കൾക്കും സന്ദേശങ്ങൾ അയക്കാനുള്ള സംവിധാനം"""
    if not message.reply_to_message:
        await message.reply_text("⚠ <b>ഉപയോഗിക്കേണ്ട വിധം:</b>\nഎല്ലാ യൂസർമാർക്കും അയക്കേണ്ട മെസ്സേജിന് റിപ്ലൈ ആയി <code>/broadcast</code> എന്ന് അയക്കുക.")
        return

    broadcast_msg = message.reply_to_message
    status_msg = await message.reply_text("🚀 <b>ബ്രോഡ്കാസ്റ്റിംഗ് ആരംഭിക്കുന്നു...</b>\nദയവായി കാത്തിരിക്കുക.")

    users_list = await db.get_all_users()
    total_users = await db.total_users_count()

    successful = 0
    blocked = 0
    deleted = 0
    failed = 0

    async for user in users_list:
        user_id = user.get("id")
        try:
            await broadcast_msg.copy(chat_id=user_id)
            successful += 1
            await asyncio.sleep(0.3)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await broadcast_msg.copy(chat_id=user_id)
            successful += 1
        except UserIsBlocked:
            await db.delete_user(user_id)
            blocked += 1
        except InputUserDeactivated:
            await db.delete_user(user_id)
            deleted += 1
        except Exception:
            failed += 1

    report = (
        f"✅ <b>ബ്രോഡ്കാസ്റ്റ് പൂർത്തിയായി!</b>\n\n"
        f"👥 <b>ആകെ ഉപയോക്താക്കൾ:</b> <code>{total_users}</code>\n"
        f"📬 <b>വിജയകരമായി അയച്ചത്:</b> <code>{successful}</code>\n"
        f"🚫 <b>ബ്ലോക്ക് ചെയ്ത അക്കൗണ്ടുകൾ:</b> <code>{blocked}</code>\n"
        f"❌ <b>ഡിലീറ്റ് ചെയ്ത അക്കൗണ്ടുകൾ:</b> <code>{deleted}</code>\n"
        f"⚠️ <b>പരാജയപ്പെട്ടവ:</b> <code>{failed}</code>"
    )
    await status_msg.edit_text(report, parse_mode=enums.ParseMode.HTML)

@Client.on_message((filters.private | filters.group) & filters.text & ~filters.command(["start", "help", "about", "users", "stats", "connect", "filter", "del", "delall", "channel", "logs", "delete", "deleteall", "settings", "set_template", "broadcast"]), group=-1)
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

    # 1. FORCE SUBSCRIBE പരിശോധന
    subscribed = await is_subscribed(client, user_id)

    if not subscribed:
        btn = [
            [InlineKeyboardButton("📢 Join Main Group / ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്യുക", url=FORCE_SUB_INVITE_LINK)],
            [InlineKeyboardButton("🔄 Try Again / വീണ്ടും ശ്രമിക്കുക", url=f"https://t.me/{temp.U_NAME}?start=start")]
        ]
        fsub_text = (
            f"👋 ഹലോ {user_name},\n\n"
            f"⚠ <b>സിനിമകൾ ഡൗൺലോഡ് ചെയ്യുന്നതിനായി ആദ്യം ഞങ്ങളുടെ മെയിൻ ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്യേണ്ടതാണ്!</b>\n\n"
            f"താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്ത് ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്ത ശേഷം വീണ്ടും സിനിമയുടെ പേര് അയക്കുക."
        )
        try:
            await message.reply_text(
                text=fsub_text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
        return

    # 2. ഡാറ്റാബേസിൽ നിന്ന് ഫയലുകൾ തിരയുന്നു
    try:
        files, offset, total_results = await get_search_results(query, max_results=10)
    except Exception as e:
        print(f"[SEARCH ERROR]: {e}")
        logger.error(f"Search Query Error: {e}")
        return

    # ഫയലുകൾ ലഭ്യമല്ലെങ്കിൽ
    if not files:
        suggestion = await get_db_spelling_suggestion(query)
        buttons = []
        req_data = f"req_{query[:40]}"

        if suggestion and suggestion.lower() != query.lower():
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"താങ്കൾ തിരഞ്ഞത്: <code>{query}</code>\n\n"
                f"🤔 <b>നിങ്ങൾ ഉദ്ദേശിച്ചത് ഇതാണോ? (Did you mean):</b>\n"
                f"👉 <b>{suggestion}</b>\n\n"
                f"<i>താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്ത് സിനിമ തിരയാവുന്നതാണ്. അല്ലെങ്കിൽ അഡ്മിനോട് റിക്വസ്റ്റ് ചെയ്യാം.</i>\n\n"
                f"⏳ <i>ഈ മെസ്സേജ് 60 സെക്കൻഡിൽ തനിയെ ഡിലീറ്റ് ആകുന്നതാണ്.</i>"
            )
            buttons.append([InlineKeyboardButton(f"🎬 Search: {suggestion}", switch_inline_query_current_chat=suggestion)])
        else:
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Hey {user_name},\n"
                f"📌 <b>You Searched :</b> <code>{query}</code>\n\n"
                f"💡 <b>Please check the spelling and send again.</b>\n"
                f"<i>(ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക)</i>\n\n"
                f"👉 സിനിമ ലഭ്യമല്ലെങ്കിൽ താഴെയുള്ള ബട്ടൺ വഴി അഡ്മിനോട് റിക്വസ്റ്റ് ചെയ്യാം.\n\n"
                f"⏳ <i>ഈ മെസ്സേജ് 60 സെക്കൻഡിൽ തനിയെ ഡിലീറ്റ് ആകുന്നതാണ്.</i>"
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
            asyncio.create_task(auto_delete_messages(message, not_found_msg, delay=60))
        except Exception:
            pass
        return

    sent_count = 0
    blocked_or_not_started = False

    # 3. ഉപയോക്താവിന് ഫയലുകൾ അയക്കുന്നു
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
            f"📥 <b>കൂടുതൽ മൂവികൾക്കായി ജോയിൻ ചെയ്യൂ:</b>\n"
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

    # ഫയലുകൾ അയച്ചു കഴിഞ്ഞ ഉടൻ PM-ലേക്ക് കസ്റ്റം നന്ദി മെസ്സേജ്
    if sent_count > 0:
        thanks_text = (
            f"🍿 <b>താങ്കൾ തിരഞ്ഞ ഫയലുകൾ വിജയകരമായി അയച്ചിട്ടുണ്ട്!</b>\n"
            f"🎉 <i>നിങ്ങൾ ചോദിച്ച സിനിമയുടെ ഫയലുകൾ തരാൻ കഴിഞ്ഞതിൽ വളരെ സന്തോഷം.</i>\n\n"
            f"💡 <i>നിങ്ങളുടെ വിലയേറിയ നിർദ്ദേശങ്ങളും തെറ്റുകളും (Suggestions & Mistakes) ഉണ്ടെങ്കിൽ അഡ്മിനെ അറിയിക്കുക.</i>\n\n"
            f"💖 <i>RRK Movies AutoBot ഉപയോഗിച്ചതിന് നന്ദി. ഹാപ്പി വാച്ചിംഗ്!</i>\n\n"
            f"കൂടുതൽ പുതിയ സിനിമകൾക്കും അപ്‌ഡേറ്റുകൾക്കുമായി ഞങ്ങളുടെ ചാനലിൽ ജോയിൻ ചെയ്യുക."
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

    # ഗ്രൂപ്പിലാണെങ്കിൽ അറിയിപ്പ് നൽകുന്നു
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and sent_count > 0:
        btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
        await message.reply_text(
            f"✅ {user_name}, താങ്കൾ ആവശ്യപ്പെട്ട സിനിമയുടെ ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയച്ചിട്ടുണ്ട്!",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )

    # ലോഗ് ചാനലിലേക്ക് അയക്കുന്നു
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

# Movie Request ബട്ടൺ ക്ലിക്ക് ചെയ്യുമ്പോൾ പ്രവർത്തിക്കുന്ന ഹാൻഡ്‌ലർ
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

    await query.answer("✅ താങ്കളുടെ റിക്വസ്റ്റ് അഡ്മിന് ലഭിച്ചിട്ടുണ്ട്! സിനിമ ഉടൻ അപ്‌ലോഡ് ചെയ്യുന്നതാണ്.", show_alert=True)

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
    await query.answer("ഈ സിനിമ ഇതിനകം അഡ്മിനോട് റിക്വസ്റ്റ് ചെയ്തിട്ടുണ്ട്!", show_alert=False)

# Help, About, Home ബട്ടണുകളുടെ Callback Query Handler
@Client.on_callback_query(filters.regex("^(help|about|home)$"))
async def cb_help_about_handler(client, query):
    data = query.data
    user_name = query.from_user.mention

    if data == "help":
        help_text = (
            f"ℹ <b>സഹായം / Help Guide</b>\n\n"
            f"ഹലോ {user_name},\n\n"
            f"1. സിനിമ ലഭിക്കാൻ സിനിമയുടെ പേര് കൃത്യമായ സ്പെല്ലിംഗിൽ അയക്കുക.\n"
            f"2. ഫയലുകൾ ഡൗൺലോഡ് ചെയ്യുന്നതിന് മുൻപ് ഞങ്ങളുടെ മെയിൻ ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്തിരിക്കണം.\n\n"
            f"📞 <b>Admin Contact / ബന്ധപ്പെടാൻ:</b>\n"
            f"👤 <b>Admin :</b> Rajeesh Raveendra Kamballur\n"
            f"📱 <b>Phone :</b> <code>+971562769519</code>\n"
            f"💬 എന്തെങ്കിലും സംശയങ്ങളോ സഹായമോ ആവശ്യമുണ്ടെങ്കിൽ നേരിട്ട് ബന്ധപ്പെടാം."
        )
        buttons = [
            [
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519"),
                InlineKeyboardButton("📢 Main Group", url=FORCE_SUB_INVITE_LINK)
            ],
            [InlineKeyboardButton("🔙 Back / പിന്നോട്ട്", callback_data="home")]
        ]
        if query.message.photo:
            await query.message.edit_caption(
                caption=help_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await query.message.edit_text(
                text=help_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    elif data == "about":
        about_text = (
            f"🤖 <b>About Bot / ബോട്ടിനെക്കുറിച്ച്</b>\n\n"
            f"⚡ <b>Bot Name :</b> RRK Movies AutoBot\n"
            f"👤 <b>Created By :</b> Rajeesh Raveendra Kamballur\n"
            f"📱 <b>Contact :</b> <code>+971562769519</code>\n"
            f"🎬 <b>Channel :</b> @RRK_Movies\n"
            f"🛠 <b>Language :</b> Python 3\n"
            f"📦 <b>Database :</b> MongoDB\n\n"
            f"<i>HD സിനിമകൾ വേഗത്തിൽ ലഭ്യമാക്കാൻ നിർമ്മിച്ചത്.</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519"),
                InlineKeyboardButton("📢 Join Channel", url=FORCE_SUB_INVITE_LINK)
            ],
            [InlineKeyboardButton("🔙 Back / പിന്നോട്ട്", callback_data="home")]
        ]
        if query.message.photo:
            await query.message.edit_caption(
                caption=about_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await query.message.edit_text(
                text=about_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    elif data == "home":
        home_text = (
            f"തിയേറ്റർ പ്രിന്റുകളോട് വിട പറയാം! ഇനി സിനിമകൾ കാണാം Full HD ക്വാളിറ്റിയിൽ മാത്രം. 🍿🎬\n\n"
            f"✅ <b>എന്തുകൊണ്ട് ഞങ്ങളുടെ ഗ്രൂപ്പ്?</b>\n\n"
            f"🚫 തിയേറ്റർ പ്രിന്റുകൾ ഇല്ല\n"
            f"💎 ശുദ്ധമായ HD മൂവീസ് മാത്രം\n"
            f"⚡ ഫാസ്റ്റ് ഡൗൺലോഡ് ലിങ്കുകൾ\n\n"
            f"📥 ഇപ്പോൾ തന്നെ ജോയിൻ ചെയ്യൂ:\n"
            f"👉 {FORCE_SUB_INVITE_LINK}"
        )
        buttons = [
            [InlineKeyboardButton("➕ Add Me To Your Groups ➕", url=f"http://t.me/{temp.U_NAME}?startgroup=true")],
            [InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🤖 Updates", url=FORCE_SUB_INVITE_LINK)],
            [InlineKeyboardButton("ℹ Help", callback_data="help"), InlineKeyboardButton("😊 About", callback_data="about")]
        ]
        if query.message.photo:
            await query.message.edit_caption(
                caption=home_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await query.message.edit_text(
                text=home_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
