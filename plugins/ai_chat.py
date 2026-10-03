import os
import json
import asyncio
import time
import urllib.request
from pyrogram import Client, filters, enums

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def request_model(model_name: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "You are 'RRK Movies Assistant', an expert cinema and OTT guide for a movie Telegram community. "
                    "When users ask about movie OTT releases, streaming platforms (Netflix, Prime, Hotstar, ManoramaMAX, etc.), "
                    "or release dates, give a direct, friendly, and complete answer in 2 to 3 sentences. "
                    "If the official date is not confirmed, state the expected period clearly. "
                    "Reply naturally in Malayalam or Manglish according to the user's query.\n\n"
                    f"User Question: {prompt}"
                )
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 600,
            "temperature": 0.4
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": GEMINI_API_KEY
        }
    )

    with urllib.request.urlopen(req, timeout=25) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()

def fetch_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Error: GEMINI_API_KEY is missing in Railway Variables!"

    # 503 ഒഴിവാക്കാൻ ഒന്നിലധികം മോഡലുകൾ ട്രൈ ചെയ്യുന്നു
    models = ["gemini-flash-latest", "gemini-1.5-flash-8b", "gemini-2.0-flash"]
    
    last_error = ""
    for model in models:
        for _ in range(2):
            try:
                return request_model(model, prompt)
            except urllib.error.HTTPError as e:
                if e.code in (503, 429):
                    time.sleep(1.5)
                    continue
                err_msg = e.read().decode("utf-8", errors="ignore")
                last_error = f"API Error ({e.code}): {err_msg[:100]}"
                break
            except Exception as e:
                last_error = str(e)
                break

    return f"⚠️ Server Busy: ദയവായി അല്പം കഴിഞ്ഞ് വീണ്ടും ചോദിക്കുക. ({last_error})"

@Client.on_message(filters.group & filters.text & filters.incoming, group=-1)
async def ai_movie_assistant(client, message):
    text = (message.text or "").strip()

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
