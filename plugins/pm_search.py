import logging
import asyncio
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, UserNotParticipant
from database.ia_filterdb import get_search_results
from utils import temp

logger = logging.getLogger(__name__)

TARGET_LOG_CHANNEL = "@rrk_temp_db_123"

# നൽകിയ ഗ്രൂപ്പ് ഐഡിയും ഇൻവൈറ്റ് ലിങ്കും
FORCE_SUB_CHAT = -1001452215783
FORCE_SUB_INVITE_LINK = "https://t.me/+NoL3OkqPwBtiZjY0"

async def is_subscribed(client, user_id):
    """യൂസർ മെയിൻ ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്തിട്ടുണ്ടോ എന്ന് സുരക്ഷിതമായി പരിശോധിക്കുന്നു"""
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
        if chat_type == enums.ChatType.PRIVATE:
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}+movie+spelling"
            buttons = [
                [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_url)],
                [InlineKeyboardButton("🎬 Join Channel / Releases", url=FORCE_SUB_INVITE_LINK)]
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

    # 3. ഉപയോക്താവിന് ഫയലുകൾ അയക്കുന്നു
    for doc in files:
        file_id = getattr(doc, "file_id", None) or (doc.get("file_id") if isinstance(doc, dict) else None)
        file_name = getattr(doc, "file_name", "Movie File") if hasattr(doc, "file_name") else (doc.get("file_name", "Movie File") if isinstance(doc, dict) else "Movie File")

        if not file_id:
            continue

        caption = (
            f"🎬 <b>File Name:</b> <code>{file_name}</code>\n\n"
            f"⚡ <b>Uploaded By:</b> @RRK_Movies\n\n"
            f"📥 <b>ഇപ്പോൾ തന്നെ ജോയിൻ ചെയ്യൂ:</b>\n"
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
            f"2. ഫയലുകൾ ഡൗൺലോഡ് ചെയ്യുന്നതിന് മുൻപ് ഞങ്ങളുടെ മെയിൻ ഗ്രൂപ്പിൽ ജോയിൻ ചെയ്തിരിക്കണം.\n"
            f"3. എന്തെങ്കിലും സംശയങ്ങളുണ്ടെങ്കിൽ അഡ്മിനുമായി ബന്ധപ്പെടുക."
        )
        buttons = [
            [InlineKeyboardButton("📢 Main Group", url=FORCE_SUB_INVITE_LINK)],
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
            f"🎬 <b>Channel :</b> @RRK_Movies\n"
            f"🛠 <b>Language :</b> Python 3\n"
            f"📦 <b>Database :</b> MongoDB\n\n"
            f"<i>HD സിനിമകൾ വേഗത്തിൽ ലഭ്യമാക്കാൻ നിർമ്മിച്ചത്.</i>"
        )
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=FORCE_SUB_INVITE_LINK)],
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
