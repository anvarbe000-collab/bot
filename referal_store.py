"""
referal_store.py — "Do'st chaqir" (referal) tizimi va foydalanuvchi BALANSI
uchun DOIMIY ombor. JSON faylda saqlanadi (data/referal.json, .gitignore'da —
admin_store.py/click_pay.py bilan BIR XIL uslub: qulflash + atomik yozish).

Balans — bu bot ICHIDA pullik xizmatlarni to'lash uchun ishlatiladigan
"sarflanadigan" qiymat (naqd PULGA aylantirib bo'lmaydi, hech qayerga
YECHILMAYDI — faqat bot/handlers.py:_tolov_sora orqali xizmat narxini
qoplash uchun).

Referal mantig'i (firibga qarshi):
  1) referrer_id — uni KIM chaqirgani. Faqat BIR MARTA yoziladi (keyin hech
     qachon o'zgarmaydi) va o'zini-o'zi chaqirish (referrer_id == user_id)
     bloklanadi.
  2) Bonus DARHOL berilmaydi — faqat chaqirilgan odam birinchi marta
     MUVAFFAQIYATLI Click to'lovini yakunlaganda (bot/click_webhook.py orqali
     chaqiriladi). Har chaqirilgan odam uchun bonus FAQAT BIR MARTA beriladi
     (qayta to'lovlarda qayta berilmaydi) — "bonus_berilgan" bayrog'i bilan.
"""

import os
import json
import logging
import threading

log = logging.getLogger("referal_store")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_STORE_PATH = os.path.join(_DATA_DIR, "referal.json")

_lock = threading.Lock()

# Har do'stning BIRINCHI muvaffaqiyatli to'lovi uchun chaqirgan odamga
# qo'shiladigan balans (so'm).
REFERAL_BONUS = 500

_DEFAULT_YOZUV = {
    "referrer_id": None,        # uni kim chaqirgan (bir marta, o'zgarmaydi)
    "bonus_berilgan": False,     # bu odam uchun REFERRERGA bonus allaqachon berilganmi
    "birinchi_tolov_qilgan": False,   # bu odam HAR QANDAY xizmat uchun kamida bir marta Click orqali haqiqiy to'lov qilganmi
    "balans": 0,                 # shu odamning SARFLANADIGAN balansi (so'm)
    "referral_daromad": 0,       # shu odam REFERRER sifatida jami ishlab topgani (lifetime, balans sarflansa ham kamaymaydi)
    "chaqirganlar_soni": 0,      # shu odam REFERRER sifatida chaqirgan (ro'yxatdan o'tkazgan) odamlar soni
}


def _bosh_holat():
    return {}


def _yukla():
    if not os.path.exists(_STORE_PATH):
        return _bosh_holat()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _bosh_holat()


def _saqla():
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


_store = _yukla()


def _yozuv(user_id):
    """Foydalanuvchi yozuvini qaytaradi — yo'q bo'lsa STANDART holat bilan
    yaratadi (LOCK ICHIDA chaqirilishi kerak)."""
    kalit = str(user_id)
    return _store.setdefault(kalit, dict(_DEFAULT_YOZUV))


# ---------- referrer (kim chaqirgani) ----------

