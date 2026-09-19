"""
admin_store.py — bot uchun DOIMIY (server qayta ishga tushsa ham yo'qolmaydigan)
statistika va sozlamalar ombori. JSON faylda saqlanadi (data/store.json,
.gitignore'da — git'ga tushmaydi, chunki API kalitlari ham shu yerda bo'lishi
mumkin).

Bu yerda ikki narsa bor:
  1) STATISTIKA — xizmat ishlatilishi, to'lovlar, tashrif buyurganlar
     (bot/handlers.py tabiiy nuqtalarda yozadi: start(), xizmat muvaffaqiyatli
     yakunlanganda, admin to'lovni tasdiqlaganda).
  2) SOZLAMALAR — narxlar, premium yoqiq/o'chiq, karta, har bo'lim uchun AI
     (Gemini) sozlamalari — bot/admin.py shu yerdan o'qiydi/yozadi.

MUHIM: bu yerdagi qiymatlar .env/config.py dagi standart qiymatlarni
ALMASHTIRMAYDI — faqat USTIGA YOZADI (bo'sh bo'lsa standart ishlatiladi).
Shu sababli admin panel orqali biror narsani o'zgartirish uchun BOTNI QAYTA
ISHGA TUSHIRISH SHART EMAS — keyingi chaqiriqda darhol amal qiladi
(ai/_runtime.py buni ta'minlaydi).
"""

import os
import json
import threading

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_STORE_PATH = os.path.join(_DATA_DIR, "store.json")

_lock = threading.Lock()

# Statistikada kuzatiladigan barcha xizmatlar (ko'rsatiladigan nom bilan)
XIZMATLAR = {
    "slayt": "🎨 Slayt yaratish",
    "tuzat": "🪄 Matn tuzatish",
    "davom": "🧩 Davom ettirish",
    "konspekt": "📋 Konspekt qilish",
    "ingliz": "🇬🇧 Ingliz yordamchisi",
    "tarjima": "🌐 Ilmiy tarjima",
    "test_link": "📚 Filedan test yaratish",
}

# Pullik (premium) bo'lishi MUMKIN bo'lgan xizmatlar — narx/yoqish-o'chirish shular
# uchun. "test_link" (Filedan test yaratish) kirmaydi — u shunchaki tashqi botga
# havola, biz hech narsa ISHLAMAYMIZ, shu sabab pullik qilish mantiqsiz.
PULLIK_XIZMATLAR = ("slayt", "tuzat", "davom", "konspekt", "ingliz", "tarjima")

# Har bir pullik xizmatning DASTLABKI (admin hali o'zgartirmagan) premium holati.
# Slayt va Ingliz — allaqachon ishlab turgan, TO'LOV TALAB QILADIGAN xizmatlar,
# shu sababli standart holati YOQILGAN. Qolganlari ILGARI BEPUL bo'lgan — shu
# sababli standart holati O'CHIRILGAN (admin ATAYLAB yoqmaguncha bepul qoladi,
# joylashtirish paytida kutilmaganda pullik bo'lib qolmasin deb).
_PREMIUM_STANDART = {"slayt": True, "ingliz": True}

# Har bo'lim uchun ALOHIDA Gemini/AI sozlamasi bo'lgan modullar (ko'rsatiladigan nom bilan)
AI_MODULLAR = {
    "slayt": "🎨 Slayt yaratish (mavzu → reja)",
    "tuzat": "🪄 Matn tuzatish",
    "til": "🇬🇧🌐 Til bo'limi (Ingliz yordamchisi + Ilmiy tarjima)",
    "konspekt": "📋 Konspekt qilish",
}

_DEFAULT = {
    "xizmatlar": {},     # kalit -> {"ishlatilgan": int, "tolov_soni": int, "tolov_summasi": int}
    "tashrif_id_lar": [],
    "narxlar": {},        # xizmat -> narx (so'm)
    "premium": {},        # xizmat -> True/False
    "ai": {},              # modul -> {"base_url":.., "key":.., "model":..}
    "rasm": {},             # {"provider":.., "base":.., "model":.., "key":.., "model_g":.., "together_key":.., "together_model":..}
    "bepul_slayt_id_lar": [],  # bepul (3 varoqlik, birinchi marta) slaytdan foydalangan foydalanuvchi ID'lari
}


def _bosh_holat():
    return json.loads(json.dumps(_DEFAULT))


def _yukla():
    if not os.path.exists(_STORE_PATH):
        return _bosh_holat()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _bosh_holat()
    for k, v in _DEFAULT.items():
        if k not in data:
            data[k] = json.loads(json.dumps(v))
    return data


def _saqla():
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


_store = _yukla()


# ---------- statistika: yozish ----------

def _xizmat_yozuvi(xizmat):
    return _store["xizmatlar"].setdefault(
        xizmat, {"ishlatilgan": 0, "tolov_soni": 0, "tolov_summasi": 0})


def xizmat_ishlatildi(xizmat):
    """Xizmat MUVAFFAQIYATLI yakunlanganda (natija foydalanuvchiga yuborilganda)
    chaqiriladi — hisoblagichni +1 qiladi."""
    with _lock:
        _xizmat_yozuvi(xizmat)["ishlatilgan"] += 1
        _saqla()


