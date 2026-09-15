"""
ai/content.py — mavzuni yangi SXEMAGA aylantiradi (render.py kutadigan)
Sozlama config.py dan olinadi. OpenAI-mos (Gemini/Groq/lokal).
"""

import os
import json

from config import AI_BASE_URL, AI_API_KEY, AI_MODEL
from ai._runtime import client_va_model

# Mavjud ikonkalar (assets/icons dan)
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "assets", "icons")
try:
    IKONKALAR = sorted(f[:-4] for f in os.listdir(_ICON_DIR) if f.endswith(".png"))
except FileNotFoundError:
    IKONKALAR = []

SYSTEM = """Sen o'quv taqdimotlari tuzuvchi mutaxassissan.
Foydalanuvchi bergan MAVZU bo'yicha slaytlar rejasini JSON'da tuzasan.

QAT'IY QOIDALAR:
- Faqat to'g'ri JSON qaytar. Izoh yoki ``` belgisi QO'YMA.
- Til: foydalanuvchi tilida (o'zbek bo'lsa LOTIN alifbosida, Kirill emas).
- Matnlar QISQA. Punkt = bitta jumla. Slaytga sig'sin.
- AYNAN {N} ta ichki slayt yasa.
- Slayt turlarini ARALASH ishlat. "image_text" turini KO'PROQ ishlat
  (kamida 2-3 marta) — chunki unda rasm bo'ladi. Matn zich slaytlar uchun
  cards/stats ishlat (ularda rasm shart emas).
- RAQAM: faqat aniq bilgan faktni yoz. Bilmasang "stats" ishlatma.
- "theme" (shablon) YOZMA — foydalanuvchi tanlaydi.
- RASM TAVSIFI ("image" maydoni): HAR DOIM INGLIZ TILIDA yoz (rasm modeli
  o'zbekchani tushunmaydi). Aniq, batafsil va konkret bo'lsin: predmet + sahna
  + uslub. Slayt mavzusiga TO'G'RIDAN-TO'G'RI mos bo'lsin, mavhum yoki qisqa emas.
  YOMON: "gen"  ·  YAXSHI: "a glowing blue DNA double helix strand with a
  highlighted gene segment, 3D scientific render, dark background, detailed".
  Har rasm o'z slaytining aniq mavzusini ko'rsatsin.

JSON tuzilmasi:
{
  "title": "qisqa sarlavha",
  "tag": "fan yoki soha (1-2 so'z)",
  "subtitle": "bitta jumla tavsif",
  "image": "INGLIZCHA batafsil rasm tavsifi (butun mavzu)",
  "slides": [
    {"type":"image_text","tag":"...","title":"...","intro":"...",
     "points":["...","...","..."],"image":"INGLIZCHA batafsil rasm tavsifi (shu slayt mavzusi)"},
    {"type":"cards","tag":"...","title":"...","intro":"...",
     "cards":[{"h":"sarlavha","d":"izoh"}]},
    {"type":"icons","tag":"...","title":"...",
     "rows":[{"icon":"IKONKA_NOMI","h":"sarlavha","d":"izoh"}]},
    {"type":"stats","tag":"...","title":"...",
     "stats":[{"num":"42%","label":"izoh"}]},
    {"type":"steps","tag":"...","title":"...","steps":["...","..."]},
    {"type":"callout","tag":"...","title":"...","intro":"...","callout":"asosiy fikr"}
  ],
  "conclusion": {"title":"Xulosa","points":["asosiy fikr 1","asosiy fikr 2","asosiy fikr 3"],"text":"yakuniy kuchli gap"}
}

Slayt turini mazmunga qarab tanla:
- image_text: rasm bilan tushuntirish (2-4 punkt) — bunda rasm bo'ladi
- cards: 2-4 tushuncha/tur (har biri sarlavha+izoh)
- icons: 3-4 ro'yxat, ikonka bilan
- stats: 2-3 raqam/fakt
- steps: bosqichli jarayon
- callout: asosiy fikr/xulosa

"icon" faqat quyidagi ro'yxatdan (aynan shu yozuvda), mos bo'lmasa "box":
{ICONS}"""

SYSTEM = SYSTEM.replace("{ICONS}", ", ".join(IKONKALAR))


def mavzudan_json(mavzu: str, ichki_slaydlar: int = 8) -> dict:
    ichki_slaydlar = max(3, min(13, int(ichki_slaydlar)))
    system = SYSTEM.replace("{N}", str(ichki_slaydlar))
    client, model = client_va_model("slayt", AI_BASE_URL, AI_API_KEY, AI_MODEL)
    resp = client.chat.completions.create(
        model=model, temperature=0.7,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": f"Mavzu: {mavzu}"}])
    data = _parse(resp.choices[0].message.content)
    if isinstance(data.get("slides"), list):
        data["slides"] = data["slides"][:ichki_slaydlar]
    return data


def _parse(matn: str) -> dict:
    matn = matn.strip()
    if matn.startswith("```"):
        matn = matn.strip("`")
        if matn.lower().startswith("json"):
            matn = matn[4:]
    b, e = matn.find("{"), matn.rfind("}")
    if b != -1 and e != -1:
        matn = matn[b:e + 1]
    data = json.loads(matn)
    if "title" not in data:
        data["title"] = "Taqdimot"
    if not isinstance(data.get("slides"), list) or not data["slides"]:
        raise ValueError("AI slaytlar bermadi")
    return data
