"""
config.py
---------
Barcha sozlamalar shu yerda, bitta joyda. Sirlar .env faylidan o'qiladi.
Boshqa fayllar sozlamani shu yerdan oladi (kodda token yozib qo'yilmaydi).
"""

import os
from dotenv import load_dotenv

load_dotenv()   # .env faylini yuklaydi

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# AI (OpenAI-mos endpoint: lokal Ollama/LM Studio yoki bulut)
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
AI_API_KEY = os.getenv("AI_API_KEY", "kalit_kerak")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")

# AI rasm (Pollinations — bepul, kalitsiz)
RASM_YOQ = os.getenv("RASM_YOQ", "1") == "1"   # rasm yoqilganmi (0 = o'chirilgan)
IMG_BASE = os.getenv("IMG_BASE", "https://image.pollinations.ai/prompt/")
IMG_MODEL = os.getenv("IMG_MODEL", "flux")

# Rasm provayderi: "pollinations" (bepul, kalitsiz) yoki "gemini" (Nano banana, PULLIK)
IMG_PROVIDER = os.getenv("IMG_PROVIDER", "pollinations")
IMG_MODEL_G = os.getenv("IMG_MODEL_G", "gemini-3.1-flash-image-preview")  # Nano banana
IMG_KEY = os.getenv("IMG_KEY", "") or AI_API_KEY  # bo'sh bo'lsa Gemini matn kaliti

# Together AI (Flux) — arzon, sifatli
IMG_TOGETHER_KEY = os.getenv("IMG_TOGETHER_KEY", "")
IMG_TOGETHER_MODEL = os.getenv("IMG_TOGETHER_MODEL", "black-forest-labs/FLUX.2-dev")

# "Matn tuzatish" xizmati uchun ALOHIDA Gemini sozlamalari (slayt AI kalitiga tegmaydi —
# boshqa akkaunt/kalit ishlatish mumkin, limitlar aralashmasin deb).
TUZAT_BASE_URL = os.getenv("TUZAT_BASE_URL", "") or AI_BASE_URL
TUZAT_KEY = os.getenv("TUZAT_KEY", "") or AI_API_KEY
TUZAT_MODEL = os.getenv("TUZAT_MODEL", "") or AI_MODEL

# "Til bo'limi" (Ingliz yordamchisi + Ilmiy tarjima) uchun ALOHIDA Gemini sozlamalari
# (boshqa bo'limlar kalitiga tegmaydi, limitlar aralashmasin deb).
TIL_BASE_URL = os.getenv("TIL_BASE_URL", "") or AI_BASE_URL
TIL_KEY = os.getenv("TIL_KEY", "") or AI_API_KEY
TIL_MODEL = os.getenv("TIL_MODEL", "") or AI_MODEL

# "Konspekt qilish" xizmati uchun ALOHIDA Gemini sozlamalari (bo'sh qolsa AI_* ishlatiladi).
KONSPEKT_BASE_URL = os.getenv("KONSPEKT_BASE_URL", "") or AI_BASE_URL
KONSPEKT_KEY = os.getenv("KONSPEKT_KEY", "") or AI_API_KEY
KONSPEKT_MODEL = os.getenv("KONSPEKT_MODEL", "") or AI_MODEL

# Yo'llar
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
GRID_IMAGE = os.path.join(ASSETS_DIR, "template_grid.jpg")

# Pullik xizmatlar narxi (standart, adminpanel narx belgilamagan bo'lsa).
# ADMIN_ID — admin panel (/admin) va admin<->talaba chatini ishlatadigan
# odamning Telegram RAQAM ID'si (username emas!) — @userinfobot ga /start
# bosib olinadi.
TOLOV_SUM = int(os.getenv("TOLOV_SUM", "5000"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

# Click (https://docs.click.uz — Shop API: Prepare + Complete webhook) —
# YAGONA to'lov usuli. Bo'sh qolsa, pullik xizmatlar ISHLAMAYDI (talabaga
# tushunarli xato ko'rsatiladi) — to'lov qabul qilish uchun bu sozlangan bo'lishi SHART.
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "")
CLICK_PAY_BASE = os.getenv("CLICK_PAY_BASE", "https://my.click.uz/services/pay")
CLICK_RETURN_URL = os.getenv("CLICK_RETURN_URL", "")   # to'lovdan keyin qaytariladigan sahifa (ixtiyoriy)
# Webhook web-server (Click bizga POST yuboradigan joy) qaysi portda ochilsin.
# MUHIM: bu server ORQASIDA haqiqiy ochiq HTTPS domen bo'lishi SHART (masalan
# nginx/Caddy orqali, yoki Railway/Render kabi platforma) — Click'ning o'zi
# faqat HTTPS'ga so'rov yubora oladi, shu portga TO'G'RIDAN-TO'G'RI emas.
# PORT — Railway (va ko'plab boshqa PaaS'lar) konteynerga QAYSI portni
# TASHQARIGA (HTTPS domenga) ulashini shu orqali AVTOMATIK aytadi — shu sabab
# CLICK_WEBHOOK_PORT'dan USTUN turadi (mavjud bo'lsa).
CLICK_WEBHOOK_HOST = os.getenv("CLICK_WEBHOOK_HOST", "0.0.0.0")
CLICK_WEBHOOK_PORT = int(os.getenv("PORT") or os.getenv("CLICK_WEBHOOK_PORT", "8080") or "8080")


def click_sozlangan():
    """Click to'lov tizimi ishlatish uchun YETARLI sozlangan-sozlanmaganini
    aytadi (asosiy 3 maydon bo'lsa yetarli — merchant_user_id ba'zi
    hisoblarda shart emas)."""
    return bool(CLICK_SERVICE_ID and CLICK_SECRET_KEY and CLICK_MERCHANT_ID)


def tekshir():
    """Ishga tushishdan oldin muhim sozlamalar borligini tekshiradi."""
    if not BOT_TOKEN or BOT_TOKEN == "bu_yerga_token":
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylini oching va tokenni yozing."
        )
