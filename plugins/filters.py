import io
import re
import asyncio
import logging
import json
import urllib.request
import urllib.parse
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import get_search_results, get_file_details
from database.connections_mdb import active_connection
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from info import BOT_TOKEN, ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, PICS, LOG_CHANNEL
from plugins.requests_notify import add_request
from plugins.auto_post import extract_movie_info, get_imdb_details, lang_hint_from_name, fetch_json

logger = logging.getLogger(__name__)

USER_GRP_MSGS = {}
OMDB_API_KEY = "97960898"

# ============================================================
# DUAL AUTO-SUGGESTION ENGINE (Google + OMDb)
# ============================================================
async def get_smart_suggestions(query):
    """Google & OMDb ഉപയോഗിച്ച് ഇംഗ്ലീഷിലും മലയാളത്തിലുമുള്ള കൃത്യമായ പേരുകൾ കണ്ടെത്തുന്നു"""
    loop = asyncio.get_event_loop()
    def fetch():
        suggestions = []
        cleaned_query = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
        if not cleaned_query:
            return []

        # 1. Google Autocomplete API
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urllib.parse.quote(cleaned_query + ' movie')}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode('utf-8'))
                if len(data) > 1:
                    for item in data[1]:
                        item_clean = re.sub(r'(?i)\b(movie|film|full movie|download|malayalam|tamil|watch online)\b', '', item).strip()
                        if item_clean and item_clean.lower() not in [s.lower() for s in suggestions]:
                            suggestions.append(item_clean.title())
        except Exception:
            pass

        # 2. OMDb API ബാക്കപ്പ്
        if len(suggestions) < 4:
            try:
                omdb_url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={urllib.parse.quote(cleaned_query)}&type=movie"
                req2 = urllib.request.Request(omdb_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=4) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    for m in res.get("Search", []):
                        title = m.get("Title")
                        if title and title.lower() not in [s.lower() for s in suggestions]:
                            suggestions.append(title)
            except Exception:
                pass

        return suggestions[:6]

    return await loop.run_in_executor(None, fetch)


# ============================================================
# HELPER TAG FUNCTIONS
# ============================================================
def get_audio_tag(name):
    n = name.lower()
    audios = []
    if any(x in n for x in ['malayalam', 'mal']):
        audios.append('Mal')
    if any(x in n for x in ['tamil', 'tam']):
        audios.append('Tam')
    if any(x in n for x in ['hindi', 'hin']):
        audios.append('Hin')
    if any(x in n for x in ['telugu', 'tel']):
        audios.append('Tel')
    if any(x in n for x in ['kannada', 'kan']):
        audios.append('Kan')
    if any(x in n for x in ['english', 'eng']):
        audios.append('Eng')
    if 'multi' in n:
        return 'Multi'
    if 'dual' in n:
        return 'Dual'
    return "/".join(audios) if audios else ""

def get_quality_tag(name):
    n = name.lower()
    if '2160p' in n or '4k' in n:
        return '4K'
    if '1080p' in n:
        return '1080p'
    if '720p' in n:
        return '720p'
    if '480p' in n:
        return '480p'
    if 'hdrip' in n:
        return 'HDRip'
    return ""


# ============================================================
# LANGUAGE / QUALITY FILTER HELPERS
# ============================================================
LANG_FILTERS = {
    "ml": ("Malayalam", r"(malayalam|mal)\b"),
    "ta": ("Tamil", r"(tamil|tam)\b"),
    "te": ("Telugu", r"(telugu|tel)\b"),
    "hi": ("Hindi", r"(hindi|hin)\b"),
    "kn": ("Kannada", r"(kannada|kan)\b"),
    "en": ("English", r"(english|eng)\b"),
}
QUAL_FILTERS = {
    "480": ("480p", r"480p"),
    "720": ("720p", r"720p"),
    "1080": ("1080p", r"1080p"),
    "4k": ("4K", r"(2160p|4k)"),
}


def cbd(prefix, text, suffix=""):
    """Telegram callback_data 64 bytes-ൽ കൂടാതെ നോക്കുന്നു"""
    text = str(text)
    while text and len(f"{prefix}{text}{suffix}".encode()) > 64:
        text = text[:-1]
    return f"{prefix}{text}{suffix}"


