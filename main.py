!pip install python-telegram-bot==20.6 aiohttp aiofiles pyunpack patool --quiet

import asyncio, random, string, aiofiles, aiohttp, os, zipfile, shutil
from pyunpack import Archive
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ==== CONFIGURATION ====
BOT_TOKEN = "8372763325:AAGQ-ZoOFkSjV1GEokqj4_B9YNMyPWph1g8"  # ⚠️ Replace with your token
CHANNEL_ID = -1002822805641
ADMIN_ID = 8293366242

file_store = {}

# === Helper ===
def gen_key():
    return "file_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def clean_temp(paths):
    for path in paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        key = args[0]
        if key in file_store:
            msg_id = file_store[key]
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
        else:
            await update.message.reply_text("⚠️ Invalid or expired file link.")
    else:
        if update.effective_user.id == ADMIN_ID:
            await update.message.reply_text(
                "👋 *Hi Admin!*\n\nYou can use:\n"
                "• Upload files directly\n"
                "• `/url <link>` — download & upload any file (mp4, mkv, zip, pdf, etc.)\n"
                "• `/zipextract <link>` — extract & upload ZIP/RAR contents",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("🔒 Use a valid file link to download.")

# === Handle uploads ===
async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Only admin can upload.")
        return

    file = update.message.document or update.message.video or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        await update.message.reply_text("❌ Invalid file type.")
        return

    sent = await update.message.forward(CHANNEL_ID)
    key = gen_key()
    file_store[key] = sent.message_id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={key}"
    await update.message.reply_text(f"✅ Uploaded!\n📎 Public link:\n👉 {link}")

# === /url command ===
async def url_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only admin can use this command.")
    if not context.args:
        return await update.message.reply_text("⚠️ Usage:\n`/url https://example.com/file.mp4`", parse_mode="Markdown")

    url = context.args[0]
    filename = url.split("/")[-1] or "file_from_url"
    temp_path = f"/tmp/{filename}"

    await update.message.reply_text(f"📡 Downloading:\n{url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await update.message.reply_text(f"❌ HTTP Error {resp.status}")
                async with aiofiles.open(temp_path, "wb") as f:
                    while chunk := await resp.content.read(1024 * 1024):
                        await f.write(chunk)

        file_size = os.path.getsize(temp_path)
        if file_size > 2 * 1024 * 1024 * 1024:
            return await update.message.reply_text("❌ File exceeds 2 GB limit.")

        sent = await context.bot.send_document(
            chat_id=CHANNEL_ID,
            document=open(temp_path, "rb"),
            caption=f"📤 Uploaded from: {url}"
        )
        key = gen_key()
        file_store[key] = sent.message_id
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={key}"

        await update.message.reply_text(f"✅ Uploaded successfully!\n📎 {link}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        await clean_temp([temp_path])

# === /zipextract command ===
async def zipextract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only admin can extract files.")
    if not context.args:
        return await update.message.reply_text("⚠️ Usage:\n`/zipextract https://example.com/file.zip`", parse_mode="Markdown")

    url = context.args[0]
    filename = url.split("/")[-1] or "archive.zip"
    zip_path = f"/tmp/{filename}"
    extract_folder = f"/tmp/extracted_{gen_key()}"
    os.makedirs(extract_folder, exist_ok=True)

    await update.message.reply_text(f"📦 Downloading archive...\n{url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await update.message.reply_text(f"❌ Failed to download (HTTP {resp.status})")
                async with aiofiles.open(zip_path, "wb") as f:
                    while chunk := await resp.content.read(1024 * 1024):
                        await f.write(chunk)

        Archive(zip_path).extractall(extract_folder)
        uploaded = []
        bot_username = (await context.bot.get_me()).username

        for root, _, files in os.walk(extract_folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024:
                    continue  # skip >2GB
                sent = await context.bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=open(file_path, "rb"),
                    caption=f"🗂 Extracted from: {filename}"
                )
                key = gen_key()
                file_store[key] = sent.message_id
                link = f"https://t.me/{bot_username}?start={key}"
                uploaded.append(f"📎 [{file_name}]({link})")

        if uploaded:
            await update.message.reply_text("✅ Extracted & uploaded:\n" + "\n".join(uploaded), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ No valid files extracted.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        await clean_temp([zip_path, extract_folder])

# === App setup ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("url", url_upload))
app.add_handler(CommandHandler("zipextract", zipextract))
app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_upload))

print("🚀 Bot is running... (press stop to end)")

async def run_bot():
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

asyncio.get_event_loop().create_task(run_bot())
