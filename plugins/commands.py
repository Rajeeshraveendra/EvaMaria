import os
import logging
import random
import asyncio
import re
import json
import base64
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id
from database.users_chats_db import db
from info import CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS, BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, PROTECT_CONTENT
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from database.connections_mdb import active_connection

logger = logging.getLogger(__name__)

BATCH_FILES = {}
TARGET_LOG_CHANNEL = -1003799495012

async def delete_group_request_after_pm(client, user_id, delay=10):
    """Member PM-il file kitti kazhinjal group-ile avarude message 10 sec-il delete cheyyunnu"""
    try:
        from plugins.filters import USER_GRP_MSGS
        msg_data = USER_GRP_MSGS.pop(user_id, None)
        if msg_data:
            await asyncio.sleep(delay)
            # User chodicha message delete cheyyunnu
            try:
                await client.delete_messages(chat_id=msg_data["chat_id"], message_ids=msg_data["user_msg_id"])
            except Exception:
                pass
            # Bot ayacha result message delete cheyyunnu
            try:
                await client.delete_messages(chat_id=msg_data["chat_id"], message_ids=msg_data["bot_msg_id"])
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error deleting group msg after PM: {e}")

async def send_completion_message(client, user_id):
    """File ayachu kazhinjal thazhe attractive thank you msg ayakkunnu"""
    success_txt = (
        "✨ ━━━━━━━━━━━━━━━━━━━━━━ ✨\n"
        "🍿 <b>ഫയലുകൾ വിജയകരമായി അയച്ചിട്ടുണ്ട്!</b>\n"
        "<i>Files delivered successfully!</i>\n"
        "✨ ━━━━━━━━━━━━━━━━━━━━━━ ✨\n\n"
        "🎉 <b>താങ്കൾ തിരഞ്ഞ സിനിമയുടെ ഫയലുകൾ ഇപ്പോൾ ലഭ്യമാണ്.</b>\n"
        "<i>Your requested movie files are ready for you.</i>\n\n"
        "💬 <b>നിങ്ങളുടെ വിലയേറിയ അഭിപ്രായങ്ങളും നിർദ്ദേശങ്ങളും അഡ്മിനെ അറിയിക്കുക.</b>\n"
        "<i>Feel free to share your valuable feedback and suggestions with the admin.</i>\n\n"
        "❤️ <b>RRK Movies AutoBot തിരഞ്ഞെടുത്തതിന് നന്ദി!</b>\n"
        "🍿 <b>Happy Watching & Enjoy Your Movie!</b>\n\n"
        "📢 <b>കൂടുതൽ പുത്തൻ സിനിമകൾക്കും വിവരങ്ങൾക്കുമായി ഞങ്ങളുടെ ചാനലിൽ അംഗമാകൂ:</b>\n"
        "<i>Stay tuned to our official channel for latest updates!</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("📢 Main Channel", url="https://t.me/+NoL3OkqPwBtiZjY0"),
            InlineKeyboardButton("💬 WhatsApp Admin", url="https://wa.me/971562769519?text=Hi%20Rajeesh%20Raveendra%20Kamballur")
        ],
        [
            InlineKeyboardButton("🔍 Search More Movies", url="https://t.me/RRK_Movies")
        ]
    ]

    try:
        await client.send_message(
            chat_id=user_id,
            text=success_txt,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Completion Message Error: {e}")

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [
            [
                InlineKeyboardButton('🤖 𝚄𝚙𝚍𝚊𝚝𝚎𝚜', url='https://t.me/+NoL3OkqPwBtiZjY0')
            ],
            [
                InlineKeyboardButton('ℹ️ 𝙷𝚎𝚕𝚙', url=f"https://t.me/{temp.U_NAME}?start=help"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup)
        await asyncio.sleep(2)
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            if LOG_CHANNEL:
                try:
                    await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))
                except Exception as e:
                    logger.error(f"LOG_CHANNEL Error: {e}")
            await db.add_chat(message.chat.id, message.chat.title)
        return 

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        if LOG_CHANNEL:
            try:
                await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
            except Exception as e:
                logger.error(f"LOG_CHANNEL Error: {e}")

    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('➕ 𝙰𝚍𝚍 𝙼𝚎 𝚃𝚘 𝚈𝚘𝚞𝚛 𝙶𝚛𝚘𝚞𝚙𝚜 ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
            InlineKeyboardButton('🔍 𝚂𝚎𝚊𝚛𝚌𝚑', switch_inline_query_current_chat=''),
            InlineKeyboardButton('🤖 𝚄𝚙𝚍𝚊𝚝𝚎𝚜', url='https://t.me/+NoL3OkqPwBtiZjY0')
            ],[
            InlineKeyboardButton('ℹ️ 𝙷𝚎𝚕𝚙', callback_data='help'),
            InlineKeyboardButton('😊 𝙰𝚋𝚘𝚞𝚝', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return

    if AUTH_CHANNEL and not await is_subscribed(client, message):
        try:
            invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL))
        except ChatAdminRequired:
            logger.error("Make sure Bot is admin in Forcesub channel")
            return
        btn = [
            [
                InlineKeyboardButton(
                    "🤖 Join Updates Channel", url=invite_link.invite_link
                )
            ]
        ]

        if message.command[1] != "subscribe":
            try:
                kk, file_id = message.command[1].split("_", 1)
                pre = 'checksubp' if kk == 'filep' else 'checksub' 
                btn.append([InlineKeyboardButton(" 🔄 Try Again", callback_data=f"{pre}#{file_id}")])
            except (IndexError, ValueError):
                btn.append([InlineKeyboardButton(" 🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
        await client.send_message(
            chat_id=message.from_user.id,
            text="**Please Join My Updates Channel to use this Bot!**",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        buttons = [[
            InlineKeyboardButton('➕ 𝙰𝚍𝚍 𝙼𝚎 𝚃𝚘 𝚈𝚘𝚞𝚛 𝙶𝚛𝚘𝚞𝚙𝚜 ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
            InlineKeyboardButton('🔍 𝚂𝚎𝚊𝚛𝚌𝚑', switch_inline_query_current_chat=''),
            InlineKeyboardButton('🤖 𝚄𝚙𝚍𝚊𝚝𝚎𝚜', url='https://t.me/+NoL3OkqPwBtiZjY0')
            ],[
            InlineKeyboardButton('ℹ️ 𝙷𝚎𝚕𝚙', callback_data='help'),
            InlineKeyboardButton('😊 𝙰𝚋𝚘𝚞𝚝', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return

    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("Please wait")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try: 
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                if LOG_CHANNEL:
                    try:
                        await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
                    except Exception:
                        pass
                return
            os.remove(file)
            BATCH_FILES[file_id] = msgs
            
        for msg in msgs:
            title = msg.get("title")
            size = get_size(int(msg.get("size", 0)))
            f_caption = msg.get("caption", "")
            if BATCH_FILE_CAPTION:
                try:
                    f_caption = BATCH_FILE_CAPTION.format(file_name='' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except Exception as e:
                    logger.exception(e)
            if f_caption is None:
                f_caption = f"{title}"
            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1) 

        try:
            u_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            log_text = (
                f"📁 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> PM\n"
                f"👤 <b>User:</b> {u_info}\n"
                f"({message.from_user.id})\n"
                f"🔍 <b>Query:</b> <code>Batch Files</code>\n"
                f"📦 <b>Files Sent:</b> {len(msgs)}"
            )
            await client.send_message(
                chat_id=TARGET_LOG_CHANNEL,
                text=log_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Batch Log Error: {e}")

        await send_completion_message(client, message.from_user.id)
        asyncio.create_task(delete_group_request_after_pm(client, message.from_user.id, delay=10))
        await sts.delete()
        return

    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("Please wait")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if PROTECT_CONTENT else "batch"

        dstore_count = 0
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media.value)
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption = BATCH_FILE_CAPTION.format(file_name=getattr(media, 'file_name', ''), file_size=getattr(media, 'file_size', ''), file_caption=getattr(msg, 'caption', ''))
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(msg, 'caption', '')
                else:
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(msg, 'caption', file_name)
                try:
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                    dstore_count += 1
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                    dstore_count += 1
                except Exception as e:
                    logger.exception(e)
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                    dstore_count += 1
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                    dstore_count += 1
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1)

        try:
            u_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            log_text = (
                f"📁 <b>#FileSentToPM</b>\n\n"
                f"👥 <b>Requested In:</b> PM\n"
                f"👤 <b>User:</b> {u_info}\n"
                f"({message.from_user.id})\n"
                f"🔍 <b>Query:</b> <code>Store Link</code>\n"
                f"📦 <b>Files Sent:</b> {dstore_count}"
            )
            await client.send_message(
                chat_id=TARGET_LOG_CHANNEL,
                text=log_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Dstore Log Error: {e}")

        await send_completion_message(client, message.from_user.id)
        asyncio.create_task(delete_group_request_after_pm(client, message.from_user.id, delay=10))
        return await sts.delete()

    files_ = await get_file_details(file_id)           
    if not files_:
        try:
            pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=True if pre == 'filep' else False,
            )
            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = file.file_name
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(file_name=title)
                except:
                    pass
            await msg.edit_caption(f_caption)

            try:
                u_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
                log_text = (
                    f"📁 <b>#FileSentToPM</b>\n\n"
                    f"👥 <b>Requested In:</b> PM\n"
                    f"👤 <b>User:</b> {u_info}\n"
                    f"({message.from_user.id})\n"
                    f"🔍 <b>Query:</b> <code>{title}</code>\n"
                    f"📦 <b>Files Sent:</b> 1"
                )
                await client.send_message(
                    chat_id=TARGET_LOG_CHANNEL,
                    text=log_text,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Log Error: {e}")

            await send_completion_message(client, message.from_user.id)
            asyncio.create_task(delete_group_request_after_pm(client, message.from_user.id, delay=10))
            return
        except:
            return await message.reply('No such file exist.')

    files = files_[0]
    title = files.file_name
    size = get_size(files.file_size)
    f_caption = files.caption
    if CUSTOM_FILE_CAPTION:
        try:
            f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
    if f_caption is None:
        f_caption = f"{files.file_name}"

    # User-nu file ayakkunnu
    await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=True if pre == 'filep' else False,
    )

    try:
        u_info = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
        log_text = (
            f"📁 <b>#FileSentToPM</b>\n\n"
            f"👥 <b>Requested In:</b> PM\n"
            f"👤 <b>User:</b> {u_info}\n"
            f"({message.from_user.id})\n"
            f"🔍 <b>Query:</b> <code>{title}</code>\n"
            f"📦 <b>Files Sent:</b> 1"
        )
        await client.send_message(
            chat_id=TARGET_LOG_CHANNEL,
            text=log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Log Error: {e}")

    # Success msg PM-il ayakkunnu
    await send_completion_message(client, message.from_user.id)

    # User PM-il file kitti kazhinjathukond, group-ile avarude message 10 sec-il auto delete aakunnu
    asyncio.create_task(delete_group_request_after_pm(client, message.from_user.id, delay=10))

@Client.on_message(filters.command('channel') & filters.user(ADMINS))
async def channel_info(bot, message):
    if isinstance(CHANNELS, (int, str)):
        channels = [CHANNELS]
    elif isinstance(CHANNELS, list):
        channels = CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        chat = await bot.get_chat(channel)
        if chat.username:
            text += '\n@' + chat.username
        else:
            text += '\n' + (chat.title or chat.first_name)

    text += f'\n\n**Total:** {len(CHANNELS)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    try:
        await message.reply_document('TelegramBot.log')
    except Exception as e:
        await message.reply(str(e))

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
        return
    
    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({'_id': file_id})
    if result.deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
        if result.deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({
                'file_name': media.file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')

@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="YES", callback_data="autofilter_delete")],
                [InlineKeyboardButton(text="CANCEL", callback_data="close_data")],
            ]
        ),
        quote=True,
    )

@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer('Piracy Is Crime')
    await message.message.edit('Succesfully Deleted All The Indexed Files.')

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and str(userid) not in ADMINS
    ):
        return

    settings = await get_settings(grp_id)

    if settings is not None:
        buttons = [
            [
                InlineKeyboardButton('Filter Button', callback_data=f'setgs#button#{settings["button"]}#{grp_id}'),
                InlineKeyboardButton('Single' if settings["button"] else 'Double', callback_data=f'setgs#button#{settings["button"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Bot PM', callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if settings["botpm"] else '❌ No', callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('File Secure', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('IMDB', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Spell Check', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No', callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}'),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=f"<b>Change Your Settings for {title} As Your Wish ⚙</b>",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=message.id
        )

@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and str(userid) not in ADMINS
    ):
        return

    if len(message.command) < 2:
        return await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")