def referrer_belgila(user_id, referrer_id):
    """Foydalanuvchi (user_id) referal havola bilan kirganda chaqiriladi.
    Faqat quyidagi shartlar TO'LIQ bajarilsa muvaffaqiyatli bo'ladi:
      - referrer_id musbat butun son (soxta/bo'sh qiymat emas)
      - o'zini-o'zi chaqirish EMAS (referrer_id != user_id)
      - bu foydalanuvchi uchun referrer HALI yozilmagan (faqat BIRINCHI marta)
    Qaytaradi: True (belgilandi) yoki False (shartlardan biri buzilgan)."""
    try:
        referrer_id = int(referrer_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        log.info("Referal: yaroqsiz referrer_id (raqam emas) — user_id=%s", user_id)
        return False
    if referrer_id <= 0:
        log.info("Referal: yaroqsiz referrer_id=%s (musbat son emas) — user_id=%s", referrer_id, user_id)
        return False
    if referrer_id == user_id:
        log.info("Referal: o'zini-o'zi chaqirish bloklandi (user_id=%s)", user_id)
        return False
    with _lock:
        yozuv = _yozuv(user_id)
        if yozuv["referrer_id"] is not None:
            log.info("Referal: user_id=%s uchun referrer ALLAQACHON bor (%s) — o'zgartirilmadi",
                     user_id, yozuv["referrer_id"])
            return False   # allaqachon chaqirilgan — o'zgartirilmaydi
        yozuv["referrer_id"] = referrer_id
        _yozuv(referrer_id)["chaqirganlar_soni"] += 1
        _saqla()
        log.info("Referal: user_id=%s endi referrer_id=%s orqali belgilandi", user_id, referrer_id)
        return True


def referrer_ol(user_id):
    with _lock:
        return _store.get(str(user_id), {}).get("referrer_id")


# ---------- bonus (faqat BIRINCHI muvaffaqiyatli to'lovda) ----------

def birinchi_tolov_qilganmi(user_id):
    with _lock:
        return bool(_store.get(str(user_id), {}).get("birinchi_tolov_qilgan"))


def birinchi_tolov_va_bonus_qayta_ishla(user_id):
    """Click orqali MUVAFFAQIYATLI to'lov tasdiqlangach (bot/click_webhook.py)
    chaqiriladi. Bu foydalanuvchining ROSTDAN HAM birinchi to'lovi bo'lsa VA
    uni chaqirgan odam bo'lsa VA o'sha chaqirgan odamga hali bonus berilmagan
    bo'lsa — bonusni beradi. Qaytaradi: (referrer_id yoki None, bonus_berildimi).
    Idempotent — bir xil user_id uchun ikkinchi marta chaqirilsa hech narsa
    qilmaydi (ikki marta bonus berilmasligi uchun MUHIM himoya)."""
    with _lock:
        yozuv = _yozuv(user_id)
        if yozuv["birinchi_tolov_qilgan"]:
            log.info("Referal bonus: user_id=%s uchun ALLAQACHON birinchi to'lov qayd etilgan — o'tkazib yuborildi", user_id)
            return None, False   # bu ALLAQACHON birinchi to'lov emas — hech narsa qilinmaydi
        yozuv["birinchi_tolov_qilgan"] = True

        referrer_id = yozuv["referrer_id"]
        bonus_berildi = False
        if referrer_id is not None and not yozuv["bonus_berilgan"]:
            yozuv["bonus_berilgan"] = True
            referrer_yozuv = _yozuv(referrer_id)
            referrer_yozuv["balans"] += REFERAL_BONUS
            referrer_yozuv["referral_daromad"] += REFERAL_BONUS
            bonus_berildi = True
        _saqla()
        if bonus_berildi:
            log.info("Referal bonus: user_id=%s birinchi to'lov qildi -> referrer_id=%s ga +%s so'm",
                     user_id, referrer_id, REFERAL_BONUS)
        else:
            log.info("Referal bonus: user_id=%s birinchi to'lov qildi, lekin referrer yo'q/bonus allaqachon berilgan",
                     user_id)
        return (referrer_id if bonus_berildi else None), bonus_berildi


# ---------- balans (sarflanadigan, pullik xizmatlarda ishlatiladi) ----------

def balans_ol(user_id):
    with _lock:
        return int(_store.get(str(user_id), {}).get("balans", 0))


def balans_yetarlimi(user_id, summa):
    return balans_ol(user_id) >= int(summa)


def balans_ayir(user_id, summa):
    """Balansdan AYNAN shuncha ayiradi — FAQAT yetarli bo'lsa (aks holda
    hech narsa qilmay False qaytaradi, manfiy balansga yo'l qo'ymaydi)."""
    with _lock:
        yozuv = _yozuv(user_id)
        if yozuv["balans"] < int(summa):
            return False
        yozuv["balans"] -= int(summa)
        _saqla()
        return True


# ---------- statistika (👥 Do'st chaqir ekrani uchun) ----------

def statistika_ol(user_id):
    with _lock:
        yozuv = _store.get(str(user_id), _DEFAULT_YOZUV)
        return {
            "chaqirganlar_soni": yozuv.get("chaqirganlar_soni", 0),
            "referral_daromad": yozuv.get("referral_daromad", 0),
            "balans": yozuv.get("balans", 0),
        }
