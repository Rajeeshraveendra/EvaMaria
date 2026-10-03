import os
import google.generativeai as genai
from pyrogram import Client, filters, enums

# Gemini API ക്രമീകരണം
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "max_output_tokens": 500,
}

system_instruction = (
    "You are an intelligent movie assistant for the Telegram channel and group 'RRK Movies'. "
    "Provide clear, accurate, and concise answers about movie OTT release dates, platforms (Netflix, Hotstar, Prime, etc.), "
    "cast, director, and updates. Answer in Malayalam, Manglish, or English depending on how the user asks. "
    "Keep answers friendly and formatted with clean bullet points and emojis. Do not invent fake release dates."
)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=system_instruction
)

@Client.on_message(filters.group & filters.text)
async def ai_movie_assistant(client, message):
    # ബോട്ട് തന്നെ അയക്കുന്ന മെസ്സേജുകൾ ഒഴിവാക്കുന്നു
    if message.from_user and message.from_user.is_bot:
        return

    text = message.text.strip()

    # കമാൻഡുകൾ ഒഴിവാക്കുക
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

    # ടൈപ്പിംഗ് സ്റ്റാറ്റസ്
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    try:
        response = model.generate_content(text)
        reply_content = response.text

        await message.reply_text(
            f"{reply_content}\n\n🍿 **RRK Movies Updates**",
            quote=True,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Gemini AI Error: {e}")
