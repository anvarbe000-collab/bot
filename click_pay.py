"""
click_pay.py — Click (https://click.uz) to'lov tizimi, Shop API
(Prepare + Complete). Rasmiy hujjat: docs.click.uz.

Buyurtmalar data/click_orders.json da saqlanadi (admin_store.py bilan bir xil
uslub — oddiy JSON, qulflash bilan, .gitignore'da).

Oqim:
  1. Bot yangi_buyurtma() bilan buyurtma yaratadi (chat_id, mode, summa) va
     pay_url() orqali Click to'lov havolasini yasaydi — shu havola talabaga
     tugma sifatida ko'rsatiladi.
  2. Talaba havolani bosib, Click sahifasida kartasini kiritadi.
  3. Click bizning webhook serverimizga IKKITA so'rov yuboradi:
       - PREPARE (action=0): to'lov BOSHLANGANI haqida — biz buyurtmani
         tekshiramiz (mavjudmi, summasi to'g'rimi), "merchant_prepare_id"
         (bizning ICHKI tasdiqlash raqamimiz) qaytaramiz.
       - COMPLETE (action=1): to'lov TUGAGANI haqida — muvaffaqiyatli bo'lsa
         buyurtmani "to'landi" deb belgilaymiz. Botga xizmatni ochish signali
         ALOHIDA (bot/click_webhook.py) beriladi — bu modul FAQAT to'lov
         mantig'i bilan shug'ullanadi, Telegramga bog'liq emas.

Xato kodlari (Click hujjati bo'yicha eng ko'p ishlatiladiganlari):
  0  = OK
  -1 = SIGN CHECK FAILED (imzo mos kelmadi)
  -2 = Incorrect parameter amount (summa mos kelmadi)
  -5 = User (order) does not exist (buyurtma topilmadi)
  -6 = Transaction does not exist (complete'da mos prepare topilmadi)
  -9 = Transaction cancelled (bekor qilingan / Click o'zi rad etgan)
"""

import os
import json
import time
import uuid
import hashlib
import logging
import threading
import urllib.parse

import config

log = logging.getLogger("click_pay")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_ORDERS_PATH = os.path.join(_DATA_DIR, "click_orders.json")

_lock = threading.Lock()


def _yukla():
    if not os.path.exists(_ORDERS_PATH):
        return {}
    try:
        with open(_ORDERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _saqla():
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _ORDERS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_buyurtmalar, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _ORDERS_PATH)


_buyurtmalar = _yukla()


def yangi_buyurtma(chat_id, mode, summa):
    """Yangi Click buyurtmasi yaratadi. Qaytaradi: order_id (transaction_param
    sifatida pay havolasiga qo'yiladi, Click buni bizga 'merchant_trans_id'
    nomi bilan qaytarib beradi)."""
    order_id = uuid.uuid4().hex[:16]
    with _lock:
        _buyurtmalar[order_id] = {
            "chat_id": chat_id,
            "mode": mode,
            "summa": int(summa),
            "holat": "kutilmoqda",   # kutilmoqda -> tayyorlangan -> tolandi | bekor
            "click_trans_id": None,
            "merchant_prepare_id": None,
            "yaratilgan": time.time(),
        }
        _saqla()
    return order_id


def buyurtma_ol(order_id):
    with _lock:
        yoz = _buyurtmalar.get(order_id)
        return dict(yoz) if yoz else None


def buyurtma_bekor_qil(order_id):
    """Talaba to'lovni o'zi bekor qilsa (Bekor qilish tugmasi) — Click hali
    Complete yubormasa ham, bizning tomonimizdan yopib qo'yamiz."""
    with _lock:
        if order_id in _buyurtmalar and _buyurtmalar[order_id]["holat"] == "kutilmoqda":
            _buyurtmalar[order_id]["holat"] = "bekor"
            _saqla()


def _yozib_qoy(order_id, **maydonlar):
    with _lock:
        if order_id not in _buyurtmalar:
            return
        _buyurtmalar[order_id].update(maydonlar)
        _saqla()


def pay_url(order_id, summa):
    """Click to'lov havolasini (Shop API "pay" havolasi) yasaydi."""
    parametrlar = {
        "service_id": config.CLICK_SERVICE_ID,
        "merchant_id": config.CLICK_MERCHANT_ID,
        "amount": summa,
        "transaction_param": order_id,
    }
    if config.CLICK_RETURN_URL:
        parametrlar["return_url"] = config.CLICK_RETURN_URL
    return f"{config.CLICK_PAY_BASE}?{urllib.parse.urlencode(parametrlar)}"


