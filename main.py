import os, asyncio, requests
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder

# ---------------------------
# BURAYA YENİ TOKENİ YAZACAKSIN
TG_TOKEN = "7758488803:AAEK-q8GOkUx87qnPkmBer65hD1hl2YIzvk"
TG_CHAT  = "1388058967"
# ---------------------------

CHECK_INTERVAL = 300  # saniye

app = Flask(__name__)

@app.route("/")
def home():
    return "FenerMacaBot çalışıyor", 200

def keep_alive():
    def run():
        app.run(host='0.0.0.0', port=8080)
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

async def main_loop():
    bot = ApplicationBuilder().token(TG_TOKEN).build().bot
    await send_telegram(bot, "✅ FenerMacaBot aktif")
    while True:
        await check_mobilet(bot)
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main_loop())
