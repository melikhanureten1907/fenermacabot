import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# ---------------------------------------
#   TOKENLER ORTAM DEĞİŞKENLERİNDEN GELMELİ
# ---------------------------------------
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL = 300  # 5 dakika

# ---------------------------------------
#   FLASK KEEP-ALIVE SERVER (Render için)
# ---------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "FenerMacaBot çalışıyor!", 200

def keep_alive():
    def run():
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    Thread(target=run).start()

# ---------------------------------------
#   TELEGRAM GÖNDERİCİ
# ---------------------------------------
async def send_telegram(app, msg):
    await app.bot.send_message(chat_id=TG_CHAT, text=msg)

# ---------------------------------------
#   MOBILET SCRAPER
# ---------------------------------------
async def check_mobilet(app):
    url = "https://mobilet.com/etkinlikler"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True).lower()
            if "fenerbahçe" in title or "beko" in title:
                await send_telegram(app, f"🎟️ Mobilet bileti: {title}\n{url}")

    except Exception as e:
        print("HATA:", e)

# ---------------------------------------
#   /start KOMUTU
# ---------------------------------------
async def start(update, context):
    await update.message.reply_text("👋 Merhaba! FenerMacaBot burda.")

async def echo(update, context):
    await update.message.reply_text(f"Aldım kardeşim: {update.message.text}")

# ---------------------------------------
#   BOT ANA DÖNGÜ
# ---------------------------------------
async def main():
    application = ApplicationBuilder().token(TG_TOKEN).build()

    # Komutlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Telegram botu başlat
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Bot açıldığında telegram'a mesaj gönder
    await send_telegram(application, "✅ FenerMacaBot aktif! (Render)")

    # Sürekli Mobilet kontrolü
    while True:
        await check_mobilet(application)
        await asyncio.sleep(CHECK_INTERVAL)

# ---------------------------------------
#   ÇALIŞTIR
# ---------------------------------------
if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())

