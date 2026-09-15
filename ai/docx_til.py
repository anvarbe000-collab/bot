"""
ai/docx_til.py — .docx faylni "Til bo'limi" funksiyalari bilan qayta ishlaydi
(ingliz grammatikasi, ravonlashtirish, ilmiy tarjima) — FORMAT SAQLANADI.
Umumiy paragraf-guruhlash dvigateli ai/docx_umumiy.py dan olinadi (kod
takrorlanmasin — ai/docx_tuzat.py bilan bir xil mexanizm, boshqa promptlar).
"""

from config import TIL_BASE_URL, TIL_KEY, TIL_MODEL
from ai.docx_umumiy import docx_ni_ishla
from ai._runtime import client_va_model

_OGOHLANTIRISH = (
    "\n\nJUDA MUHIM: kirishdagi ro'yxatda NECHTA bo'lak bo'lsa, chiqishda ham "
    "AYNAN SHUNCHA bo'lak bo'lishi SHART. Bo'lak ICHIDAGI qator ko'chirishlarni "
    "(\\n) alohida elementlarga BO'LIB YUBORMA — uni BUTUN HOLICHA bitta "
    "elementda qaytar."
)

_SYSTEM_GRAMMAR = (
    "Sen ingliz tili grammatika mutaxassisisan (Grammarly kabi). Senga JSON "
    "RO'YXAT ko'rinishida ingliz matn bo'laklari beriladi. Har bir bo'lakda "
    "FAQAT grammatika, imlo va tinish belgilari xatolarini tuzat — ma'no va "
    "uslubni o'zgartirma. Bo'sh, raqamli yoki maxsus belgilardan iborat "
    "bo'laklarni O'ZGARTIRMASDAN qaytar."
    + _OGOHLANTIRISH +
    "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar — boshqa "
    "hech narsa, izoh yoki ``` yozma."
)
_SYSTEM_GRAMMAR_BITTA = (
    "Sen ingliz tili grammatika mutaxassisisan. Quyidagi ingliz matnda FAQAT "
    "grammatika, imlo va tinish belgilari xatolarini tuzat — ma'no, uslub va "
    "qator ko'chirishlarni o'zgartirma. Faqat tuzatilgan matnni qaytar."
)

_SYSTEM_RAVON = (
    "Sen ingliz tilida native muharrirsan. Senga JSON RO'YXAT ko'rinishida "
    "ingliz matn bo'laklari beriladi. Har birini tabiiy, ravon ingliz tiliga "
    "moslashtir — ASOSIY MA'NONI o'zgartirma. Bo'sh, raqamli yoki maxsus "
    "belgilardan iborat bo'laklarni O'ZGARTIRMASDAN qaytar."
    + _OGOHLANTIRISH +
    "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar — boshqa "
    "hech narsa, izoh yoki ``` yozma."
)
_SYSTEM_RAVON_BITTA = (
    "Sen ingliz tilida native muharrirsan. Quyidagi ingliz matnni tabiiy, "
    "ravon ingliz tiliga moslashtir — ASOSIY MA'NONI va qator ko'chirishlarni "
    "saqla. Faqat qayta yozilgan matnni qaytar."
)

_TIL_NOMI = {"uz": "O'ZBEK", "en": "INGLIZ", "ru": "RUS"}


def _tarjima_system(maqsad_til):
    nom = _TIL_NOMI.get(maqsad_til, "O'ZBEK")
    return (
        f"Sen professional ilmiy tarjimonsan. Senga JSON RO'YXAT ko'rinishida "
        f"matn bo'laklari beriladi. Har birining tilini avtomatik aniqlab, {nom} "
        f"tiliga ILMIY-RASMIY uslubda tarjima qil. O'zbek tiliga tarjima qilsang "
        f"— LOTIN alifbosida yoz. Bo'sh, raqamli yoki maxsus belgilardan iborat "
        f"bo'laklarni O'ZGARTIRMASDAN qaytar."
        + _OGOHLANTIRISH +
        "\n\nQAT'IY QOIDA: Faqat XUDDI SHU UZUNLIKDAGI JSON RO'YXAT qaytar — "
        "boshqa hech narsa, izoh yoki ``` yozma."
    )


def _tarjima_system_bitta(maqsad_til):
    nom = _TIL_NOMI.get(maqsad_til, "O'ZBEK")
    return (
        f"Sen professional ilmiy tarjimonsan. Quyidagi matnning tilini avtomatik "
        f"aniqlab, {nom} tiliga ILMIY-RASMIY uslubda tarjima qil. O'zbek tiliga "
        f"tarjima qilsang — LOTIN alifbosida yoz, qator ko'chirishlarni saqla. "
        f"Faqat tarjimani qaytar."
    )


def docx_grammar(kirish_yol: str, chiqish_yol: str):
    """.docx dagi ingliz matn grammatikasini tuzatadi (format saqlanadi)."""
    client, model = client_va_model("til", TIL_BASE_URL, TIL_KEY, TIL_MODEL)
    return docx_ni_ishla(client, model, kirish_yol, chiqish_yol,
                         _SYSTEM_GRAMMAR, _SYSTEM_GRAMMAR_BITTA)


def docx_ravon(kirish_yol: str, chiqish_yol: str):
    """.docx dagi ingliz matnni ravon, native uslubga moslashtiradi (format saqlanadi)."""
    client, model = client_va_model("til", TIL_BASE_URL, TIL_KEY, TIL_MODEL)
    return docx_ni_ishla(client, model, kirish_yol, chiqish_yol,
                         _SYSTEM_RAVON, _SYSTEM_RAVON_BITTA)


def docx_tarjima(kirish_yol: str, chiqish_yol: str, maqsad_til: str = "uz"):
    """.docx dagi matnni ilmiy-rasmiy uslubda tarjima qiladi (format saqlanadi)."""
    client, model = client_va_model("til", TIL_BASE_URL, TIL_KEY, TIL_MODEL)
    return docx_ni_ishla(client, model, kirish_yol, chiqish_yol,
                         _tarjima_system(maqsad_til), _tarjima_system_bitta(maqsad_til))
