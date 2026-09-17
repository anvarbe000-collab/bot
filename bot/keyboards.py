"""
bot/keyboards.py — barcha klaviaturalar.

IKKI XIL tugma bor, bot konventsiyasiga muvofiq:
  1) DOIMIY (ReplyKeyboardMarkup) — ketma-ket, BITTA tanlov qilinadigan
     navigatsiya bosqichlari uchun (xizmat, shablon, varaq soni, daraja).
     Bular bosilganda oddiy MATN sifatida keladi (bot/handlers.py:matn_router).
  2) INLINE (InlineKeyboardMarkup) — muayyan BITTA xabarga tegishli, ko'p
     nusxada bo'ladigan amallar uchun (har slaydning o'z "Tahrirlash" tugmasi,
     "Yaratish/Bekor qilish"). Bularni doimiy tugma qila olmaysiz — har bir
     slayd o'z alohida tugmasiga muhtoj.
"""

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton)
from slides.design import TEMPLATES, RUYXAT

# ---------- 1) DOIMIY (almashinuvchi) tugmalar ----------

SLAYT_TUGMA = "🎨 Slayt yaratish"
TUZAT_TUGMA = "🪄 Matn tuzatish"
DAVOM_TUGMA = "🧩 Davom ettirish"
KONSPEKT_TUGMA = "📋 Konspekt qilish"
INGLIZ_TUGMA = "🇬🇧 Ingliz yordamchisi"
TARJIMA_TUGMA = "🌐 Ilmiy tarjima"
ORQAGA_TUGMA = "◀️ Orqaga"
IMLO_TUGMA = "🔍 Imlo"
RAVON_TUGMA = "🌟 Ravon"
TEST_TUGMA = "📚 Filedan test yaratish"
ADMIN_XABAR_TUGMA = "💬 Adminga xabar"

# Faqat ADMIN uchun (config.ADMIN_ID) — /start bosganda oddiy foydalanuvchi
# menyusi O'RNIGA shu ikkisi ko'rsatiladi (bot/handlers.py:start).
ADMIN_PANEL_TUGMA = "🛡 Admin panel"
FOYDALANUVCHI_REJIMI_TUGMA = "👤 Foydalanuvchi rejimi"

DARAJA_LABEL_KEY = {IMLO_TUGMA: "imlo", RAVON_TUGMA: "ravon"}

# Word/PDF fayldan Telegram test (quiz) yaratadigan alohida bot — TEST_TUGMA
# bosilganda shu botga o'tuvchi havola yuboriladi (bot/handlers.py:_filedan_test_yaratish).
# ReplyKeyboardMarkup tugmasi URL ochib bera olmaydi (Telegram cheklovi), shu
# sabab bosilgach botga matn keladi, bot esa javoban toza havola qaytaradi.
FILE_QUIZ_BOT_USERNAME = "FileQuizMakerBot"


def bosh_klaviatura():
    """Botning bosh menyusi — YETTITA xizmat + adminga xabar, har doim shu
    tartibda va ko'rinishda qaytiladi."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(SLAYT_TUGMA), KeyboardButton(TUZAT_TUGMA)],
         [KeyboardButton(DAVOM_TUGMA), KeyboardButton(KONSPEKT_TUGMA)],
         [KeyboardButton(INGLIZ_TUGMA), KeyboardButton(TARJIMA_TUGMA)],
         [KeyboardButton(TEST_TUGMA), KeyboardButton(ADMIN_XABAR_TUGMA)]],
        resize_keyboard=True, is_persistent=True)


def admin_bosh_klaviatura():
    """ADMIN uchun DOIMIY tugmalar — /start bosganda oddiy foydalanuvchi
    menyusi o'rniga shu ko'rsatiladi (bot doim "admin rejimi"da ochiladi,
    /user buyrug'i bilan vaqtincha oddiy menyuga o'tish mumkin)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ADMIN_PANEL_TUGMA)],
         [KeyboardButton(FOYDALANUVCHI_REJIMI_TUGMA)]],
        resize_keyboard=True, is_persistent=True)


