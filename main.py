import os
import asyncio
import json
import requests
from threading import Thread

from flask import Flask
from bs4 import BeautifulSoup

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ------------------------------------------------------------------
#  TELEGRAM AYARLARI (Render veya sistem ortam değişkenlerinden)
# ------------------------------------------------------------------
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")      # Render Env: TELEGRAM_TOKEN
TG_CHAT_FALLBACK = os.getenv("TELEGRAM_CHAT_ID")  # İstersen kullanılabilir ama zorunlu değil

CHECK_INTERVAL = 300  # saniye (abonelik kontrol süresi)
ABONE_DOSYA = "aboneler.json"

# ------------------------------------------------------------------
#  FLASK – UptimeRobot / Render health check
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "FenerMacaBot çalışıyor!", 200


def run_flask():
    # Render Free PORT ortam değişkenini veriyor, yoksa 10000 kullan
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------
#  JSON Abonelik Veri Tabanı
# ------------------------------------------------------------------
def aboneleri_yukle() -> dict:
    if not os.path.exists(ABONE_DOSYA):
        return {}
    try:
        with open(ABONE_DOSYA, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[HATA] aboneleri_yukle:", e)
        return {}


def aboneleri_kaydet(data: dict) -> None:
    try:
        with open(ABONE_DOSYA, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[HATA] aboneleri_kaydet:", e)

# ------------------------------------------------------------------
#  Süper Lig Takım İsimleri ve Logolarını beIN Sports'tan Çek
# ------------------------------------------------------------------
def super_lig_takimlarini_yukle() -> dict:
    """
    https://beinsports.com.tr/lig/super-lig/puan-durumu
    sayfasından takım isimlerini ve logo src'lerini yakalamaya çalışır.
    Yapı değişirse CSS seçicileri güncellemek gerekebilir.
    Dönüş: { "Fenerbahçe": "logo_url", ... }
    """
    url = "https://beinsports.com.tr/lig/super-lig/puan-durumu"
    takimlar = {}

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Generic yaklaşım: her satırda img + takım ismi var varsayımı
        for tr in soup.find_all("tr"):
            img = tr.find("img")
            if not img:
                continue

            # Takım adı img alt veya title'dan gelir
            isim = img.get("alt") or img.get("title")
            if not isim:
                continue

            isim = isim.strip()
            # Logo URL
            logo = img.get("src")
            if logo and logo.startswith("//"):
                logo = "https:" + logo

            if isim and isim not in takimlar:
                takimlar[isim] = logo

    except Exception as e:
        print("[HATA] super_lig_takimlarini_yukle:", e)

    # Eğer hiçbir şey çekemediyse yedek statik liste
    if not takimlar:
        takimlar = {
            "Fenerbahçe": None,
            "Galatasaray": None,
            "Beşiktaş": None,
            "Trabzonspor": None,
            "Başakşehir FK": None,
        }

    print(f"[INFO] {len(takimlar)} takım yüklendi.")
    return takimlar


TAKIMLAR = super_lig_takimlarini_yukle()

# ------------------------------------------------------------------
#  Telegram yardımcı fonksiyonlar
# ------------------------------------------------------------------
async def send_text_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, text: str):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print("[HATA] send_text_to_chat:", e)


def build_takim_keyboard() -> InlineKeyboardMarkup:
    """Süper Lig takımlarından inline buton listesi üretir."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for isim in sorted(TAKIMLAR.keys()):
        keyboard.append([
            InlineKeyboardButton(
                text=isim,
                callback_data=f"team:{isim}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

# ------------------------------------------------------------------
#  Bilet sitelerinde takım adına göre arama
# ------------------------------------------------------------------
BILET_SITELERI = [
    ("Mobilet",    "https://mobilet.com/etkinlikler",          "https://mobilet.com"),
    ("Passo",      "https://www.passo.com.tr/tr/etkinlik-spor","https://www.passo.com.tr"),
    ("Biletinial", "https://www.biletinial.com/tr-tr/spor",    "https://www.biletinial.com"),
]


def ara_bilet_linkleri(takim: str) -> list[tuple[str, str]]:
    """
    Verilen takım için Mobilet, Passo, Biletinial gibi sitelerde
    takım adını içeren etkinlik linklerini arar.
    Dönüş: [(site_adi, url), ...]
    """
    takim_lower = takim.lower()
    sonuc: list[tuple[str, str]] = []

    for site_adi, base_url, host in BILET_SITELERI:
        try:
            r = requests.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            bulundu = False
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if takim_lower in text:
                    href = a["href"]
                    if href.startswith("http"):
                        full_url = href
                    else:
                        if href.startswith("/"):
                            full_url = host + href
                        else:
                            full_url = host + "/" + href
                    sonuc.append((site_adi, full_url))
                    bulundu = True
                    break  # aynı siteden ilk eşleşme yeter
            if not bulundu:
                print(f"[INFO] {site_adi} içinde {takim} bulunamadı.")
        except Exception as e:
            print(f"[HATA] {site_adi} taramada hata: {e}")

    return sonuc

# ------------------------------------------------------------------
#  /start komutu
# ------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        "👋 Merhaba, ben FenerMacaBot.\n\n"
        "Hangi takımın maçına bilet arıyorsunuz?\n"
        "Aşağıdaki listeden bir Süper Lig takımı seçin 👇"
    )
    await update.message.reply_text(text, reply_markup=build_takim_keyboard())


# ------------------------------------------------------------------
#  Takım seçildiğinde (callback)
# ------------------------------------------------------------------
async def cb_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # örn: "team:Fenerbahçe"
    _, takim = data.split(":", 1)
    takim = takim.strip()

    await query.edit_message_text(
        text=f"🔍 {takim} için bilet arıyorum, lütfen bekleyin..."
    )

    # Senkron bilet aramasını async fonksiyonda to_thread ile yapabiliriz
    links = await asyncio.to_thread(ara_bilet_linkleri, takim)

    if links:
        msg_lines = [f"🎫 {takim} için aşağıdaki sitelerde bilet buldum:"]
        for site_adi, url in links:
            msg_lines.append(f"• {site_adi}: {url}")

        msg_text = "\n".join(msg_lines)
        await query.edit_message_text(text=msg_text)
    else:
        # Bilet yok, abonelik sor
        keyboard = [
            [
                InlineKeyboardButton("Evet, bilet çıkınca haber ver", callback_data=f"notify_yes:{takim}"),
                InlineKeyboardButton("Hayır", callback_data="notify_no")
            ]
        ]
        await query.edit_message_text(
            text=(
                f"❌ Şu anda {takim} için aktif bilet bulamadım.\n\n"
                f"📢 Bilet satışa çıktığında sana bildirim göndermemi ister misin?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ------------------------------------------------------------------
#  Abonelik onayı (notify_yes / notify_no)
# ------------------------------------------------------------------
async def cb_notify_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # örn: "notify_yes:Fenerbahçe"
    _, takim = data.split(":", 1)
    takim = takim.strip()
    user_id = str(query.from_user.id)

    aboneler = aboneleri_yukle()
    if takim not in aboneler:
        aboneler[takim] = []
    if user_id not in aboneler[takim]:
        aboneler[takim].append(user_id)
        aboneleri_kaydet(aboneler)

    await query.edit_message_text(
        text=f"📌 Tamamdır, {takim} maçı için bilet satışa çıktığında sana Telegram üzerinden haber vereceğim."
    )


async def cb_notify_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Tamamdır, abonelik kaydedilmedi. İstediğin zaman /start ile tekrar takım seçebilirsin."
    )

# ------------------------------------------------------------------
#  Serbest metin mesajlar (echo)
# ------------------------------------------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if "bilet" in text:
        await update.message.reply_text("🎟 Hangi takım için bilet aradığını belirtmek için /start komutunu kullan :)")
    else:
        await update.message.reply_text("Mesajını aldım. Bilet aramak için /start yazabilirsin.")

# ------------------------------------------------------------------
#  JobQueue ile abonelik kontrolü (belli aralıklarla)
# ------------------------------------------------------------------
async def job_check_abonelik(context: ContextTypes.DEFAULT_TYPE):
    """
    Kayıtlı abonelikleri dolaşır, her takım için tekrar bilet arar.
    Bilet bulunursa ilgili kullanıcılara mesaj gönderir ve abonelikten çıkarır.
    """
    aboneler = aboneleri_yukle()
    if not aboneler:
        return

    for takim, user_list in list(aboneler.items()):
        links = await asyncio.to_thread(ara_bilet_linkleri, takim)
        if not links:
            continue

        # Bilet bulundu → tüm abonelere gönder
        msg_lines = [f"📢 {takim} için bilet bulundu!"]
        for site_adi, url in links:
            msg_lines.append(f"• {site_adi}: {url}")
        msg_text = "\n".join(msg_lines)

        for user_id in user_list:
            try:
                await context.bot.send_message(chat_id=int(user_id), text=msg_text)
            except Exception as e:
                print("[HATA] job_check_abonelik send_message:", e)

        # Bu takım için aboneliği sıfırla (tekrarlı bildirim olmasın)
        aboneler.pop(takim, None)
        aboneleri_kaydet(aboneler)

# ------------------------------------------------------------------
#  MAIN
# ------------------------------------------------------------------
async def main():
    application = ApplicationBuilder().token(TG_TOKEN).build()

    # Komutlar
    application.add_handler(CommandHandler("start", cmd_start))

    # Callback query handler'lar (takım seçimi & abonelik onayı)
    application.add_handler(CallbackQueryHandler(cb_team_selected, pattern=r"^team:"))
    application.add_handler(CallbackQueryHandler(cb_notify_yes, pattern=r"^notify_yes:"))
    application.add_handler(CallbackQueryHandler(cb_notify_no, pattern=r"^notify_no$"))

    # Serbest metin
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # JobQueue: abonelik kontrolü
    application.job_queue.run_repeating(job_check_abonelik, interval=CHECK_INTERVAL, first=60)

    print("[INFO] Telegram bot başlatılıyor...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("[INFO] FenerMacaBot polling aktif.")

    # Bot çalışırken ana task bloklanmasın diye:
    await application.updater.wait_for_stop()


if __name__ == "__main__":
    # Flask'ı ayrı thread'de çalıştır (Render / UptimeRobot için)
    Thread(target=run_flask, daemon=True).start()

    # Telegram botu asyncio ile başlat
    asyncio.run(main())
