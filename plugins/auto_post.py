# 3. മെസ്സേജ് ഐഡി വെച്ച് ഇൻഡെക്സ് ചെയ്യാനുള്ള കമാൻഡ്
# ഉപയോഗിക്കേണ്ട രീതി: /index 14 306
@Client.on_message(filters.command("index") & filters.private)
async def custom_index_command(client, message):
    user_id = message.from_user.id
    admin_list = [int(admin) if str(admin).isdigit() else admin for admin in ADMINS] if isinstance(ADMINS, list) else [int(ADMINS)]
    if user_id not in admin_list:
        return

    args = message.text.split()
    if len(args) < 3:
        return await message.reply_text("ഉപയോഗിക്കേണ്ട രീതി:\n<code>/index 14 306</code>")

    try:
        start_id = int(args[1])
        end_id = int(args[2])
    except ValueError:
        return await message.reply_text("നമ്പറുകൾ കൃത്യമായി നൽകുക!")

    # RRK Movies Productions ചാനലിന്റെ പൂർണ്ണമായ ID നേരിട്ട് നൽകുന്നു
    target_channel = -1003799495012

    status_msg = await message.reply_text(f"⏳ {start_id} മുതൽ {end_id} വരെയുള്ള ഫയലുകൾ സ്കാൻ ചെയ്ത് സേവ് ചെയ്യുന്നു...")
    saved_count = 0

    for msg_id in range(start_id, end_id + 1):
        try:
            ch_msg = await client.get_messages(target_channel, msg_id)
            if ch_msg and (ch_msg.document or ch_msg.video):
                try:
                    s = await save_file(client, ch_msg)
                except TypeError:
                    try:
                        s = await save_file(ch_msg)
                    except TypeError:
                        media = ch_msg.document or ch_msg.video
                        s = await save_file(media)
                if s:
                    saved_count += 1
        except Exception as e:
            print(f"Error indexing {msg_id}: {e}")

    await status_msg.edit_text(f"✅ പൂർത്തിയായി!\n📁 ആകെ സേവ് ചെയ്ത ഫയലുകൾ: <b>{saved_count}</b>")
