import re
import asyncio
import os
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import CHANNELS, PICS, ADMINS
from database.ia_filterdb import save_file
from imdb import Cinemagoer

# IMDb instance
ia = Cinemagoer()

UPDATE_CHANNEL = int(os.environ.get("UPDATE_CHANNEL", "-1003799495012"))

POST_CACHE = {}
LOCK = asyncio.Lock()

def get_pure_title(filename):
    name = re.sub(r"\[.*?\]|\(.*?\)", "", filename)
    name = name.replace(".", " ").replace("_", " ").strip()
    
    tags = ["hindi", "tamil", "telugu", "malayalam", "kannada", "english", "hdrip", "web-dl", "hevc", "720p", "1080p", "480p", "mkv", "mp4"]
    words = name.split()
    clean = []
    for w in words:
        if any(w.lower().startswith(t) for t in tags):
            break
        clean.append(w)
    
    title = " ".join(clean).strip()
    return title if title else (words[0] if words else "Movie")

async def get_imdb_details(movie_name):
    loop = asyncio.get_event_loop()
    def fetch():
        try:
            movies = ia.search_movie(movie_name)
            if not movies:
                return None
            movie = movies[0]
            ia.update(movie, ['main', 'plot'])
            
            title = movie.get('title', movie_name)
            year = movie.get('year', '')
            rating = movie.get('rating', 'N/A')
            genres = ", ".join(movie.get('genres', []))
            
            # Story / Plot edukkunnu
            plot_list = movie.get('plot', [])
            story = plot_list[0] if plot_list else movie.get('plot outline', 'No story description available.')
            # Length kooduthal aanenkil shrink cheyyunnu
            if len(story) > 600:
                story = story[:600] + "..."
                
            poster = movie.get('full-size cover url', None)
            return {
                "title": f"{title} ({year})" if year else title,
                "rating": rating,
                "genres": genres,
                "story": story,
                "poster": poster
            }
        except Exception as e:
            print(f"IMDb Error: {e}")
            return None

    return await loop.run_in_executor(None, fetch)

def get_caption_and_buttons(movie_title, entries, imdb_info=None):
    movies_list_text = "\n".join(entries)
    
    if imdb_info:
        story_text = imdb_info.get("story", "")
        rating_text = imdb_info.get("rating", "N/A")
        genres_text = imdb_info.get("genres", "N/A")
        
        caption = (
            f"🎬 <b>{imdb_info['title']}</b>\n\n"
            f"⭐️ <b>IMDb Rating :</b> {rating_text}/10\n"
            f"🎭 <b>Genres :</b> {genres_text}\n\n"
            f"📖 <b>Storyline :</b>\n<i>{story_text}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Available Files :</b>\n"
            f"{movies_list_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Released & Verified</b> ✅"
        )
    else:
        caption = (
            f"<b>Today's Movies :</b>\n"
            f"{movies_list_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"          <b>Released ✅</b>\n"
            f"📌 <b>Pin For Instant Updates</b>\n"
            f"       😎 <b>Check it Out</b> 😎\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Movie Files 📥", switch_inline_query_current_chat=movie_title)]
    ])
    
    return caption, buttons

# 1. Direct file save handler
@Client.on_message(filters.private & (filters.document | filters.video))
async def save_direct_files(client, message):
    media = message.document or message.video
    if not media:
        return

    if not hasattr(media, 'file_type'):
        media.file_type = "video" if message.video else "document"
    if not hasattr(media, 'caption'):
        media.caption = None

    try:
        saved = await save_file(media)
        is_success = saved[0] if isinstance(saved, tuple) else saved
        if is_success:
            await message.reply_text(f"✅ <b>Database-il save cheythu!</b>\n\n📁 <code>{media.file_name}</code>", quote=True)
        else:
            await message.reply_text(f"ℹ️️ <b>File already database-il undu:</b>\n\n📁 <code>{media.file_name}</code>", quote=True)
    except Exception as e:
        await message.reply_text(f"⚠️ <b>Save cheyyan kazhinjilla:</b>\n<code>{e}</code>", quote=True)

# 2. Channel forward auto post with IMDb storyline
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def auto_post_to_group(client, message):
    media = message.document or message.video
    if not media:
        return

    try:
        if not hasattr(media, 'file_type'):
            media.file_type = "video" if message.video else "document"
        if not hasattr(media, 'caption'):
            media.caption = None
        await save_file(media)
    except Exception as err:
        print(f"Channel DB Save Error: {err}")

    if not UPDATE_CHANNEL:
        return

    file_name = getattr(media, 'file_name', 'New Movie')
    base_title = get_pure_title(file_name)
    line_entry = f"🎬 {file_name}"

    async with LOCK:
        if base_title in POST_CACHE:
            data = POST_CACHE[base_title]
            if line_entry not in data["entries"]:
                data["entries"].append(line_entry)
                caption, buttons = get_caption_and_buttons(base_title, data["entries"], data.get("imdb_info"))
                
                try:
                    await client.edit_message_caption(
                        chat_id=UPDATE_CHANNEL,
                        message_id=data["msg_id"],
                        caption=caption,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Edit Caption Error: {e}")
            return

        # IMDb-il ninnu katha fetch cheyyunnu
        imdb_info = await get_imdb_details(base_title)
        entries = [line_entry]
        caption, buttons = get_caption_and_buttons(base_title, entries, imdb_info)

        sent_msg = None
        photo_url = imdb_info.get("poster") if (imdb_info and imdb_info.get("poster")) else (random.choice(PICS) if PICS else None)

        if photo_url:
            try:
                sent_msg = await client.send_photo(
                    chat_id=UPDATE_CHANNEL,
                    photo=photo_url,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as err:
                print(f"Poster send error: {err}")

        if not sent_msg:
            sent_msg = await client.send_message(
                chat_id=UPDATE_CHANNEL,
                text=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        POST_CACHE[base_title] = {
            "msg_id": sent_msg.id,
            "entries": entries,
            "imdb_info": imdb_info
        }