def tolov_qayd_et(xizmat, summa):
    """Admin to'lovni ✅ TASDIQLAGANDA chaqiriladi — to'lov soni va summasini +."""
    with _lock:
        yoz = _xizmat_yozuvi(xizmat)
        yoz["tolov_soni"] += 1
        yoz["tolov_summasi"] += int(summa)
        _saqla()


def tashrif_qayd_et(foydalanuvchi_id):
    """/start bosilganda chaqiriladi — YANGI foydalanuvchi bo'lsa ro'yxatga
    qo'shadi. Qaytaradi: True (aynan hozir yangi qo'shildi) yoki False (avvaldan bor)."""
    with _lock:
        idlar = _store["tashrif_id_lar"]
        if foydalanuvchi_id not in idlar:
            idlar.append(foydalanuvchi_id)
            _saqla()
            return True
        return False


# ---------- bepul sinov (birinchi marta, 3 varoqlik slayt) ----------

def bepul_slayt_ishlatganmi(foydalanuvchi_id):
    """Bu foydalanuvchi bepul (3 varoqlik, faqat BIRINCHI marta) slaytdan
    ALLAQACHON foydalanganmi — True bo'lsa, endi 3 varoq ham pullik."""
    with _lock:
        return foydalanuvchi_id in _store["bepul_slayt_id_lar"]


def bepul_slayt_belgila(foydalanuvchi_id):
    """Bepul slayt MUVAFFAQIYATLI yuborilgach chaqiriladi — shu foydalanuvchi
    uchun bepul imkoniyat ENDI ishlatilgan deb belgilanadi (qayta bermaydi)."""
    with _lock:
        idlar = _store["bepul_slayt_id_lar"]
        if foydalanuvchi_id not in idlar:
            idlar.append(foydalanuvchi_id)
            _saqla()


# ---------- statistika: o'qish ----------

def hisobot_ol():
    """Admin panel uchun to'liq statistikani (chuqur nusxa) qaytaradi."""
    with _lock:
        return json.loads(json.dumps(_store))


# ---------- narx / premium ----------

def narx_ol(xizmat, standart):
    with _lock:
        qiymat = _store["narxlar"].get(xizmat)
        return int(qiymat) if qiymat is not None else int(standart)


def narx_belgila(xizmat, narx):
    with _lock:
        _store["narxlar"][xizmat] = int(narx)
        _saqla()


def premium_yoqilganmi(xizmat):
    """Har xizmatning O'ZINING standart holati bor (_PREMIUM_STANDART) — admin
    hali o'zgartirmagan bo'lsa O'SHA qiymat ishlatiladi (slayt/ingliz uchun
    YOQILGAN, qolganlari uchun O'CHIRILGAN — ilgari bepul bo'lganlar joylashtirish
    paytida kutilmaganda pullik bo'lib qolmasin deb)."""
    with _lock:
        qiymat = _store["premium"].get(xizmat)
        return bool(qiymat) if qiymat is not None else bool(_PREMIUM_STANDART.get(xizmat, False))


def eng_arzon_pullik_xizmat(standart_narx):
    """Hozir PREMIUM yoqilgan xizmatlar orasidan ENG ARZONINI (mode, narx)
    qaytaradi — hech biri yoqilmagan bo'lsa (None, None). Referal balans
    "xizmatlardan bepul foydalanish uchun yetarlimi" ko'rsatkichi uchun
    ishlatiladi (bot/handlers.py, bot/click_webhook.py). ICHKARIDA narx_ol/
    premium_yoqilganmi O'ZI qulflaydi — bu yerda qo'shimcha lock OLINMAYDI."""
    variantlar = [(x, narx_ol(x, standart_narx)) for x in PULLIK_XIZMATLAR if premium_yoqilganmi(x)]
    if not variantlar:
        return None, None
    return min(variantlar, key=lambda t: t[1])


def premium_almashtir(xizmat):
    """Joriy holatni teskarisiga o'zgartiradi, YANGI holatni qaytaradi."""
    with _lock:
        qiymat = _store["premium"].get(xizmat)
        joriy = bool(qiymat) if qiymat is not None else bool(_PREMIUM_STANDART.get(xizmat, False))
        yangi = not joriy
        _store["premium"][xizmat] = yangi
        _saqla()
        return yangi


# ---------- AI (Gemini) sozlamalari ----------

def ai_sozlama_ol(modul, standart_base, standart_key, standart_model):
    with _lock:
        ov = _store["ai"].get(modul, {})
        return (ov.get("base_url") or standart_base,
               ov.get("key") or standart_key,
               ov.get("model") or standart_model)


def ai_sozlama_belgila(modul, maydon, qiymat):
    """maydon: 'base_url' | 'key' | 'model'. qiymat bo'sh/None bo'lsa —
    standart (.env) qiymatga qaytaradi (o'chiradi)."""
    with _lock:
        ov = _store["ai"].setdefault(modul, {})
        if qiymat:
            ov[maydon] = qiymat
        else:
            ov.pop(maydon, None)
        _saqla()


# ---------- rasm (AI image) sozlamalari ----------

def rasm_sozlama_ol():
    with _lock:
        return dict(_store["rasm"])


def rasm_sozlama_belgila(maydon, qiymat):
    """maydon: 'provider' | 'base' | 'model' | 'key' | 'model_g' | 'together_key' | 'together_model'."""
    with _lock:
        if qiymat:
            _store["rasm"][maydon] = qiymat
        else:
            _store["rasm"].pop(maydon, None)
        _saqla()
