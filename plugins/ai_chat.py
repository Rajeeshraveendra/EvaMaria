import os
import aiohttp
from pyrogram import Client, filters, enums

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

async def ask_gemini(prompt: str):
    # Google AI Studio API key format check
    if not GEMINI_API_KEY:
        return "⚠️️ എറർ: GEMINI_API_KEY റെയിൽവേയിൽ കണ്ടെത്തിയില്ല!"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{
                "text": f"You are an AI cinema assistant for the Telegram movie channel 'RRK Movies'. "
                        f"Answer concisely with movie/OTT details in simple Malayalam, Manglish, or English.\n\nQuestion: {prompt}"
            }]
        }]
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    err_msg = data.get("error", {}).get("message", str(data))
                    return f"⚠️ Gemini API Error: {err_msg}"
        except Exception as e:
            return f"⚠️ Connection Error: {str(e)}"

@Client.on_message(filters.group & filters.text)
async def ai_movie_assistant(client, message):
    if message.from_user and message.from_user.is_bot:
        return

    text = message.text.strip()
    if text.startswith(("/", "!", "#")):
        return

    triggers = [
        "eppo", "eppozha", "release", "ott", "date", "undoo", "undോ", "varum",
        "evide", "netflix", "prime", "hotstar", "review", "ennanu", "ennu", "?"
    ]

    is_question = (
        "?" in text or
        any(trigger in text.lower() for trigger in triggers)
    )

    if not is_question:
        return

    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    reply_content = await ask_gemini(text)

    if reply_content:
        await client.send_message(
            chat_id=message.chat.id,
            text=f"{reply_content}\n\n🍿 RRK Movies Updates",
            reply_to_message_id=message.id,
            disable_web_page_preview=True
        )