def btn_name(raw_name):
    """ബട്ടണിൽ മുഴുവൻ പേര് കാണിക്കാൻ: [tags], @handles, ._- മാറ്റുന്നു"""
    n = re.sub(r'\[[^\]]*\]', ' ', raw_name or '')
    n = re.sub(r'(?i)@(?!rrk_movies\b)\w+', ' ', n)
    n = re.sub(r'(?i)\b(?:www\.)\S+', ' ', n)
    n = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', n.strip(), flags=re.I)
    n = re.sub(r'[_.]+', ' ', n)
    n = re.sub(r'\s*-\s*', ' - ', n)
    n = re.sub(r'\s+', ' ', n).strip(' -')
    if len(n) > 60:
        n = n[:58] + '..'
    return n or (raw_name or '')


def build_file_buttons(files):
    btn = []
    for file in files:
        label = f"《{get_size(file.file_size)}》 {btn_name(file.file_name)}"
        btn.append([InlineKeyboardButton(label, url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}")])
    return btn


def result_header(text, total_results, page=1, label=""):
    total_pages = max(1, (total_results + 9) // 10)
    head = (
        f"🍂 <b>Movie Name :</b> <code>{text}</code>\n"
        f"🗳 <b>Total Results :</b> <code>{total_results}</code>\n"
        f"📚 <b>Total Pages :</b> <code>{page}/{total_pages}</code>\n"
    )
    if label:
        head += f"🔎 <b>Filter :</b> {label}\n"
    head += "\n🔻 <b>Tap On The File Button Below And Then Start To Download</b> 🔻"
    return head


# ============================================================
# SEARCH RESULT: IMDb DETAILS (poster, rating, story)
# ============================================================
IMDB_CACHE = {}


def _norm(t):
    return re.sub(r"[^a-z0-9]+", "", str(t or "").lower())


def pick_movie(query, files):
    """Thettaya movie details varaathirikkan: query-yude athe peru ulla file
    undenkil athu; illenkil ella file-um ore movie aanenkil athu; allenkil None"""
    q = _norm(re.sub(r"\b(19|20)\d{2}\b", "", query))
    found = []
    for f in files:
        title, year = extract_movie_info(f.file_name)
        if title != "Movie":
            found.append((title, year, lang_hint_from_name(f.file_name)))
    exact = [x for x in found if _norm(x[0]) == q]
    pool = exact or (found if len({_norm(x[0]) for x in found}) == 1 else [])
    if not pool:
        return None, None, None
    year = next((x[1] for x in pool if x[1]), None)
    lang = next((x[2] for x in pool if x[2]), None)
    return pool[0][0], year, lang


def details_match(info, title, year, lang):
    """IMDb-il ninnu kittiya movie sherikkum ithu thanneyano ennu urappikkunnu"""
    if not info or _norm(info.get("title")) != _norm(title):
        return False
    iy = re.search(r"(19|20)\d{2}", str(info.get("year") or ""))
    if year:
        return bool(iy) and abs(int(iy.group(0)) - int(year)) <= 1
    if lang:
        return lang.lower() in str(info.get("language") or "").lower()
    return False


async def get_search_details(query, files):
    title, year, lang = pick_movie(query, files)
    if not title:
        return None
    key = f"{_norm(title)}_{year}"
    if key in IMDB_CACHE:
        return IMDB_CACHE[key]
    info = None
    try:
        info = await asyncio.wait_for(get_imdb_details(title, year, lang), timeout=12)
        if info and info.get("imdb_id"):
            def plot():
                try:
                    d = fetch_json(f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={info['imdb_id']}&plot=short")
                    p = d.get("Plot")
                    return p if p and p != "N/A" else None
                except Exception:
                    return None
            info["plot"] = await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, plot), timeout=8)
    except Exception as e:
        logger.error(f"Search IMDb error: {e}")
    if not details_match(info, title, year, lang):
        info = None
    if len(IMDB_CACHE) > 300:
        IMDB_CACHE.clear()
    IMDB_CACHE[key] = info
    return info


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def details_block(info):
    if not info or not info.get("title"):
        return ""
    ok = lambda v: v and str(v) != "N/A"
    t = f"🎬 <b>{_esc(info['title'])}</b>"
    if ok(info.get("year")):
        t += f" ({_esc(info['year'])})"
    t += "\n"
    if ok(info.get("rating")):
        t += f"⭐ <b>IMDb :</b> {_esc(info['rating'])}/10\n"
    if ok(info.get("genres")):
        t += f"🎭 <b>Genre :</b> {_esc(info['genres'])}\n"
    if ok(info.get("language")):
        t += f"🗣 <b>Language :</b> {_esc(info['language'])}\n"
    if ok(info.get("runtime")):
        t += f"⏱ <b>Runtime :</b> {_esc(info['runtime'])}\n"
    if ok(info.get("plot")):
        p = info["plot"]
        if len(p) > 300:
            p = p[:297].rsplit(" ", 1)[0] + "..."
        t += f"📖 <b>Story :</b> <i>{_esc(p)}</i>\n"
    if info.get("url"):
        t += f"🔗 <a href=\"{info['url']}\">IMDb Page</a>\n"
    return t + "━━━━━━━━━━━━━━━\n"


async def send_result(message, query, files, total_results, btn):
    """Poster undenkil photo + caption, illenkil text"""
    info = await get_search_details(query, files)
    text = details_block(info) + result_header(query, total_results)
    markup = InlineKeyboardMarkup(btn)
    poster = (info or {}).get("poster")
    if poster and len(text) <= 1024:
        for url in (poster, (info or {}).get("poster_alt")):
            if not url:
                continue
            try:
                m = await message.reply_photo(url, caption=text, reply_markup=markup,
                                              parse_mode=enums.ParseMode.HTML)
                await colorize(m, btn)
                return m
            except Exception as e:
                logger.error(f"Poster send error: {e}")
    m = await message.reply_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML,
                                 disable_web_page_preview=True)
    await colorize(m, btn)
    return m


def keep_details(msg):
    """Pazhaya message-ile details bhagam (header-inu munpu) thirike edukkunnu"""
    old = (msg.caption.html if msg.caption else (msg.text.html if msg.text else "")) or ""
    i = old.find("━━━━━━━━━━━━━━━")
    return old[: i + 16] if i != -1 else ""


async def edit_result(msg, text, markup):
    if msg.photo:
        m = await msg.edit_caption(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    else:
        m = await msg.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML,
                                disable_web_page_preview=True)
    await colorize(msg, markup.inline_keyboard)
    return m


# ============================================================
# COLOUR BUTTONS (Bot API 9.4 "style": primary = blue, success = green)
# Pyrogram-il style illa, athukondu send cheytha shesham HTTP Bot API vazhi
# reply_markup maathram colour aakki edit cheyyunnu. Fail aayaal grey thanne.
# ============================================================
def _btn_json(b, style):
    d = {"text": b.text, "style": style}
    if b.url:
        d["url"] = b.url
    elif b.callback_data is not None:
        d["callback_data"] = b.callback_data if isinstance(b.callback_data, str) else b.callback_data.decode()
    else:
        return None
    return d


async def colorize(msg, btn):
    if not msg or not BOT_TOKEN:
        return
    styles = ("primary", "success", "danger")
    rows, k = [], 0
    for row in btn:
        r = []
        for b in row:
            j = _btn_json(b, styles[k % 3])
            k += 1
            if j:
                r.append(j)
        if r:
            rows.append(r)
    payload = json.dumps({
        "chat_id": msg.chat.id,
        "message_id": msg.id,
        "reply_markup": {"inline_keyboard": rows},
    }).encode()

    def post():
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            data=payload, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=8).read()
        except Exception as e:
            logger.warning(f"Colour buttons failed: {e}")

    await asyncio.get_event_loop().run_in_executor(None, post)


