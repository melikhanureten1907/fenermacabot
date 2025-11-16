import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL = 300

app = Flask(__name__)

@app.route("/")
def home():
    return "FenerMacaBot çalışıyor", 200

def keep_alive():
    def run():
        app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
    Thread(target=run).start()

async def send_telegram(bot, msg):
    await bot.send_message(chat_id=TG_CHAT, text=msg)

async def check_mobilet(bot):
    url = "https://mobilet.com/etkinlikler"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            t = a.get_text(strip=True).lower()
            if "fenerbahçe" in t or "beko" in t:
                await send_telegram(bot, f"🎫 Mobilet bileti bulundu: {t}\n{url}")
    except Exception as e:
        print("HATA:", e)

# ---------------------------
#  USER COMMAND HANDLERS
# ---------------------------

async def start(update, context):
    await update.message.reply_text("👋 Merhaba! FenerMacaBot burda.")

async def echo(update, context):
    await update.message.reply_text(f"Aldım kardeşim: {update.message.text}")

# ---------------------------
#  BOT LOOP
# ---------------------------

async def bot_loop():
    bot_app = ApplicationBuilder().token(TG_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    bot = bot_app.bot

    await send_telegram(bot, "✅ FenerMacaBot aktif! (Render Free)")

    asyncio.create_task(bot_app.initialize())
    asyncio.create_task(bot_app.start())
    asyncio.create_task(bot_app.updater.start_polling())

    while True:
        await check_mobilet(bot)
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(bot_loop())
