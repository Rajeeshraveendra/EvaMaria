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

logger = logging.getLogger(__name__)

TARGET_LOG_CHANNEL = "@rrk_temp_db_123"

FORCE_SUB_CHAT = -1001452215783
FORCE_SUB_INVITE_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"

def get_readable_file_size(size_in_bytes):
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

async def auto_delete_group_pair(client, chat_id, user_msg_id, bot_msg_id=None, delay=5):
    """5 സെക്കൻഡിൽ മെസ്സേജ് ഡിലീറ്റ് ചെയ്യുന്നു"""
    await asyncio.sleep(delay)
    if bot_msg_id:
        try:
            await client.delete_messages(chat_id=chat_id, message_ids=bot_msg_id)
        except Exception as e:
            logger.error(f"Bot delete error: {e}")
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=user_msg_id)
    except Exception as e:
        logger.error(f"User delete error: {e}")

async def get_db_spelling_suggestion(query):
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
    except Exception:
        pass
    return None

async def is_subscribed(client, user_id):
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
    except Exception:
        return True
    return False

# group=-1 നൽകി ഏറ്റവും ഉയർന്ന മുൻഗണന ഉറപ്പാക്കുന്നു
@Client.on_message(filters.text, group=-1)
async def pm_group_movie_search(client, message):
    if not message.text:
        return

    text = message.text.strip()
    if text.startswith(("/", "!", "#")):
        return

    if len(text) < 2:
        return

    # മറ്റ് പഴയ ഫയലുകളിലേക്ക് ഈ മെസ്സേജ് പോകുന്നത് ഇവിടെവച്ച് പൂർണ്ണമായി തടയുന്നു!
    message.stop_propagation()

    user = message.from_user
    if not user or user.is_bot:
        return

    query = text
    user_id = user.id
    user_name = user.mention
    is_group = bool(message.chat and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP])

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
            fsub_msg = await message.reply_text(
                text=fsub_text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            if is_group:
                asyncio.create_task(auto_delete_group_pair(client, message.chat.id, message.id, fsub_msg.id, delay=10))
        except Exception:
            pass
        return

    # 2. ഡാറ്റാബേസ് സെർച്ച്
    try:
        files, offset, total_results = await get_search_results(query, max_results=10)
    except Exception as e:
        logger.error(f"Search Query Error: {e}")
        return

    # ഫയലുകൾ ഇല്ലെങ്കിൽ
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
                f"⏳ <i>ഈ മെസ്സേജ് തനിയെ ഡിലീറ്റ് ആവുന്നതാണ്.</i>"
            )
            buttons.append([InlineKeyboardButton(f"🎬 Search: {suggestion}", switch_inline_query_current_chat=suggestion)])
        else:
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
            reply_text = (
                f"❌ <b>Movie Not Found! / സിനിമ കണ്ടെത്താനായില്ല!</b>\n\n"
                f"Hey {user_name},\n"
                f"📌 <b>You Searched :</b> <code>{query}</code>\n\n"
                f"💡 <b>Please check the spelling and send again.</b>\n\n"
                f"⏳ <i>ഈ മെസ്സേജ് തനിയെ ഡിലീറ്റ് ആവുന്നതാണ്.</i>"
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
            del_delay = 5 if is_group else 60
            asyncio.create_task(auto_delete_group_pair(client, message.chat.id, message.id, not_found_msg.id, delay=del_delay))
        except Exception:
            pass
        return

    # 3. ഗ്രൂപ്പിൽ അയച്ചയുടൻ കൺഫർമേഷൻ അയച്ച് 5 സെക്കൻഡിൽ ഡിലീറ്റ് ചെയ്യുന്നു
    if is_group:
        try:
            btn = [[InlineKeyboardButton("📥 Check Your PM", url=f"https://t.me/{temp.U_NAME}")]]
            grp_confirm_msg = await message.reply_text(
                f"✅ {user_name}, താങ്കൾ ആവശ്യപ്പെട്ട സിനിമയുടെ ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയച്ചിട്ടുണ്ട്!",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            asyncio.create_task(auto_delete_group_pair(client, message.chat.id, message.id, grp_confirm_msg.id, delay=5))
        except Exception as err:
            logger.error(f"Group confirm error: {err}")

    # 4. ഫയലുകൾ ഇൻബോക്സിലേക്ക് (PM) അയക്കുന്നു
    sent_count = 0
    blocked_or_not_started = False

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
            f"📥 <b>കൂടുതൽ സിനിമകൾക്കായി ജോയിൻ ചെയ്യൂ:</b>\n"
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

    # യൂസർ ബോട്ട് PM-ൽ സ്റ്റാർട്ട് ചെയ്തിട്ടില്ലെങ്കിൽ മുന്നറിയിപ്പ്
    if blocked_or_not_started:
        if is_group:
            btn = [[InlineKeyboardButton("🍿 Start Bot in PM", url=f"https://t.me/{temp.U_NAME}?start=start")]]
            warn_msg = await message.reply_text(
                f"ഹലോ {user_name}, സിനിമ ഇൻബോക്സിലേക്ക് അയക്കാൻ താഴെ കാണുന്ന ബട്ടൺ വഴി ബോട്ട് <b>Start</b> ചെയ്യുക!",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            asyncio.create_task(auto_delete_group_pair(client, message.chat.id, message.id, warn_msg.id, delay=10))
        return

    # 5. ഇൻബോക്സിലേക്ക് താങ്ക്സ് മെസ്സേജ്
    if sent_count > 0:
        thanks_text = (
            f"🍿 <b>താങ്കൾ തിരഞ്ഞ ഫയലുകൾ ഇൻബോക്സിൽ അയച്ചിട്ടുണ്ട്!</b>\n\n"
            f"💖 <i>RRK Movies AutoBot ഉപയോഗിച്ചതിന് നന്ദി. ഹാപ്പി വാച്ചിംഗ്!</i>\n\n"
            f"കൂടുതൽ പുതിയ സിനിമകൾക്കും അപ്‌ഡേറ്റുകൾക്കുമായി ഞങ്ങളുടെ ചാനലിൽ ജോയിൻ ചെയ്യുക."
        )
        thanks_buttons = [
            [
                InlineKeyboardButton("📢 Main Channel", url=FORCE_SUB_INVITE_LINK),
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519")
            ],
            [InlineKeyboardButton("🔍 Search More Movies", switch_inline_query_current_chat="")]
        ]
        try:
            await client.send_message(
                chat_id=user_id,
                text=thanks_text,
                reply_markup=InlineKeyboardMarkup(thanks_buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

    # ലോഗ് ചാനലിലേക്ക് വിവരങ്ങൾ അയക്കുന്നു
    if sent_count > 0:
        try:
            req_in = message.chat.title if (message.chat and message.chat.title) else "PM"
            user_full = f"<a href='tg://user?id={user_id}'>{user.first_name}</a>"
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
        except Exception:
            pass

# Movie Request ബട്ടൺ ഹാൻഡ്‌ലർ
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
                    new_row.append(InlineKeyboardButton("✅ Requested", callback_data="already_requested"))
                else:
                    new_row.append(btn)
            new_buttons.append(new_row)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex("^already_requested$"))
async def already_requested_handler(client, query):
    await query.answer("ഈ സിനിമ ഇതിനകം അഡ്മിനോട് റിക്വസ്റ്റ് ചെയ്തിട്ടുണ്ട്!", show_alert=False)

# Help, About, Home ബട്ടൺ ഹാൻഡ്‌ലർ
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
            f"📱 <b>Phone :</b> <code>+971562769519</code>"
        )
        buttons = [
            [
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519"),
                InlineKeyboardButton("📢 Main Group", url=FORCE_SUB_INVITE_LINK)
            ],
            [InlineKeyboardButton("🔙 Back / പിന്നോട്ട്", callback_data="home")]
        ]
        if query.message.photo:
            await query.message.edit_caption(caption=help_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        else:
            await query.message.edit_text(text=help_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

    elif data == "about":
        about_text = (
            f"🤖 <b>About Bot / ബോട്ടിനെക്കുറിച്ച്</b>\n\n"
            f"⚡ <b>Bot Name :</b> RRK Movies AutoBot\n"
            f"👤 <b>Created By :</b> Rajeesh Raveendra Kamballur\n"
            f"📱 <b>Contact :</b> <code>+971562769519</code>\n"
            f"🎬 <b>Channel :</b> @RRK_Movies\n"
            f"🛠 <b>Language :</b> Python 3\n"
            f"📦 <b>Database :</b> MongoDB"
        )
        buttons = [
            [
                InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519"),
                InlineKeyboardButton("📢 Join Channel", url=FORCE_SUB_INVITE_LINK)
            ],
            [InlineKeyboardButton("🔙 Back / പിന്നോട്ട്", callback_data="home")]
        ]
        if query.message.photo:
            await query.message.edit_caption(caption=about_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        else:
            await query.message.edit_text(text=about_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

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
            await query.message.edit_caption(caption=home_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        else:
            await query.message.edit_text(text=home_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
