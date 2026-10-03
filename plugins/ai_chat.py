import os
import json
import asyncio
import urllib.request
from pyrogram import Client, filters, enums

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def fetch_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Error: GEMINI_API_KEY is missing in Railway Variables!"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "You are an AI cinema assistant for the Telegram channel and group 'RRK Movies'. "
                    "Answer user queries politely, accurately, and concisely (OTT release dates, streaming platform, cast details). "
                    "Respond in Malayalam, Manglish, or English depending on user query. Keep answers brief with emojis.\n\n"
                    f"User Query: {prompt}"
                )
            }]
        }]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# group=-1 നൽകുന്നത് മെയിൻ ഫിൽട്ടറിന് മുൻപ് തന്നെ പ്രവർത്തിക്കാനാണ്
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

    # ചോദ്യമല്ലെങ്കിൽ സാധാരണ സിനിമ സെർച്ചിലേക്ക് വിടുക
    if not is_question:
        message.continue_propagation()
        return

    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    # പൈത്തൺ ത്രെഡ് വഴി Gemini കോൾ ചെയ്യുന്നു
    loop = asyncio.get_event_loop()
    reply_content = await loop.run_in_executor(None, fetch_gemini, text)

    try:
        await message.reply_text(
            f"{reply_content}\n\n🍿 **RRK Movies Updates**",
            disable_web_page_preview=True
        )
        message.stop_propagation()
    except Exception as e:
        print(f"Send Message Error: {e}")
        message.continue_propagation()
