"""
ai/docx_tuzat.py — .docx faylni "Matn tuzatish" (imlo/ravon) funksiyasi bilan
qayta ishlaydi, FORMAT SAQLANADI. Umumiy paragraf-guruhlash dvigateli
ai/docx_umumiy.py dan olinadi (kod takrorlanmasin).
"""

from config import TUZAT_BASE_URL, TUZAT_KEY, TUZAT_MODEL
from ai.docx_umumiy import docx_ni_ishla
from ai._runtime import client_va_model

_OGOHLANTIRISH = (
    "\n\nJUDA MUHIM: kirishdagi ro'yxatda NECHTA bo'lak bo'lsa, chiqishda ham "
    "AYNAN SHUNCHA bo'lak bo'lishi SHART — bittasi ham ko'p, bittasi ham kam emas. "
    "Bitta bo'lak ICHIDA qator ko'chirish (\\n) yoki bir nechta gap bo'lishi mumkin — "
    "buni HECH QACHON alohida ro'yxat elementlariga BO'LIB YUBORMA, uni BUTUN "
    "HOLICHA bitta elementda qaytar."
)

_SYSTEM = {
    "imlo": (
        "Sen o'zbek tili (LOTIN alifbosida) imlo va grammatika mutaxassisisan. "
        "Senga JSON RO'YXAT ko'rinishida matn bo'laklari beriladi. Har bir bo'lakda "
        "FAQAT imlo, tinish belgisi, kelishik va qo'shimcha xatolarini tuzat — "
        "ma'no, uslub va tuzilishni o'zgartirma. Kirillcha bo'lsa lotinga o'gir. "
        "Bo'sh, raqamli yoki maxsus belgilardan iborat bo'laklarni O'ZGARTIRMASDAN qaytar."
        + _OGOHLANTIRISH +
        "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar "
        "(masalan [\"...\", \"...\"]) — boshqa hech narsa, izoh yoki ``` yozma."
    ),
    "ravon": (
        "Sen o'zbek tili (LOTIN alifbosida) muharrir-tahririyot mutaxassisisan. "
        "Senga JSON RO'YXAT ko'rinishida matn bo'laklari beriladi. Har bir bo'lakni "
        "imlo, grammatika, tinish belgilari jihatidan to'g'rila VA jumlalarni adabiy "
        "tilga mosroq, ravonroq qil — lekin ASOSIY MA'NONI o'zgartirma. Kirillcha "
        "bo'lsa lotinga o'gir. Bo'sh, raqamli yoki maxsus belgilardan iborat "
        "bo'laklarni O'ZGARTIRMASDAN qaytar."
        + _OGOHLANTIRISH +
        "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar "
        "(masalan [\"...\", \"...\"]) — boshqa hech narsa, izoh yoki ``` yozma."
    ),
}

_SYSTEM_QAYTA = (
    "Senga JSON RO'YXAT ko'rinishida, allaqachon bir marta tuzatilgan matn "
    "bo'laklari beriladi. Har birini yana bir bor diqqat bilan tekshir — QOLGAN "
    "imlo/grammatika xatosi bo'lsa tuzat, bo'lmasa O'ZGARTIRMASDAN qaytar."
    + _OGOHLANTIRISH +
    "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar — boshqa hech "
    "narsa, izoh yoki ``` yozma."
)

_SYSTEM_BITTA = {
    "imlo": (
        "Sen o'zbek tili (LOTIN alifbosida) imlo va grammatika mutaxassisisan. "
        "Quyidagi matnda FAQAT imlo, tinish belgisi, kelishik va qo'shimcha "
        "xatolarini tuzat — ma'no, uslub, tuzilish va qator ko'chirishlarni (\\n) "
        "o'zgartirma. Kirillcha bo'lsa lotinga o'gir. Faqat tuzatilgan matnni "
        "qaytar — izoh, tirnoq belgisi QO'YMA."
    ),
    "ravon": (
        "Sen o'zbek tili (LOTIN alifbosida) muharrir-tahririyot mutaxassisisan. "
        "Quyidagi matnni imlo, grammatika, tinish belgilari jihatidan to'g'rila va "
        "adabiy tilga mosroq qil — lekin ASOSIY MA'NONI va qator ko'chirishlarni (\\n) "
        "o'zgartirma. Kirillcha bo'lsa lotinga o'gir. Faqat tuzatilgan matnni "
        "qaytar — izoh, tirnoq belgisi QO'YMA."
    ),
}

_SYSTEM_BITTA_QAYTA = (
    "Quyidagi matn allaqachon bir marta tuzatilgan. Uni yana bir bor tekshir — "
    "qolgan xato bo'lsa tuzat, bo'lmasa O'ZGARTIRMASDAN aynan qaytar. Qator "
    "ko'chirishlarni (\\n) saqlab qol. Faqat yakuniy matnni qaytar — izoh yozma."
)


def docx_ni_tuzat(kirish_yol: str, chiqish_yol: str, daraja: str = "imlo"):
    """.docx faylni ochib, matnini tuzatadi (format saqlanadi), yangi faylga saqlaydi.
    daraja: 'imlo' yoki 'ravon'. Hujjat juda katta bo'lsa ValueError ko'taradi.

    Qaytaradi: (chiqish_yol, ozgarishlar, jami_tekshirilgan)
    """
    system = _SYSTEM.get(daraja, _SYSTEM["imlo"])
    bitta_system = _SYSTEM_BITTA.get(daraja, _SYSTEM_BITTA["imlo"])
    client, model = client_va_model("tuzat", TUZAT_BASE_URL, TUZAT_KEY, TUZAT_MODEL)
    return docx_ni_ishla(client, model, kirish_yol, chiqish_yol,
                         system, bitta_system, _SYSTEM_QAYTA, _SYSTEM_BITTA_QAYTA)
