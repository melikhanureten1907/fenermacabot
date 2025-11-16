import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL = 300  # saniye

app = Flask(__name__)

@app.route("/")
def home():
    return "FenerMacaBot çalışıyor", 200


# --- TELEGRAM BOT LOOP ---
async def send_telegram(bot, msg):
    await bot.send_message(chat_id=TG_CHAT, text=msg)

async def check_mobilet(bot):
    url = "https://mobilet.com/etkinlikler"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True).lower()
            if "fenerbahçe" in txt or "beko" in txt:
                await send_telegram(bot, f"🎫 Mobilet bileti bulundu:\n{txt}\n{url}")
    except Exception as e:
        print("HATA:", e)

async def bot_loop():
    bot = ApplicationBuilder().token(TG_TOKEN).build().bot
    await send_telegram(bot, "✅ FenerMacaBot aktif! (Render Free)")
    while True:
        await check_mobilet(bot)
        await asyncio.sleep(CHECK_INTERVAL)


# --- ASYNC LOOPU BACKGROUND’TA ÇALIŞTIR ---
def start_bot():
    asyncio.run(bot_loop())


def start_background():
    t = Thread(target=start_bot)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    start_background()
    app.run(host="0.0.0.0", port=10000)