def shablon_reply_klaviatura():
    """Shablon tanlash — 8 ta doimiy tugma (2 tadan qatorda) + Orqaga."""
    tugmalar, qator = [], []
    for i, key in enumerate(RUYXAT, 1):
        t = TEMPLATES[key]
        qator.append(KeyboardButton(f"{t['emoji']} {t['nom']}"))
        if i % 2 == 0:
            tugmalar.append(qator); qator = []
    if qator:
        tugmalar.append(qator)
    tugmalar.append([KeyboardButton(ORQAGA_TUGMA)])
    return ReplyKeyboardMarkup(tugmalar, resize_keyboard=True)


SHABLON_LABEL_KEY = {f"{TEMPLATES[k]['emoji']} {TEMPLATES[k]['nom']}": k for k in RUYXAT}

# 3 — birinchi marta uchun BEPUL sinov varianti (keyingi safar boshqalar kabi
# pullik bo'lib qoladi). Doim RO'YXAT BOSHIDA — yangi foydalanuvchi birinchi
# ko'radigan tanlov shu bo'lsin deb.
VARAQ_TANLOV = [3, 5, 7, 10, 12, 15]
VARAQ_BEPUL_N = 3


def _varaq_tugma_matni(n, pullik, bepul_mavjudmi, narx):
    if not pullik:
        return f"📄 {n}"   # "Slayt yaratish" hozircha butunlay bepul (admin o'chirgan) — narx ko'rsatilmaydi
    if n == VARAQ_BEPUL_N and bepul_mavjudmi:
        return f"📄 {n} (Bepul)"
    return f"📄 {n} ({narx:,} so'm)".replace(",", " ")


def varaq_reply_klaviatura(pullik, bepul_mavjudmi=False, narx=0):
    """Varaqlar soni — doimiy tugmalar + Orqaga. "Slayt yaratish" pullik
    (admin panelda yoqilgan) bo'lsa har tugma ustida narxi (yoki 3 — hali
    bepul sinov ishlatilmagan bo'lsa "Bepul") ko'rsatiladi; butunlay bepul
    bo'lsa (admin o'chirgan) faqat oddiy raqamlar ko'rsatiladi."""
    q = [KeyboardButton(_varaq_tugma_matni(n, pullik, bepul_mavjudmi, narx)) for n in VARAQ_TANLOV]
    satrlar = [q[i:i + 3] for i in range(0, len(q), 3)]
    satrlar.append([KeyboardButton(ORQAGA_TUGMA)])
    return ReplyKeyboardMarkup(satrlar, resize_keyboard=True)


def varaq_dan_n(matn):
    """Tugma matnidan ("📄 3 (Bepul)" yoki "📄 12 (5000 so'm)") varaq sonini
    ajratib oladi — narx/"Bepul" qismi o'zgarib turgani uchun ANIQ (tayyor)
    lug'at o'rniga tugma matni BOSHIDAGI raqamni o'qiydi."""
    if not matn.startswith("📄 "):
        return None
    raqam = matn[2:].split()[0].strip()
    if raqam.isdigit() and int(raqam) in VARAQ_TANLOV:
        return int(raqam)
    return None


def tuzat_daraja_reply_klaviatura():
    """Matn tuzatish darajasi — doimiy tugmalar + Orqaga."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(IMLO_TUGMA), KeyboardButton(RAVON_TUGMA)],
         [KeyboardButton(ORQAGA_TUGMA)]],
        resize_keyboard=True)


IELTS_TUGMA = "📝 IELTS baholash"
GRAMMAR_TUGMA = "🔤 Grammatika"

INGLIZ_DARAJA_LABEL_KEY = {IELTS_TUGMA: "ielts", GRAMMAR_TUGMA: "grammar", RAVON_TUGMA: "ravon"}


def ingliz_daraja_reply_klaviatura():
    """Ingliz yordamchisi tanlovlari — doimiy tugmalar + Orqaga."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(IELTS_TUGMA)],
         [KeyboardButton(GRAMMAR_TUGMA), KeyboardButton(RAVON_TUGMA)],
         [KeyboardButton(ORQAGA_TUGMA)]],
        resize_keyboard=True)