def filter_row(text):
    return [
        InlineKeyboardButton("🌐 Language", callback_data=cbd("flang#", text)),
        InlineKeyboardButton("🎞 Quality", callback_data=cbd("fqual#", text)),
    ]


async def send_log_safe(client, log_txt):
    if not LOG_CHANNEL:
        return
    try:
        chat_target = int(LOG_CHANNEL) if str(LOG_CHANNEL).startswith("-100") or str(LOG_CHANNEL).isdigit() else str(LOG_CHANNEL)
        await client.send_message(chat_id=chat_target, text=log_txt)
    except Exception as e:
        logger.error(f"Log Channel Error: {e}")

async def safe_delete_messages(client, chat_id, message_ids, delay=10):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except Exception as e:
        logger.error(f"Error in safe_delete_messages: {e}")


# ============================================================
# MAIN SEARCH FILTER HANDLER
# ============================================================
@Client.on_message((filters.group | filters.private) & filters.text & filters.incoming, group=1)
async def give_filter(client, message):
    if not message.text or message.text.startswith(("/", "!", "#")) or len(message.text.strip()) < 2:
        return

    text = message.text.strip()
    user = message.from_user
    if not user:
        return

    userid = user.id
    user_mention = user.mention
    is_group = message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]
    chat_title = message.chat.title if is_group else "Bot PM / Personal"

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        return

    # ഗ്രൂപ്പ് സ്പാം ഡിലീറ്റ്
    if is_group:
        spam_words = ["xxx", "18+", "playnow", "oiled", "massage", "moaning", "homemade", "sweet dreams", "audition"]
        if any(w in text.lower() for w in spam_words) or (message.forward_date and userid not in ADMINS):
            try:
                await message.delete()
                return
            except Exception:
                pass

    files, offset, total_results = await get_search_results(text, max_results=10)

    # 1. ഫയലുകൾ കിട്ടിയില്ലെങ്കിൽ (Dual Language Suggestions)
    if not files:
        suggestions = await get_smart_suggestions(text)

        # സജഷനുകൾ കണ്ടെത്തിയാൽ
        if suggestions:
            btn = []
            for mov in suggestions:
                btn.append([InlineKeyboardButton(f"🎬 {mov}", callback_data=f"spolling#{mov}")])

            suggest_text = (
                f"👋 <b>ഹലോ / Hello {user_mention},</b>\n\n"
                f"❓ <b>നിങ്ങൾ ഉദ്ദേശിച്ചത് താഴെ പറയുന്നവയിൽ ഏതെങ്കിലും ആണോ?</b>\n"
                f"<i>Did you mean one of the movies listed below?</i>\n\n"
                f"👇 <i>ശരിയായ സിനിമയിൽ ടാപ്പ് ചെയ്യുക / Tap on the correct movie:</i>"
            )
            suggest_msg = await message.reply_text(
                suggest_text,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            if is_group:
                asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, suggest_msg.id], delay=60))
            message.stop_propagation()
            return

        # സജഷനുകൾ ഒന്നും കണ്ടെത്താൻ സാധിച്ചില്ലെങ്കിൽ (Dual Language Error)
        log_txt = (
            f"❌ <b>#MovieNotFound</b>\n\n"
            f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
            f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
            f"🔍 <b>Query:</b> <code>{text}</code>"
        )
        await send_log_safe(client, log_txt)

        btn = [
            [InlineKeyboardButton("📥 Request ചെയ്യുക / Request", callback_data=cbd("mreq#", text))],
            [InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={urllib.parse.quote(text)}+movie")],
        ]
        err_text = (
            f"❌ <b>സിനിമ കണ്ടെത്താനായില്ല / Movie Not Found!</b>\n\n"
            f"👋 <b>ഹലോ / Hello {user_mention},</b>\n"
            f"📌 <b>നിങ്ങൾ തിരഞ്ഞത് / Your Query:</b> <code>{text}</code>\n\n"
            f"💡 <i>ദയവായി ശരിയായ സ്പെല്ലിംഗ് പരിശോധിച്ച് വീണ്ടും അയക്കുക.</i>\n"
            f"<i>Please check your spelling and try again.</i>"
        )
        err_msg = await message.reply_text(
            err_text,
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        
        if is_group:
            asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, err_msg.id], delay=60))
        
        message.stop_propagation()
        return

    # 2. ഫയലുകൾ കണ്ടെത്തിയാൽ
    log_txt = (
        f"🎬 <b>#FileSentToPM</b>\n\n"
        f"👥 <b>Requested In:</b> <b>{chat_title}</b>\n"
        f"👤 <b>User:</b> {user_mention} (<code>{userid}</code>)\n"
        f"🔍 <b>Query:</b> <code>{text}</code>\n"
        f"📦 <b>Files Found:</b> {total_results}"
    )
    await send_log_safe(client, log_txt)

    btn = build_file_buttons(files)

    if offset != "":
        total_pages = (total_results + 9) // 10
        btn.append([
            InlineKeyboardButton(f"📚 Page 1/{total_pages}", callback_data="pages_info"),
            InlineKeyboardButton("Next ⏩", callback_data=cbd("next_", text, f"_{offset}_1"))
        ])
    if total_results > 1:
        btn.append(filter_row(text))

    result_msg = await send_result(message, text, files, total_results, btn)

    if is_group:
        USER_GRP_MSGS[userid] = {
            "chat_id": message.chat.id,
            "user_msg_id": message.id,
            "bot_msg_id": result_msg.id
        }
        asyncio.create_task(safe_delete_messages(client, message.chat.id, [message.id, result_msg.id], delay=120))

    message.stop_propagation()


