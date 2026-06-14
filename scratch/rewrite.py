import re

file_path = "e:/Autoo/ExpressSetup/telegram-bot/bot/handlers.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

helper_code = """
async def _reply_new(query, text, reply_markup=None):
    \"\"\"Remove keyboard from old message and send a new one.\"\"\"
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    return await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup, quote=False)

"""

# Insert the helper code right above callback_handler
content = content.replace("@restricted\nasync def callback_handler", helper_code + "@restricted\nasync def callback_handler")

# We want to replace single occurrences of:
# await query.edit_message_text(...)
# with:
# await _reply_new(query, ...)

# BUT for loading sequences, we want to replace the first with:
# msg = await _reply_new(query, ...)
# and the second with:
# await msg.edit_text(...)

# Let's just use regex to replace all `await query.edit_message_text(` with `await _reply_new(query, ` first.
# Note: we need to handle multi-line calls.
content = re.sub(r'await query\.edit_message_text\(', r'await _reply_new(query, ', content)

# Now fix the loading states manually by regex matching the specific patterns.
# A loading state looks like:
# await _reply_new(query, "⏳ ...")
# result = await ...
# await _reply_new(query, result...)

loading_pattern = re.compile(r'(await _reply_new\(query,\s*(?:".*?[⏳].*?"|\'.*?[⏳].*?\').*?\))\s*(.*?=\s*await.*?)\s*await _reply_new\(query,\s*(result|stats|log|new_status|prefs)', re.DOTALL)

def fix_loading(m):
    first_call = m.group(1).replace("await _reply_new", "msg = await _reply_new")
    middle = m.group(2)
    third_var = m.group(3)
    # The third part is: await _reply_new(query, result, parse_mode="Markdown", reply_markup=...)
    # We want to change it to: await msg.edit_text(result, parse_mode="Markdown", reply_markup=...)
    return f"{first_call}\n        {middle}\n        await msg.edit_text({third_var}"

# Because the regex might miss some things, let's do a more robust approach:
# We just find all "await _reply_new(query," that have "⏳" in them, and change them to "msg = await _reply_new(query,"
# Then, the next "await _reply_new(query, result" we change to "await msg.edit_text(result"

lines = content.split('\n')
in_loading = False

for i, line in enumerate(lines):
    if "await _reply_new(query," in line and "⏳" in line:
        lines[i] = line.replace("await _reply_new(query,", "msg = await _reply_new(query,")
        in_loading = True
    elif in_loading and "await _reply_new(query," in line:
        lines[i] = line.replace("await _reply_new(query,", "await msg.edit_text(")
        in_loading = False

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Rewrite successful")