TIL_UZ_TUGMA = "🇺🇿 O'zbekchaga"
TIL_EN_TUGMA = "🇬🇧 Inglizchaga"
TIL_RU_TUGMA = "🇷🇺 Ruschaga"

TARJIMA_TIL_LABEL_KEY = {TIL_UZ_TUGMA: "uz", TIL_EN_TUGMA: "en", TIL_RU_TUGMA: "ru"}


def tarjima_til_reply_klaviatura():
    """Tarjima maqsad tili — doimiy tugmalar + Orqaga."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(TIL_UZ_TUGMA), KeyboardButton(TIL_EN_TUGMA)],
         [KeyboardButton(TIL_RU_TUGMA)],
         [KeyboardButton(ORQAGA_TUGMA)]],
        resize_keyboard=True)


YARATISH_TUGMA = "✅ Yaratish"
BEKOR_TUGMA = "🔁 Bekor qilish"


def reja_reply_klaviatura():
    """Reja (slaydlarni ko'rib chiqish) bosqichida — asosiy 6 tugma O'RNIGA shu
    ikkitasi ko'rsatiladi, toki foydalanuvchi tasodifan boshqa xizmatni bosib,
    joriy slayd ishini uzib qo'ymasin (bosh menyu Yaratish/Bekordan keyin qaytadi)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(YARATISH_TUGMA), KeyboardButton(BEKOR_TUGMA)]],
        resize_keyboard=True)


def bekor_reply_klaviatura():
    """To'lov (Click) kutilayotganda — asosiy tugmalar O'RNIGA FAQAT Bekor
    qilish ko'rsatiladi (istalgan pullik xizmat uchun umumiy), toki
    foydalanuvchi tasodifan boshqa xizmatga o'tib, to'lov jarayonini uzib
    qo'ymasin (bosh menyu to'lov tugagach yoki bekor qilingach qaytadi)."""
    return ReplyKeyboardMarkup([[KeyboardButton(BEKOR_TUGMA)]], resize_keyboard=True)


# ---------- 2) INLINE tugmalar (bitta xabarga tegishli, ko'p nusxali amallar) ----------

def slayd_tahrir_tugmasi(i):
    """Bitta slayt xabari ostidagi yagona tugma. callback = 'edit:<i>'."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit:{i}")]])


def tahrir_klaviatura():
    """Slayd tahrirlash rejimida — orqaga qaytish tugmasi. callback = 'edit_cancel'."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bekor qilish", callback_data="edit_cancel")]])


def tolov_amal_klaviaturasi(click_url):
    """To'lov ekranidagi YAGONA tugma — Click orqali to'lash (avtomatik).
    Bekor qilish uchun pastdagi doimiy 🔁 Bekor qilish tugmasi (reply
    klaviatura) yetarli — qo'shimcha inline tugmalar chalg'itmasin deb
    qo'yilmagan."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Click orqali to'lash", url=click_url)],
    ])


def admin_talaba_javob_klaviaturasi(talaba_chat_id):
    """Adminga forward qilingan talaba xabari OSTIDAGI tugma — bosilganda
    ANIQ shu talaba "faol suhbat" qilib belgilanadi (bir nechta talaba BIR
    VAQTDA yozganda ham, admin Telegramning "Reply" funksiyasidan foydalanmasa
    ham, keyingi oddiy matn TO'G'RI odamga borishi uchun).
    callback = 'admjav:<talaba_chat_id>'."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        "↩️ Shu foydalanuvchiga javob yozish", callback_data=f"admjav:{talaba_chat_id}")]])
