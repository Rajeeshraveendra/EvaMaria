from pyrogram import Client, filters
from pyrogram.errors import UserIsBlocked, InputUserDeactivated, PeerIdInvalid, FloodWait
from info import ADMINS
import asyncio

USAGE = (
    "<b>Usage / ഉപയോഗം:</b>\n"
    "<code>/send USER_ID message</code>\n"
    "അല്ലെങ്കിൽ ഒരു മെസേജിന് (photo/video/file ഉൾപ്പെടെ) reply ചെയ്ത് <code>/send USER_ID</code>"
)


@Client.on_message(filters.command(["send", "dm"]) & filters.user(ADMINS))
async def send_to_user(bot, message):
    parts = message.text.split(None, 2)
    if len(parts) < 2:
        return await message.reply_text(USAGE)
    target = parts[1]
    try:
        target = int(target)
    except ValueError:
        target = target.lstrip("@")
    text = parts[2] if len(parts) > 2 else None
    reply = message.reply_to_message
    if not text and not reply:
        return await message.reply_text(USAGE)
    for _ in range(2):
        try:
            if reply:
                await reply.copy(target)
            else:
                await bot.send_message(target, text, disable_web_page_preview=True)
            return await message.reply_text(f"✅ Sent to <code>{target}</code>")
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except UserIsBlocked:
            return await message.reply_text("❌ ഈ user ബോട്ടിനെ block ചെയ്തിട്ടുണ്ട്.")
        except InputUserDeactivated:
            return await message.reply_text("❌ ഈ അക്കൗണ്ട് deleted ആണ്.")
        except PeerIdInvalid:
            return await message.reply_text("❌ ഈ user ഇതുവരെ ബോട്ട് start ചെയ്തിട്ടില്ല / ID തെറ്റാണ്.")
        except Exception as e:
            return await message.reply_text(f"❌ Failed: <code>{e}</code>")
