"""
ai/_runtime.py — har bir AI moduli uchun DINAMIK (admin panel orqali
o'zgartirilishi mumkin) OpenAI klientini beradi. Klient FAQAT sozlama
(base_url/key) haqiqatan o'zgarganda qayta yaratiladi (keshlanadi) — shu
sababli har chaqiriqda admin_store'ni tekshirish tezlikka deyarli ta'sir
qilmaydi, lekin admin narsani o'zgartirsa, KEYINGI chaqiriqda darhol
yangi klient ishlatiladi (bot qayta ishga tushirilishi shart emas).
"""

from openai import OpenAI

import admin_store

_kesh = {}  # modul -> (base_url, key, OpenAI instansi)


def client_va_model(modul, standart_base, standart_key, standart_model):
    """modul: admin_store.AI_MODULLAR dagi kalitlardan biri ('slayt','tuzat','til','konspekt').
    Qaytaradi: (OpenAI klient, model_nomi)."""
    base, key, model = admin_store.ai_sozlama_ol(modul, standart_base, standart_key, standart_model)
    joriy = _kesh.get(modul)
    if joriy is None or joriy[0] != base or joriy[1] != key:
        joriy = (base, key, OpenAI(base_url=base, api_key=key))
        _kesh[modul] = joriy
    return joriy[2], model
