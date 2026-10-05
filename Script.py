class script(object):
    START_TXT = """തിയറ്റർ പ്രിന്റുകളോട് വിട പറയാം! ഇനി സിനിമകൾ കാണാം Full HD ക്വാളിറ്റിയിൽ മാത്രം. 🍿🎬

✅ എന്തുകൊണ്ട് ഞങ്ങളുടെ ഗ്രൂപ്പ്?

🚫 തിയറ്റർ പ്രിന്റുകൾ ഇല്ല
💎 ശുദ്ധമായ HD മൂവീസ് മാത്രം
⚡ ഫാസ്റ്റ് ഡൗൺലോഡ് ലിങ്കുകൾ

📥 ഇപ്പോൾ തന്നെ ജോയിൻ ചെയ്യൂ:
👉 https://t.me/+NoL3OkqPwBtiZjY0"""

    HELP_TXT = """
🙋🏻‍♂️   ഹലോ  {} 🤓

○ സിനിമകൾ ലഭിക്കാൻ ഗ്രൂപ്പിൽ സിനിമയുടെ ശരിയായ പേര് ടൈപ്പ് ചെയ്യുക.

○ ഇൻലൈൻ മോഡ് വഴി തിരയാൻ:
ഏതൊരു ചാറ്റിലും @RRK_Movies_AutoBot എന്ന് ടൈപ്പ് ചെയ്ത് ഒരു സ്പേസ് ഇട്ട് സിനിമയുടെ പേര് നൽകുക.

○ ലഭ്യമായ കമാൻഡുകൾ:
/start - ബോട്ട് ആക്ടീവ് ആണോ എന്ന് പരിശോധിക്കാൻ
/info - യൂസർ വിവരങ്ങൾ
/id - നിങ്ങളുടെ ഐഡി
/stats - ഡാറ്റാബേസ് സ്റ്റാറ്റസ്

😎 Powered by @RRK_Movies

©️ Maintained by @RRK_Movies"""

    ABOUT_TXT = """✯ 𝙼𝚈 𝙽𝙰𝙼𝙴: {}
✯ 𝙲𝚁𝙴𝙰𝚃𝙾𝚁: <a href=https://t.me/RRK_Movies>RRK Movies</a>
✯ 𝙲𝙷𝙰𝙽𝙽𝙴𝙻: @RRK_Movies
✯ 𝙻𝙸𝙱𝚁𝙰𝚁𝚈: 𝙿𝚈𝚁𝙾𝙶𝚁𝙰𝙼
✯ 𝙻𝙰𝙽𝙶𝚄𝙰𝙶𝙴: 𝙿𝚈𝚃𝙷𝙾𝙽 𝟹
✯ 𝙳𝙰𝚃𝙰 𝙱𝙰𝚂𝙴: 𝙼𝙾𝙽𝙶𝙾 𝙳𝙱
✯ 𝚂𝚃𝙰𝚃𝚄𝚂: 𝙰𝙲𝚃𝙸𝚅𝙴"""

    SOURCE_TXT = """<b>NOTE:</b>
- Eva Maria is an open source project. 
- Source - https://github.com/8769ANURAG/EvaMaria  

<b>CHANNEL:</b>
- <a href=https://t.me/RRK_Movies>RRK Movies</a>"""

    MANUELFILTER_TXT = """Help: <b>Filters</b>

- Filter is the feature where users can set automated replies for a particular keyword.

<b>Commands and Usage:</b>
• /filter - <code>add a filter in chat</code>
• /filters - <code>list all the filters of a chat</code>
• /del - <code>delete a specific filter in chat</code>
• /delall - <code>delete all filters in a chat (chat owner only)</code>"""

    BUTTON_TXT = """Help: <b>Buttons</b>

- Eva Maria Supports both URL and alert inline buttons.

<b>URL buttons:</b>
<code>[Button Text](buttonurl:https://t.me/RRK_Movies)</code>

<b>Alert buttons:</b>
<code>[Button Text](buttonalert:This is an alert message)</code>"""

    AUTOFILTER_TXT = """Help: <b>Auto Filter</b>

<b>NOTE:</b>
1. Make me an admin in your channel if it's private.
2. Forward the last message with quotes to index files."""

    CONNECTION_TXT = """Help: <b>Connections</b>

- Used to connect bot to PM for managing filters.

<b>Commands and Usage:</b>
• /connect  - <code>connect a chat to PM</code>
• /disconnect  - <code>disconnect from chat</code>
• /connections - <code>list all connections</code>"""

    EXTRAMOD_TXT = """Help: <b>Extra Modules</b>

<b>Commands and Usage:</b>
• /id - <code>get ID of a specified user</code>
• /info  - <code>get user information</code>
• /imdb  - <code>get movie info from IMDb</code>
• /search  - <code>search movies</code>"""

    ADMIN_TXT = """Help: <b>Admin mods</b>

<b>Commands and Usage:</b>
• /stats - <code>file status in DB</code>
• /delete - <code>delete file from DB</code>
• /users - <code>list users and IDs</code>
• /chats - <code>list chats and IDs</code>
• /broadcast - <code>broadcast message to all users</code>"""

    STATUS_TXT = """★ 𝚃𝙾𝚃𝙰𝙻 𝙵𝙸𝙻𝙴𝚂: <code>{}</code>
★ 𝚃𝙾𝚃𝙰𝙻 𝚄𝚂𝙴𝚁𝚂: <code>{}</code>
★ 𝚃𝙾𝚃𝙰𝙻 𝙲𝙷𝙰𝚃𝚂: <code>{}</code>
★ 𝚄𝚂𝙴𝙳 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: <code>{}</code> 
★ 𝙵𝚁𝙴𝙴 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: <code>{}</code>"""

    LOG_TEXT_G = """#NewGroup
Group = {}(<code>{}</code>)
Total Members = <code>{}</code>
Added By - {}
"""

    LOG_TEXT_P = """#NewUser
ID - <code>{}</code>
Name - {}
"""

    SPELL_CHECK_TXT = """❌ <b>സിനിമ കണ്ടെത്താനായില്ല!</b>

📌 <b>നിങ്ങൾ തിരഞ്ഞത് :</b> <code>{}</code>

💡 <i>ദയവായി ശരിയായ സ്പെല്ലിംഗ് (Correct Spelling) പരിശോധിച്ച് വീണ്ടും അയക്കുക.</i>

🔍 <b>ഗൂഗിളിൽ സ്പെല്ലിംഗ് നോക്കാൻ താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്യുക.</b>"""