# ============================================================
# CALLBACK: SPELL CHECK CLICK & AUTO REQUEST HANDLER
# ============================================================
@Client.on_callback_query(filters.regex(r"^spolling#"))
async def spelling_click_handler(client, query: CallbackQuery):
    movie_name = query.data.split("#", 1)[1]
    files, offset, total_results = await get_search_results(movie_name, max_results=10)
    
    # 1. Database-il file illenkil Adminu request ayakkunnu
    if not files:
        user = query.from_user
        user_mention = user.mention
        user_id = user.id
        chat_title = query.message.chat.title if query.message.chat.title else "Bot PM"

        # Admin Log Channel-ilekku request ayakkunnu
        req_log = (
            f"📥 <b>#NewMovieRequest</b>\n\n"
            f"🎬 <b>Requested Movie:</b> <code>{movie_name}</code>\n"
            f"👤 <b>Requested By:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"👥 <b>From Chat:</b> <b>{chat_title}</b>\n\n"
            f"⚡ <i>Dhayavayi ee movie database-il upload cheyyuka!</i>"
        )
        await send_log_safe(client, req_log)
        await add_request(user_id, movie_name)

        # Popup Alert-ൽ മലയാളവും ഇംഗ്ലീഷും ഒന്നിച്ച് നൽകുന്നു
        alert_msg = (
            f"⚠️ '{movie_name}' നിലവിൽ ലഭ്യമല്ല!\n"
            f"Movie not available!\n\n"
            f"✅ റിക്വസ്റ്റ് അഡ്മിന് അയച്ചിട്ടുണ്ട്. ഉടൻ ചേർക്കാം!\n"
            f"Request sent to admin!\n\n"
            f"🔔 അപ്‌ലോഡ് ആകുമ്പോൾ PM-ൽ അറിയിക്കും."
        )
        await query.answer(alert_msg[:200], show_alert=True)

        # Chat-ile message request confirmation aayi edit cheyyunnu (Malayalam + English)
        req_confirm_text = (
            f"🎬 <b>സിനിമ / Movie :</b> <code>{movie_name}</code>\n\n"
            f"❌ <b>ഈ സിനിമ നിലവിൽ ഡാറ്റാബേസിൽ ലഭ്യമല്ല!</b>\n"
            f"<i>This movie is currently not available in our database.</i>\n\n"
            f"✅ <b>താങ്കളുടെ റിക്വസ്റ്റ് അഡ്മിന് വിജയകരമായി അയച്ചിട്ടുണ്ട്. ഉടൻ അപ്‌ലോഡ് ചെയ്യുന്നതാണ്!</b>\n"
            f"<i>Your request has been forwarded to the admin. It will be uploaded soon!</i>"
        )
        
        btn = [[
            InlineKeyboardButton("📢 Updates Channel", url="https://t.me/RRK_Movies")
        ]]

        return await query.message.edit_text(
            req_confirm_text,
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )

    # 2. File undenkil list cheyyunnu
    btn = build_file_buttons(files)

    if offset != "":
        total_pages = (total_results + 9) // 10
        btn.append([
            InlineKeyboardButton(f"📚 Page 1/{total_pages}", callback_data="pages_info"),
            InlineKeyboardButton("Next ⏩", callback_data=f"next_{movie_name}_{offset}_1")
        ])

    info = await get_search_details(movie_name, files)
    await query.message.edit_text(
        details_block(info) + result_header(movie_name, total_results),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )
    await colorize(query.message, btn)
    await query.answer()


