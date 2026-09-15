"""
ai/til.py — "Til bo'limi": Ingliz tili yordamchisi (IELTS baholash, grammatika,
ravonlashtirish) va ilmiy tarjima. TIL_KEY bilan ALOHIDA OpenAI klient ishlatadi
(config.TIL_*) — boshqa bo'limlar kalitiga tegmaydi.
"""

from config import TIL_BASE_URL, TIL_KEY, TIL_MODEL
from ai._runtime import client_va_model


def _chaqir(system: str, matn: str, temperature: float = 0.3) -> str:
    client, model = client_va_model("til", TIL_BASE_URL, TIL_KEY, TIL_MODEL)
    resp = client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": matn}])
    return (resp.choices[0].message.content or "").strip()


_SYSTEM_IELTS = """Sen IELTS Writing baholovchi ekspertisan (rasmiy IELTS mezonlari bo'yicha).
Foydalanuvchi ingliz tilida yozgan esse/matnni baho.

Javobni O'ZBEK TILIDA (lotin alifbosida) yoz, quyidagi tuzilishda:

📊 TAXMINIY BALL: X.X / 9.0

Mezonlar bo'yicha alohida ball va qisqa izoh:
— Task Response: X.X — [izoh]
— Coherence & Cohesion: X.X — [izoh]
— Lexical Resource: X.X — [izoh]
— Grammatical Range & Accuracy: X.X — [izoh]

❌ ASOSIY XATOLAR (ingliz misollar bilan, har biri uchun to'g'ri variantini ham ko'rsat):
— "..." → to'g'risi: "..."

💡 YAXSHILASH UCHUN MASLAHATLAR:
— aniq, amaliy maslahatlar (3-5 ta band)

QOIDALAR:
- Haqiqiy IELTS mezonlariga tayan, real va halol baho ber (haddan ortiq maqtama).
- Xatolar albatta original ingliz matndan olingan aniq misollar bo'lsin.
- Juda qisqa yoki mavzudan tashqari matn bo'lsa, buni ayt va past ball ber."""

_SYSTEM_GRAMMAR = """Sen ingliz tili grammatika mutaxassisisan (Grammarly kabi).
Quyidagi ingliz matnda FAQAT grammatika, imlo va tinish belgilari xatolarini
tuzat — ma'no va uslubni o'zgartirma.

QAT'IY QOIDA: Faqat tuzatilgan INGLIZ matnni qaytar. Izoh, tarjima, tushuntirish
YOZMA."""

_SYSTEM_RAVON = """Sen ingliz tilida so'zlashuvchi (native speaker) professional
muharrirsan. Quyidagi ingliz matnni tabiiy, ravon va native ingliz tiliga xos
uslubda qayta yoz — ASOSIY MA'NONI o'zgartirma.

QAT'IY QOIDA: Faqat qayta yozilgan INGLIZ matnni qaytar. Izoh, tarjima yozma."""

_TIL_NOMI = {"uz": "O'ZBEK", "en": "INGLIZ", "ru": "RUS"}


def ingliz_ielts(matn: str) -> str:
    """IELTS Writing mezonlari bo'yicha baholaydi (natija HAR DOIM o'zbek tilida matn)."""
    return _chaqir(_SYSTEM_IELTS, matn, temperature=0.3)


def ingliz_grammar(matn: str) -> str:
    """Ingliz matn grammatikasini tuzatadi (Grammarly kabi)."""
    return _chaqir(_SYSTEM_GRAMMAR, matn, temperature=0.2)


def ingliz_ravon(matn: str) -> str:
    """Ingliz matnni ravon, tabiiy (native) qilib qayta yozadi."""
    return _chaqir(_SYSTEM_RAVON, matn, temperature=0.4)


def tarjima(matn: str, maqsad_til: str = "uz") -> str:
    """Matn tilini AVTOMATIK aniqlab, maqsad_til (uz/en/ru) ga ILMIY-RASMIY
    uslubda tarjima qiladi. O'zbekcha bo'lsa LOTIN alifbosida."""
    nom = _TIL_NOMI.get(maqsad_til, "O'ZBEK")
    system = (
        f"Sen professional ilmiy tarjimonsan. Quyidagi matnning tilini AVTOMATIK "
        f"aniqla va uni {nom} tiliga ILMIY-RASMIY uslubda tarjima qil — atamalar "
        f"aniq, uslub rasmiy va izchil bo'lsin.\n\n"
        f"QOIDALAR:\n"
        f"- Agar maqsad til o'zbek bo'lsa — albatta LOTIN alifbosida yoz (kirill EMAS).\n"
        f"- Matn mazmuni va ma'nosini AYNAN saqla, o'zingdan narsa qo'shma yoki tushirib qoldirma.\n"
        f"- Faqat tarjima qilingan matnni qaytar — izoh, original matn, tushuntirish YOZMA."
    )
    return _chaqir(system, matn, temperature=0.2)
