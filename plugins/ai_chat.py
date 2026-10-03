import os
import json
import asyncio
import time
import urllib.request
from pyrogram import Client, filters, enums

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def fetch_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Error: GEMINI_API_KEY is missing in Railway Variables!"

    # നിങ്ങളുടെ പ്രോജക്റ്റിൽ ലഭ്യമായ ഒഫീഷ്യൽ എൻഡ്‌പോയിന്റ്
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "You are an AI assistant for the Telegram channel and movie group 'RRK Movies'. "
                    "Answer user queries politely, accurately, and concisely (OTT release dates, platforms, cast details). "
                    "Respond in simple Malayalam, Manglish, or English depending on how the user asks. Keep it crisp.\n\n"
                    f"User Question: {prompt}"
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

    # 503 (ഹൈ ഡിമാൻഡ്) വന്നാൽ തനിയെ 2 തവണ കൂടി ട്രൈ ചെയ്യുന്നു
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 2:
                time.sleep(2)  # 2 സെക്കൻഡ് കാത്തിരുന്ന് വീണ്ടും റിക്വസ്റ്റ് ചെയ്യുന്നു
                continue
            err_msg = e.read().decode("utf-8", errors="ignore")
            return f"⚠️ API Error ({e.code}): {err_msg[:120]}"
        except Exception as e:
            return f"⚠️ Connection Error: {str(e)}"

    return "⚠️ AI Server Busy: ദയവായി അല്പം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക."

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
