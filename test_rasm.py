"""
test_rasm.py — RASM generatsiyani ALOHIDA sinash (botsiz).
Ishlatish:  python test_rasm.py
Muvaffaqiyatli bo'lsa: test_natija.jpg yasaladi.
Xato bo'lsa: aniq sabab (billing / o'rnatish / kalit) chiqadi.
"""
import os
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

os.environ.setdefault("BOT_TOKEN", "test")
import config
from ai.images import rasm_yasa

print("=" * 50)
print("Provayder     :", config.IMG_PROVIDER)
print("Rasm yoqilgan :", config.RASM_YOQ)
if config.IMG_PROVIDER == "gemini":
    print("Nano model    :", config.IMG_MODEL_G)
    print("Kalit (oxiri) :", "..." + (config.IMG_KEY[-6:] if config.IMG_KEY else "YO'Q"))
print("=" * 50)

prompt = ("a glowing blue DNA double helix strand, 3D scientific illustration, "
          "dark background, highly detailed, professional")
print("Sinov prompt:", prompt[:60], "...")
print("Yaratilmoqda... (biroz kuting)")

path = rasm_yasa(prompt, 1024, 1024, "test_natija.jpg")

print("=" * 50)
if path and os.path.exists(path):
    print(f"✅ MUVAFFAQIYATLI! Rasm yaratildi: {path} ({os.path.getsize(path)} bayt)")
    print("   Faylni ochib rasmga qarang.")
else:
    print("❌ Rasm yaratilMADI. Yuqoridagi XATO xabarini o'qing.")
    print("   Ehtimoliy sabablar:")
    print("   • google-genai o'rnatilmagan  ->  pip install google-genai")
    print("   • billing (karta) yoqilmagan  ->  Google AI Studio'da to'lov sozlang")
    print("   • IMG_PROVIDER=gemini emas     ->  .env ni tekshiring")