def _sign_tekshir(d, complete=False):
    """Click yuborgan sign_string'ni tekshiradi (d — so'rov parametrlari, dict).
    Formula (docs.click.uz):
      prepare:  md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id +
                    amount + action + sign_time)
      complete: yuqoridagiga merchant_trans_id'dan KEYIN merchant_prepare_id qo'shiladi."""
    qismlar = [
        str(d.get("click_trans_id", "")),
        str(d.get("service_id", "")),
        config.CLICK_SECRET_KEY,
        str(d.get("merchant_trans_id", "")),
    ]
    if complete:
        qismlar.append(str(d.get("merchant_prepare_id", "")))
    qismlar += [str(d.get("amount", "")), str(d.get("action", "")), str(d.get("sign_time", ""))]
    kutilgan = hashlib.md5("".join(qismlar).encode("utf-8")).hexdigest()
    return kutilgan == str(d.get("sign_string", ""))


def _amount_mos(d, buyurtma):
    try:
        return round(float(d.get("amount", 0)), 2) == round(float(buyurtma["summa"]), 2)
    except (TypeError, ValueError):
        return False


def prepare_ishla(d):
    """PREPARE (action=0) so'rovini ishlaydi.
    Qaytaradi: (Click'ga qaytariladigan JSON javob, order_id yoki None)."""
    order_id = str(d.get("merchant_trans_id", ""))
    asos = {"click_trans_id": d.get("click_trans_id"), "merchant_trans_id": order_id}

    if not _sign_tekshir(d, complete=False):
        log.warning("Click PREPARE: imzo mos kelmadi (order_id=%s)", order_id)
        return {**asos, "error": -1, "error_note": "SIGN CHECK FAILED"}, None

    buyurtma = buyurtma_ol(order_id)
    if not buyurtma:
        return {**asos, "error": -5, "error_note": "Buyurtma topilmadi"}, None
    if buyurtma["holat"] == "bekor":
        return {**asos, "error": -9, "error_note": "Buyurtma bekor qilingan"}, None
    if not _amount_mos(d, buyurtma):
        return {**asos, "error": -2, "error_note": "Summa mos kelmadi"}, None

    merchant_prepare_id = int(time.time() * 1000) % 2_000_000_000
    _yozib_qoy(order_id, holat="tayyorlangan", click_trans_id=d.get("click_trans_id"),
              merchant_prepare_id=merchant_prepare_id)
    return {**asos, "merchant_prepare_id": merchant_prepare_id,
           "error": 0, "error_note": "Success"}, order_id


def complete_ishla(d):
    """COMPLETE (action=1) so'rovini ishlaydi.
    Qaytaradi: (Click'ga qaytariladigan JSON javob, order_id, muvaffaqiyatlimi)."""
    order_id = str(d.get("merchant_trans_id", ""))
    asos = {"click_trans_id": d.get("click_trans_id"), "merchant_trans_id": order_id}

    if not _sign_tekshir(d, complete=True):
        log.warning("Click COMPLETE: imzo mos kelmadi (order_id=%s)", order_id)
        return {**asos, "error": -1, "error_note": "SIGN CHECK FAILED"}, None, False

    buyurtma = buyurtma_ol(order_id)
    if not buyurtma:
        return {**asos, "error": -5, "error_note": "Buyurtma topilmadi"}, None, False
    if buyurtma["holat"] == "tolandi":
        return ({**asos, "merchant_confirm_id": buyurtma.get("merchant_prepare_id"),
                "error": -4, "error_note": "Allaqachon to'langan"}, order_id, False)
    if str(d.get("merchant_prepare_id", "")) != str(buyurtma.get("merchant_prepare_id", "")):
        return {**asos, "error": -6, "error_note": "Tranzaksiya topilmadi"}, None, False

    # Click O'ZI xato/bekor qilgan bo'lsa (masalan mijoz kartasi rad etilgan)
    try:
        click_xato = int(d.get("error", 0) or 0)
    except (TypeError, ValueError):
        click_xato = 0
    if click_xato < 0:
        _yozib_qoy(order_id, holat="bekor")
        return ({**asos, "merchant_confirm_id": buyurtma.get("merchant_prepare_id"),
                "error": -9, "error_note": "Click tomonidan bekor qilingan"}, order_id, False)

    _yozib_qoy(order_id, holat="tolandi")
    return ({**asos, "merchant_confirm_id": buyurtma.get("merchant_prepare_id"),
            "error": 0, "error_note": "Success"}, order_id, True)
