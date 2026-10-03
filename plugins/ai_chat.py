import os
import json
import asyncio
import urllib.request
from pyrogram import Client, filters, enums

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def fetch_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Error: GEMINI_API_KEY is missing in Railway Variables!"

    # Gemini 1.5 Pro എൻഡ്‌പോയിന്റ്
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "You are an AI cinema assistant for the Telegram channel and group 'RRK Movies'. "
                    "Answer user queries politely, accurately, and concisely (OTT release dates, streaming platforms, cast details). "
                    "Respond in simple Malayalam, Manglish, or English depending on user query. Keep answers brief with emojis.\n\n"
                    f"User Query: {prompt}"
                )
            }]
        }]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": GEMINI_API_KEY
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return f"⚠️ API Error ({e.code}): {err_msg[:120]}"
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)}"

@Client.on_message(filters.group & filters.text & filters.incoming, group=-1)
async def ai_movie_assistant(client, message):
    text = (message.text or "").strip()

    # കമാൻഡുകൾ ഒഴിവാക്കുന്നു
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

    # ചോദ്യമല്ലെങ്കിൽ ഫയൽ സെർച്ചിലേക്ക് കൈമാറുന്നു
    if not is_question:
        message.continue_propagation()
        return

    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, fetch_gemini, text)

    try:
        await message.reply_text(
            f"{reply}\n\n🍿 **RRK Movies Updates**",
            disable_web_page_preview=True
        )
        message.stop_propagation()
    except Exception as e:
        print(f"Error sending message: {e}")
        message.continue_propagation()