# ============================================================
# CALLBACK: PAGINATION (Next / Back)
# ============================================================
@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page_handler(client, query: CallbackQuery):
    try:
        payload = query.data[5:]
        parts = payload.rsplit("_", 2)
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            text, offset, curr_page = parts[0], int(parts[1]), int(parts[2])
        else:
            text, offset = payload.rsplit("_", 1)
            offset, curr_page = int(offset), 1
    except Exception:
        return await query.answer("കൂടുതൽ ഫയലുകളില്ല / No more results!", show_alert=True)

    files, next_offset, total_results = await get_search_results(text, offset=int(offset), max_results=10)
    if not files:
        return await query.answer("അവസാനത്തെ പേജ് ആയി / Last page reached!", show_alert=True)

    total_pages = (total_results + 9) // 10
    new_page = curr_page + 1

    btn = build_file_buttons(files)

    page_btns = []
    prev_offset = max(0, int(offset) - 10)
    page_btns.append(InlineKeyboardButton("⏪ Back", callback_data=cbd("next_", text, f"_{prev_offset}_{new_page - 2}")))
    page_btns.append(InlineKeyboardButton(f"📚 Page {new_page}/{total_pages}", callback_data="pages_info"))

    if next_offset != "":
        page_btns.append(InlineKeyboardButton("Next ⏩", callback_data=cbd("next_", text, f"_{next_offset}_{new_page}")))

    btn.append(page_btns)

    try:
        disp = text
        for _lbl, _pat in list(LANG_FILTERS.values()) + list(QUAL_FILTERS.values()):
            if disp.endswith(" " + _pat):
                disp = disp[: -len(_pat) - 1]
        await edit_result(query.message, keep_details(query.message) + result_header(disp, total_results, new_page),
                          InlineKeyboardMarkup(btn))
        await query.answer()
    except Exception as e:
        logger.error(f"Page edit error: {e}")
        await query.answer()

