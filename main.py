"""
main.py
-------
Dastur shu yerdan ishga tushadi:  python main.py

Nima qiladi:
  1. Sozlamalarni tekshiradi (token bormi)
  2. Telegram botni yig'adi va handlerlarni ulaydi
  3. Botni ishga tushiradi
"""

import asyncio
import logging

from aiohttp import web
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters)

import config
from bot.handlers import (start, matn_router, slayd_tahrir_bosildi,
                          tahrir_bekor, hujjat_qabul, rasm_qabul)
from bot.admin import admin_komandasi, admin_callback
from bot.click_webhook import click_web_ilova

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger(__name__)

# Bot bilan suhbat hali BOSHLANMAGAN paytda Telegram bu matnni chatning O'RTASIDA,
# kattaroq va markazlashgan shriftda ko'rsatadi (BotFather'dagi "About" bilan bir xil,
# lekin shu yerda kodda boshqariladi — o'zgartirish uchun faylni tahrirlab qayta ishga tushirish kifoya).
_TOLOV_SUM_STR = f"{config.TOLOV_SUM:,}".replace(",", " ")

BOT_TAVSIF = (
    "✨ Xush kelibsiz!\n\n"
    "Professional AI yordamchi — hujjatlar, taqdimotlar va til ishlari uchun.\n\n"
    f"👑  Slayt yaratish  ·  Premium ({_TOLOV_SUM_STR} so'm)\n"
    "Mavzu asosida zamonaviy, dizaynli va professional PowerPoint taqdimot\n\n"
    "🪄  Matn tuzatish\n"
    ".docx hujjatdagi imlo, grammatika va uslubni mukammal tuzatish\n\n"
    "🧩  Davom ettirish\n"
    "Chala qolgan .docx yoki .pdf hujjatni xuddi shu uslubda to‘liq yakunlash\n\n"
    "📋  Konspekt qilish\n"
    "Uzun matn yoki ma'ruzani (.docx/.pdf) imtihonga tayyor, qisqa konspektga aylantirish\n\n"
    f"👑  Ingliz yordamchisi  ·  Premium ({_TOLOV_SUM_STR} so'm)\n"
    "IELTS baholash, grammatika tuzatish va matnni professional ravonlashtirish\n\n"
    "🌐  Ilmiy tarjima\n"
    "Matn yoki hujjatni o‘zbek, ingliz yoki rus tillariga ilmiy uslubda tarjima\n\n"
    "📚  Filedan test yaratish\n"
    "Word yoki PDF fayldan sifatli Telegram test (quiz) yaratish\n\n"
    "Boshlash uchun «/Start» /start tugmasini bosing."
)

BOT_QISQA_TAVSIF = "👑 Premium slayt/IELTS • 🪄 Tuzatish • 📋 Konspekt • 🌐 Tarjima • 📚 Test"

async def _post_init(app):
    """Bot ishga tushganda BIR MARTA chaqiriladi — Telegram profilidagi
    tavsifni (chat o'rtasida ko'rinadigan matnni) yangilaydi."""
    try:
        await app.bot.set_my_description(description=BOT_TAVSIF)
        await app.bot.set_my_short_description(short_description=BOT_QISQA_TAVSIF)
    except Exception as e:
        log.warning("Bot tavsifini o'rnatishda xato: %s", e)


def main():
    config.tekshir()   # token yo'q bo'lsa, shu yerda tushunarli xato beradi
    if not config.click_sozlangan():
        log.warning(
            "Click sozlanmagan (.env: CLICK_SERVICE_ID/CLICK_SECRET_KEY/CLICK_MERCHANT_ID bo'sh) — "
            "pullik xizmatlar (Slayt yaratish, Ingliz yordamchisi) talabalar uchun ishlamaydi.")

    app = Application.builder().token(config.BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", start))
    # --- admin panel (FAQAT config.ADMIN_ID uchun — /admin ichida tekshiriladi) ---
    app.add_handler(CommandHandler("admin", admin_komandasi))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm:"))
    # --- callbacklar (FAQAT bitta xabarga tegishli, ko'p nusxali amallar —
    #     xizmat/shablon/varaq/daraja tanlash endi botning DOIMIY tugmalari
    #     orqali, oddiy matn sifatida keladi va matn_router orqali ishlanadi) ---
    app.add_handler(CallbackQueryHandler(slayd_tahrir_bosildi, pattern=r"^edit:\d+$"))
    app.add_handler(CallbackQueryHandler(tahrir_bekor, pattern=r"^edit_cancel$"))
    # --- to'lov ekranida FAQAT bitta tugma bor: Click (url) — bekor qilish
    #     pastdagi doimiy 🔁 Bekor qilish (reply klaviatura) orqali, alohida
    #     callback shart emas; to'lovning O'ZI Click orqali avtomatik
    #     (bot/click_webhook.py) ---
    # --- hujjat (har qanday fayl qabul qilinadi — .docx bo'lmasa hujjat_qabul
    #     o'zi tushunarli xabar beradi, aks holda jim o'tkazib yuborilar edi) ---
    app.add_handler(MessageHandler(filters.Document.ALL, hujjat_qabul))
    # --- RASM (faqat admin «Umumiy xabar» uchun; talabadan endi chek so'ralmaydi) ---
    app.add_handler(MessageHandler(filters.PHOTO, rasm_qabul))
    # --- matn ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_router))

    try:
        asyncio.run(_run(app))
    except KeyboardInterrupt:
        pass


async def _run(app):
    """Botni (polling) va — Click sozlangan bo'lsa — Click webhook serverini
    (/click/prepare, /click/complete) BIR XIL asyncio davrasida birga ishga
    tushiradi. Webhook faqat Click COMPLETE'da application.bot/.user_data'ga
    to'g'ridan-to'g'ri kirishi kerak bo'lgani uchun run_polling() ning
    qulay-lekin-bloklovchi qobig'i o'rniga qo'lda boshqariladi."""
    runner = None
    if config.click_sozlangan():
        web_app = click_web_ilova(app)
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, config.CLICK_WEBHOOK_HOST, config.CLICK_WEBHOOK_PORT)
        await site.start()
        log.info("Click webhook server ishga tushdi: %s:%s (/click/prepare, /click/complete)",
                 config.CLICK_WEBHOOK_HOST, config.CLICK_WEBHOOK_PORT)
    else:
        log.info("Click sozlanmagan (.env bo'sh) — pullik xizmatlar ishlamaydi.")

    async with app:
        await app.start()
        await app.updater.start_polling()
        print("✅ Bot ishga tushdi. To'xtatish: Ctrl+C")
        try:
            await asyncio.Event().wait()   # Ctrl+C (KeyboardInterrupt) bosilguncha abadiy kutadi
        finally:
            await app.updater.stop()
            await app.stop()
            if runner:
                await runner.cleanup()


if __name__ == "__main__":
    main()
