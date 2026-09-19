"""
promo_store.py — TARG'IBOT (promo) linklari uchun DOIMIY ombor. Admin panelda
har targ'ibotchi uchun alohida link yaratiladi (t.me/<bot>?start=promo_<kod>);
shu link orqali botga KELGAN har bir YANGI foydalanuvchi shu targ'ibotchiga
yoziladi va har biri uchun PROMO_HAQ so'm hisoblanadi (pulni admin qo'lda
to'laydi — bu yerda faqat hisob-kitob yuritiladi).

JSON faylda (data/promo.json, .gitignore'da) saqlanadi — admin_store.py /
referal_store.py bilan BIR XIL uslub: qulflash + atomik yozish.

Firibga qarshi: foydalanuvchi FAQAT bir marta va FAQAT botga umuman birinchi
marta kirganda (avval hech qachon /start bosmagan bo'lsa) yoziladi — eski
foydalanuvchi linkni bossa hisoblanmaydi.
"""

import os
import json
import time
import secrets
import threading

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_STORE_PATH = os.path.join(_DATA_DIR, "promo.json")

_lock = threading.Lock()

PROMO_HAQ = 500   # har bir yangi foydalanuvchi uchun targ'ibotchiga hisoblanadigan summa (so'm)
PREFIKS = "promo_"


def _bosh_holat():
    # linklar: kod -> {"nom", "faol", "yaratilgan"}
    # kelganlar: kod -> [{"id", "ism", "username", "vaqt"}, ...]
    return {"linklar": {}, "kelganlar": {}, "biriktirilgan": {}}


def _yukla():
    if not os.path.exists(_STORE_PATH):
        return _bosh_holat()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _bosh_holat()
    for k, v in _bosh_holat().items():
        data.setdefault(k, v)
    return data


def _saqla():
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


_store = _yukla()


def link_yarat(nom):
    """Yangi targ'ibot linki yaratadi. Qaytaradi: kod (start parametri PREFIKS + kod)."""
    with _lock:
        while True:
            kod = secrets.token_hex(4)
            if kod not in _store["linklar"]:
                break
        _store["linklar"][kod] = {"nom": nom.strip()[:60], "faol": True, "yaratilgan": time.time()}
        _store["kelganlar"][kod] = []
        _saqla()
        return kod


def faol_almashtir(kod):
    """Linkni o'chiradi/qayta yoqadi (o'chiq linkdan kelganlar hisoblanmaydi, tarix saqlanadi)."""
    with _lock:
        link = _store["linklar"].get(kod)
        if not link:
            return None
        link["faol"] = not link["faol"]
        _saqla()
        return link["faol"]


def kod_ajrat(start_arg):
    """'/start promo_<kod>' argumentidan kodni ajratadi (bo'lmasa None)."""
    if start_arg and start_arg.startswith(PREFIKS):
        return start_arg[len(PREFIKS):]
    return None


def foydalanuvchi_qayd_et(user_id, kod, ism, username):
    """YANGI foydalanuvchini link egasiga yozadi. True — yozildi; False — link
    yo'q/o'chiq yoki bu foydalanuvchi allaqachon biror linkka yozilgan."""
    with _lock:
        link = _store["linklar"].get(kod)
        if not link or not link["faol"]:
            return False
        if str(user_id) in _store["biriktirilgan"]:
            return False
        _store["biriktirilgan"][str(user_id)] = kod
        _store["kelganlar"][kod].append({
            "id": user_id, "ism": ism or "", "username": username or "", "vaqt": time.time()})
        _saqla()
        return True


def linklar_royxati():
    """[(kod, nom, faol, soni)] — yaratilish tartibida."""
    with _lock:
        return [(k, v["nom"], v["faol"], len(_store["kelganlar"].get(k, [])))
                for k, v in _store["linklar"].items()]


def link_ol(kod):
    """Bitta link haqida to'liq ma'lumot (chuqur nusxa) yoki None."""
    with _lock:
        link = _store["linklar"].get(kod)
        if not link:
            return None
        return {"nom": link["nom"], "faol": link["faol"],
                "kelganlar": json.loads(json.dumps(_store["kelganlar"].get(kod, [])))}
