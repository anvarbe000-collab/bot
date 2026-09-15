"""
ai/docx_umumiy.py — .docx paragraflarini GURUHLAB, JSON orqali AI bilan qayta
ishlaydigan UMUMIY DVIGATEL (format saqlanadi). ai/docx_tuzat.py ("Matn
tuzatish": imlo/ravon) va ai/docx_til.py ("Til bo'limi": grammatika/ravon/
tarjima) shu dvigatelni ishlatadi — kod takrorlanmaydi.

Har modul o'zining system-promptini beradi, dvigatel esa: paragraflarni yig'ish,
guruhlash, JSON orqali so'rov yuborish, javobni tekshirish, muvaffaqiyatsiz
bo'lsa har bo'lakni alohida ishlashga o'tish va formatni saqlab yozishni bajaradi.
"""

import json
import logging

from docx import Document

log = logging.getLogger("docx-umumiy")

GURUH_HAJMI = 15
SOZ_LIMIT = 15000


def docx_matnini_ol(yol):
    """.docx fayldagi BARCHA matnni (paragraf + jadval kataklari) bitta
    matn qilib qaytaradi — masalan, IELTS baholash uchun butun esseni o'qishda."""
    doc = Document(yol)
    qismlar = [p.text for p in doc.paragraphs if p.text.strip()]
    for jadval in doc.tables:
        for qator in jadval.rows:
            for katak in qator.cells:
                qismlar += [p.text for p in katak.paragraphs if p.text.strip()]
    return "\n".join(qismlar)


def _json_ajrat(matn: str):
    matn = matn.strip()
    if matn.startswith("```"):
        matn = matn.strip("`")
        if matn.lower().startswith("json"):
            matn = matn[4:]
    b, e = matn.find("["), matn.rfind("]")
    if b != -1 and e != -1:
        matn = matn[b:e + 1]
    return json.loads(matn)


def _bitta_ai_orqali_ishla(client, model, matn, system):
    """Bitta bo'lakni ALOHIDA ishlaydi (oddiy matn, JSON emas) — guruh usuli
    muvaffaqiyatsiz bo'lganda zaxira sifatida ishlatiladi."""
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0.2,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": matn}])
        natija = (resp.choices[0].message.content or "").strip()
        return natija or matn
    except Exception as e:
        log.error("Bitta bo'lak ishlashda xato: %s", e)
        return matn


def _guruhni_ai_orqali_ishla(client, model, boklar, system, bitta_system):
    """Bitta guruhni (<=GURUH_HAJMI bo'lak) AI orqali BIR SO'ROVDA ishlaydi (tez).
    JSON uzunligi mos kelmasa yoki xato bo'lsa — ZAXIRA sifatida har bo'lakni
    ALOHIDA-ALOHIDA ishlashga o'tadi (sekinroq, lekin har doim ishlaydi)."""
    if not boklar:
        return boklar
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0.2,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(boklar, ensure_ascii=False)}])
        natija = _json_ajrat(resp.choices[0].message.content or "")
        if isinstance(natija, list) and len(natija) == len(boklar):
            return [str(x) for x in natija]
        log.warning("AI javobi guruh uzunligiga mos kelmadi (%d != %d), har bo'lak alohida ishlanadi",
                   len(natija) if isinstance(natija, list) else -1, len(boklar))
    except Exception as e:
        log.error("Guruh ishlashda xato: %s — har bo'lak alohida ishlanadi", e)
    return [_bitta_ai_orqali_ishla(client, model, b, bitta_system) for b in boklar]


def _paragraflarni_yig(doc):
    """Hujjatdagi BARCHA paragraflarni (jadval kataklaridagilar ham) tartib bilan yig'adi."""
    paragraflar = list(doc.paragraphs)
    for jadval in doc.tables:
        for qator in jadval.rows:
            for katak in qator.cells:
                paragraflar.extend(katak.paragraphs)
    return paragraflar


def _paragraf_yoz(p, yangi_matn):
    """Paragraf matnini FORMATNI buzmasdan almashtiradi: birinchi run'ga yozadi,
    qolgan run'larni bo'shatadi (shrift/rang/qalinlik — hammasi saqlanadi)."""
    if not p.runs:
        p.add_run(yangi_matn)
        return
    p.runs[0].text = yangi_matn
    for run in p.runs[1:]:
        run.text = ""


def docx_ni_ishla(client, model, kirish_yol, chiqish_yol,
                  system, bitta_system, system_qayta=None, bitta_system_qayta=None):
    """.docx faylni ochib, matnini AI bilan qayta ishlaydi (format saqlanadi),
    yangi faylga saqlaydi.

    system/bitta_system — asosiy ishlov (guruh/bitta versiyalari).
    system_qayta/bitta_system_qayta — ixtiyoriy IKKINCHI bosqich (masalan,
    qolgan xatolarni qayta tekshirish); berilmasa, faqat bitta bosqich bajariladi.

    Qaytaradi: (chiqish_yol, ozgarishlar, jami_tekshirilgan)
      - ozgarishlar: [(eski_matn, yangi_matn), ...] — FAQAT o'zgargan paragraflar
      - jami_tekshirilgan: nechta (bo'sh bo'lmagan) paragraf tekshirilgani

    Hujjat juda katta bo'lsa ValueError ko'taradi.
    """
    doc = Document(kirish_yol)
    paragraflar = _paragraflarni_yig(doc)

    jami_soz = sum(len(p.text.split()) for p in paragraflar)
    if jami_soz > SOZ_LIMIT:
        raise ValueError(f"hujjat juda katta ({jami_soz} so'z, limit {SOZ_LIMIT} so'z)")

    nishonlar = [(i, p.text) for i, p in enumerate(paragraflar) if p.text.strip()]
    ozgarishlar = []

    for boshi in range(0, len(nishonlar), GURUH_HAJMI):
        guruh = nishonlar[boshi:boshi + GURUH_HAJMI]
        matnlar = [t for _, t in guruh]

        natija = _guruhni_ai_orqali_ishla(client, model, matnlar, system, bitta_system)
        if system_qayta:
            natija = _guruhni_ai_orqali_ishla(client, model, natija, system_qayta, bitta_system_qayta)

        for (idx, eski), yangi in zip(guruh, natija):
            if yangi.strip() != eski.strip():
                ozgarishlar.append((eski, yangi))
            _paragraf_yoz(paragraflar[idx], yangi)

    doc.save(chiqish_yol)
    return chiqish_yol, ozgarishlar, len(nishonlar)
