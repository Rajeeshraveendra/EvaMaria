import os
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.errors import MessageNotModified

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

async def ask_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Error: GEMINI_API_KEY is missing in Railway Variables!"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "You are an AI cinema assistant for the Telegram channel and movie group 'RRK Movies'. "
                    "Answer user queries politely, accurately, and concisely (OTT release dates, streaming platform, cast details). "
                    "Respond in Malayalam, Manglish, or English depending on user query. Keep answers brief with emojis.\n\n"
                    f"User Query: {prompt}"
                )
            }]
        }]
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    err_msg = data.get("error", {}).get("message", "API response error")
                    return f"⚠️ AI Error: {err_msg}"
        except Exception as e:
            return f"⚠️ Connection Error: {str(e)}"

# group=-1 നൽകുന്നത് പ്രധാന മൂവി സെർച്ച് ഫിൽട്ടറിന് മുൻപ് തന്നെ AI പ്രവർത്തിക്കാനാണ്
@Client.on_message(filters.group & filters.text & filters.incoming, group=-1)
async def ai_movie_assistant(client, message):
    text = (message.text or "").strip()

    # കമാൻഡുകൾ ഒഴിവാക്കുക
    if text.startswith(("/", "!", "#")):
        message.continue_propagation()
        return

    triggers = [
        "eppo", "eppozha", "release", "ott", "date", "undoo", "undോ", "varum",
        "evide", "netflix", "prime", "hotstar", "review", "ennanu", "ennu", "?"
    ]

    is_question = (
        "?" in text or
        any(trigger in text.lower() for trigger in triggers)
    )

    # ചോദ്യമല്ലെങ്കിൽ സാധാരണ ഫയൽ സെർച്ചിനായി വിട്ടുകൊടുക്കുക
    if not is_question:
        message.continue_propagation()
        return

    # ചോദ്യമാണെങ്കിൽ ബോട്ട് നേരിട്ട് AI റിപ്ലൈ നൽകുന്നു
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    reply_content = await ask_gemini(text)

    try:
        await message.reply_text(
            f"{reply_content}\n\n🍿 **RRK Movies Updates**",
            disable_web_page_preview=True
        )
        # ചോദ്യത്തിന് AI മറുപടി നൽകിയതിനാൽ ഫയൽ സെർച്ച് നിർത്തിവെക്കുന്നു
        message.stop_propagation()
    except Exception as e:
        print(f"Send Message Error: {e}")
        message.continue_propagation()
