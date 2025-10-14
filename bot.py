import os
import asyncio
import random
import string
import aiofiles
import aiohttp
import shutil
import zipfile
from pyunpack import Archive
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1002822805641"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

file_store = {}

def gen_key():
    return "file_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def clean_temp(paths):
    for path in paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        key = args[0]
        msg_id = file_store.get(key)
        if msg_id:
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
                "👋 *Hi Admin!*\n\nYou can:\n"
                "• Upload files directly\n"
                "• `/url <link>` — download & upload any file\n"
                "• `/zipextract <link>` — extract & upload ZIP/RAR contents",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("🔒 Use a valid file link to download.")

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only admin can upload.")
    file = update.message.document or update.message.video or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        return await update.message.reply_text("❌ Invalid file type.")
    sent = await update.message.forward(CHANNEL_ID)
    key = gen_key()
    file_store[key] = sent.message_id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={key}"
    await update.message.reply_text(f"✅ Uploaded!\n📎 Public link:\n👉 {link}")

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

        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(extract_folder)
        except zipfile.BadZipFile:
            Archive(zip_path).extractall(extract_folder)

        uploaded = []
        bot_username = (await context.bot.get_me()).username
        for root, _, files in os.walk(extract_folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024:
                    continue
                sent = await context.bot.send_document(chat_id=CHANNEL_ID, document=open(file_path, "rb"),
                                                      caption=f"🗂 Extracted from: {filename}")
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

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("zipextract", zipextract))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_upload))
    app.run_polling()

if __name__ == "__main__":
    main()
