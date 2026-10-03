import os
import google.generativeai as genai
from pyrogram import Client, filters, enums

# Gemini API ക്രമീകരണം
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=(
        "You are an AI assistant for the Telegram channel 'RRK Movies'. "
        "Answer movie questions, OTT releases, cast details concisely and clearly. "
        "Keep answers short, friendly, and formatted without unsupported markdown. "
        "Answer in Malayalam, Manglish, or English depending on user request."
    )
)

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

    try:
        # Generate AI response
        response = model.generate_content(text)
        reply_content = response.text or "വിവരങ്ങൾ ലഭ്യമായില്ല. ദയവായി അല്പം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക."

        # ParseMode ഒഴിവാക്കി പ്ലെയിൻ ടെക്സ്റ്റായി അയക്കുന്നു (മാർക്ക്ഡൗൺ എറർ വരാതിരിക്കാൻ)
        await client.send_message(
            chat_id=message.chat.id,
            text=f"{reply_content}\n\n🍿 RRK Movies Updates",
            reply_to_message_id=message.id,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Gemini AI Error: {e}")
