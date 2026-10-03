import os
import aiohttp
from pyrogram import Client, filters, enums

# Railway Environment Variable-ൽ നിന്ന് കീ എടുക്കുന്നു
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

async def ask_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{
                "text": f"You are an AI assistant for the Telegram channel and movie group 'RRK Movies'. "
                        f"Answer the user query politely, accurately, and concisely (OTT release dates, platform info, movie updates). "
                        f"Respond in Malayalam, Manglish, or English depending on how the user asks. Keep it short and crisp with emojis.\n\nUser Question: {prompt}"
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
                    err_msg = data.get("error", {}).get("message", "Unknown error")
                    print(f"Gemini API Error: {err_msg}")
                    return None
        except Exception as e:
            print(f"Connection Error: {e}")
            return None

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

    if not is_question or not GEMINI_API_KEY:
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