@Client.on_callback_query(filters.regex(r"^pages_info"))
async def pages_info_click(client, query: CallbackQuery):
    await query.answer("Current Page Number", show_alert=False)


# ============================================================
# CALLBACK: MOVIE REQUEST BUTTON
# ============================================================
@Client.on_callback_query(filters.regex(r"^mreq#"))
async def movie_request_click(client, query: CallbackQuery):
    movie_name = query.data.split("#", 1)[1].strip()
    user = query.from_user
    saved = await add_request(user.id, movie_name)
    chat_title = query.message.chat.title if query.message.chat.title else "Bot PM"
    if saved:
        await send_log_safe(client, (
            f"📥 <b>#NewMovieRequest</b>\n\n"
            f"🎬 <b>Requested Movie:</b> <code>{movie_name}</code>\n"
            f"👤 <b>Requested By:</b> {user.mention} (<code>{user.id}</code>)\n"
            f"👥 <b>From Chat:</b> <b>{chat_title}</b>"
        ))
    await query.answer(
        (f"✅ '{movie_name[:40]}' റിക്വസ്റ്റ് ചെയ്തു! / Request saved!\n\n"
         f"🔔 അപ്‌ലോഡ് ആകുമ്പോൾ PM-ൽ അറിയിക്കും (ബോട്ട് Start ചെയ്തിരിക്കണം).")[:200],
        show_alert=True
    )


# ============================================================
# CALLBACK: LANGUAGE / QUALITY FILTER
# ============================================================
@Client.on_callback_query(filters.regex(r"^(flang|fqual)#"))
async def filter_menu(client, query: CallbackQuery):
    kind, text = query.data.split("#", 1)
    options = LANG_FILTERS if kind == "flang" else QUAL_FILTERS
    rows, row = [], []
    for code, (label, _) in options.items():
        row.append(InlineKeyboardButton(label, callback_data=cbd(f"fsel#{code}#", text)))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 എല്ലാം / All", callback_data=cbd("fsel#all#", text))])
    try:
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(rows))
        await colorize(query.message, rows)
    except Exception as e:
        logger.error(f"Filter menu error: {e}")
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsel#"))
async def filter_select(client, query: CallbackQuery):
    _, code, text = query.data.split("#", 2)
    if code == "all":
        label, search = "", text
    else:
        label, pattern = LANG_FILTERS.get(code) or QUAL_FILTERS.get(code) or ("", "")
        search = f"{text} {pattern}" if pattern else text

    res = await get_search_results(search, max_results=10)
    files, offset, total_results = res if res else ([], "", 0)
    if not files:
        return await query.answer(f"❌ {label} ഫയലുകൾ ഇല്ല / No {label} files found!", show_alert=True)

    btn = build_file_buttons(files)
    if offset != "":
        total_pages = (total_results + 9) // 10
        btn.append([
            InlineKeyboardButton(f"📚 Page 1/{total_pages}", callback_data="pages_info"),
            InlineKeyboardButton("Next ⏩", callback_data=cbd("next_", search, f"_{offset}_1")),
        ])
    btn.append(filter_row(text))

    head = result_header(text, total_results, 1, label)
    try:
        await edit_result(query.message, keep_details(query.message) + head, InlineKeyboardMarkup(btn))
        await query.answer(f"✅ {label or 'All'}: {total_results} files")
    except Exception as e:
        logger.error(f"Filter select error: {e}")
        await query.answer(f"✅ {label or 'All'}: {total_results} files")
