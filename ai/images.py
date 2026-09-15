"""
ai/images.py — mavzuga mos AI rasm yasaydi (Pollinations, bepul, kalitsiz)
Har slaytdagi "image" tavsifini olib, rasm yasab, faylga saqlaydi.
Rasm ustiga shablonning uslub-tavsifi qo'shiladi (barcha rasm bir uslubda — Gamma kabi).
"""

import os
import time
import logging
import tempfile
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

from config import (RASM_YOQ, IMG_BASE, IMG_MODEL, IMG_PROVIDER, IMG_MODEL_G,
                    IMG_KEY, IMG_TOGETHER_KEY, IMG_TOGETHER_MODEL)
from slides.design import TEMPLATES
import admin_store

log = logging.getLogger("ai.images")


def _sozlama():
    """Admin panel orqali o'zgartirilgan bo'lsa o'shani, aks holda .env
    standart qiymatlarini qaytaradi — har chaqiriqda YANGI qiymat olinadi
    (bot qayta ishga tushirilishi shart emas)."""
    ov = admin_store.rasm_sozlama_ol()
    return {
        "provider": ov.get("provider") or IMG_PROVIDER,
        "base": ov.get("base") or IMG_BASE,
        "model": ov.get("model") or IMG_MODEL,
        "key": ov.get("key") or IMG_KEY,
        "model_g": ov.get("model_g") or IMG_MODEL_G,
        "together_key": ov.get("together_key") or IMG_TOGETHER_KEY,
        "together_model": ov.get("together_model") or IMG_TOGETHER_MODEL,
    }


def rasm_yasa(prompt, width, height, path, retries=2):
    """Bitta rasm yasaydi. Provayderga qarab Pollinations, Together yoki Gemini.
    Vaqtinchalik xatolarda (timeout, rate-limit) bir necha marta qayta urinadi —
    aks holda bitta tasodifiy xato butun slaytni placeholderga aylantirib qo'yadi."""
    if not RASM_YOQ:
        return None
    sozlama = _sozlama()
    if sozlama["provider"] == "gemini":
        urin = lambda: _gemini_rasm(prompt, path, sozlama)
    elif sozlama["provider"] == "together":
        urin = lambda: _together_rasm(prompt, width, height, path, sozlama)
    else:
        urin = lambda: _pollinations_rasm(prompt, width, height, path, sozlama)

    for attempt in range(retries + 1):
        natija = urin()
        if natija:
            return natija
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    log.warning("Rasm yasab bo'lmadi (%d urinishdan keyin): %s", retries + 1, prompt[:80])
    return None


def _pollinations_rasm(prompt, width, height, path, sozlama):
    """Bepul, kalitsiz (Pollinations / Flux)."""
    if requests is None:
        return None
    try:
        p = urllib.parse.quote(prompt.strip()[:300])
        url = (f"{sozlama['base']}{p}?width={width}&height={height}"
               f"&nologo=true&model={sozlama['model']}")
        r = requests.get(url, timeout=90)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    except Exception:
        return None
    return None


_gclient = None
_gclient_key = None

def _gemini_rasm(prompt, path, sozlama):
    """Nano banana (Gemini 2.5 Flash Image) — PULLIK, karta/billing kerak."""
    global _gclient, _gclient_key
    import logging
    log = logging.getLogger("nano-banana")
    try:
        if _gclient is None or _gclient_key != sozlama["key"]:
            try:
                from google import genai
            except ImportError:
                log.error("google-genai o'rnatilmagan. Buyruq: pip install google-genai")
                return None
            _gclient = genai.Client(api_key=sozlama["key"])
            _gclient_key = sozlama["key"]
        resp = _gclient.models.generate_content(model=sozlama["model_g"], contents=[prompt])
        for part in resp.candidates[0].content.parts:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                with open(path, "wb") as f:
                    f.write(data)
                return path
        log.error("Nano banana rasm qaytarmadi (matn qaytdi?). Javob: %s",
                  str(resp)[:200])
    except Exception as e:
        # eng ko'p sabab: billing yoqilmagan yoki kalit noto'g'ri
        log.error("Nano banana XATO: %s", e)
    return None


def rasmlarni_tayyorla(deck, tmpdir=None):
    """Deck ichidagi barcha rasmlarni yasab, yo'llarini deckka biriktiradi.
    Sarlavha rasmi + har 'image_text' slayt rasmi."""
    if not RASM_YOQ or requests is None:
        return deck
    cfg = TEMPLATES.get(deck.get("template", "modern"), TEMPLATES["modern"])
    style = cfg.get("img_prompt", "clean professional illustration")
    tmpdir = tmpdir or tempfile.mkdtemp()

    # Sarlavha rasmi
    if deck.get("image"):
        pth = os.path.join(tmpdir, "title.jpg")
        # title_bg (fon) bo'lsa keng, aks holda kvadratga yaqin
        w, h = (1280, 960) if cfg.get("title_bg") else (1024, 1152)
        if rasm_yasa(f"{deck['image']}, {style}, highly detailed, professional, no text, no words, no letters", w, h, pth):
            deck["_img_path"] = pth

    # Har image_text slayt rasmi
    for i, s in enumerate(deck.get("slides", [])):
        if s.get("type") in ("image_text", "image") and s.get("image"):
            pth = os.path.join(tmpdir, f"s{i}.jpg")
            if rasm_yasa(f"{s['image']}, {style}, highly detailed, professional, no text, no words, no letters", 896, 1152, pth):
                s["_img_path"] = pth
    return deck

_tclient = None
_tclient_key = None

def _together_rasm(prompt, width, height, path, sozlama):
    """Together AI — Flux (arzon, sifatli). base64 qaytaradi."""
    global _tclient, _tclient_key
    import logging, base64
    log = logging.getLogger("together-flux")
    try:
        if _tclient is None or _tclient_key != sozlama["together_key"]:
            try:
                from together import Together
            except ImportError:
                log.error("together o'rnatilmagan. Buyruq: pip install together")
                return None
            _tclient = Together(api_key=sozlama["together_key"])
            _tclient_key = sozlama["together_key"]
        # o'lchamni 16 ga bo'linadigan qilamiz (Flux talabi)
        w = max(512, (int(width) // 16) * 16)
        h = max(512, (int(height) // 16) * 16)
        resp = _tclient.images.generate(
            prompt=prompt, model=sozlama["together_model"], width=w, height=h, n=1)
        b64 = resp.data[0].b64_json
        if b64:
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            return path
        # ba'zi modellar url qaytaradi
        url = getattr(resp.data[0], "url", None)
        if url and requests is not None:
            r = requests.get(url, timeout=90)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
                return path
        log.warning("Together javobida rasm topilmadi (b64 ham, url ham yo'q)")
    except Exception as e:
        log.error("Together XATO: %s", e)
    return None
