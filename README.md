# SlaytBot — mavzudan chiroyli taqdimot yasovchi Telegram bot

Foydalanuvchi mavzu yozadi → 9 shablondan tanlaydi → chiroyli, tahrirlanadigan `.pptx` oladi.

## Loyiha tuzilmasi
```
slaytbot/
├── .env               ← sirlar (token, AI). Git'ga TUSHMAYDI.
├── .env.example       ← namuna
├── requirements.txt   ← kutubxonalar
├── config.py          ← sozlamalarni .env dan o'qiydi
├── main.py            ← ISHGA TUSHIRISH nuqtasi
├── bot/               ← Telegram (handlers, keyboards)
├── ai/                ← AI: mavzu → JSON
├── slides/            ← templates (dizayn) + generator (JSON → pptx)
└── assets/            ← namoyish rasmi
```

---

## 1-qadam: Virtual muhit (venv) yaratish

Loyiha papkasida terminal ochib (VS Code'da: `Ctrl + ~`):

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux / Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Muvaffaqiyatli bo'lsa, satr boshida `(venv)` paydo bo'ladi.

> Virtual muhit — bu shu loyihaga alohida "quti". Kutubxonalar shu quti ichiga
> o'rnatiladi, boshqa loyihalarga aralashmaydi. Professional ish shundan boshlanadi.

## 2-qadam: Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

## 3-qadam: Sirlarni sozlash (Gemini bepul — tavsiya)
`.env` ni oching va to'ldiring:
```
BOT_TOKEN=BotFather_bergan_token
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=Gemini_kalit
AI_MODEL=gemini-2.5-flash
```
- **BOT_TOKEN** — Telegram'da @BotFather ga `/newbot` yozib olasan.
- **AI_API_KEY** — https://aistudio.google.com -> "Get API key" (BEPUL, karta shart emas).
  Serverga qo'yganда ham shu ishlaydi (GPU kerak emas).
- Muqobil: Groq yoki lokal Ollama — `.env.example` ichida ko'rsatilgan.

## 4-qadam: Ishga tushirish
```bash
python main.py
```
`✅ Bot ishga tushdi` chiqsa — Telegram'da botingga mavzu yozib sinab ko'r.

---

## VS Code'da to'g'ri sozlash
1. `File → Open Folder` → `slaytbot` papkasini och.
2. `Ctrl+Shift+P` → **Python: Select Interpreter** → `venv` ichidagini tanla.
3. Terminal ochsang, avtomatik `(venv)` faollashadi.

## Lokal AI (GPU) — Ollama namunasi
```bash
# Ollama o'rnatilgan bo'lsa:
ollama pull qwen2.5:7b     # modelni yuklab olish
ollama serve               # serverni yoqish (odatda avtomatik)
```
RTX 3060 Ti (8GB) uchun 7B model mos. Kattaroq model kerak bo'lsa yoki ko'p
foydalanuvchi kelsa — bulut API'ga o'tish tavsiya etiladi.

---

## Muammolar
| Belgi | Yechim |
|-------|--------|
| `BOT_TOKEN topilmadi` | `.env` faylini to'ldir |
| AI xato/noto'g'ri JSON | model kichik — promptni sinab tuzat yoki kattaroq model |
| `ModuleNotFoundError` | venv faol emas yoki `pip install -r requirements.txt` qilinmagan |

## Keyingi bosqichlar
1. Ikonka/rasm qatlami (Unsplash + mavzuga mos belgi).
2. O'zbekcha til sifatini AI promptida kuchaytirish.
3. Kunlik so'rov cheklovi.
4. Ko'p foydalanuvchi uchun rasm/AI'ni bulutga ko'chirish.


## YANGI TIZIM (shablon = config)
- `slides/design.py` — 8 shablon, har biri config (rang, shrift, fon, karta/rasm uslubi).
  Yangi shablon qo'shish = shu faylga yangi config yozish (kod yozilmaydi).
- `slides/render.py` — BITTA dvigatel: config'ni o'qib, har xil layout va uslub yasaydi.
- Oqim: mavzu -> 8 shablondan tanlash -> varaq soni (5-15) -> slayt.
- Rasm o'rni har shablonda belgilangan (AI rasm keyingi bosqichda tushadi).

## Shablonlar (8)
Modern · Editorial · Minimal · Corporate · Academic · Neon · Forest · Coral

## ORQA FON RASMLAR (assets/backgrounds/)
- Har shablonning o'z fon rasmi bor (nozik, abstrakt, bezak).
- design.py'da har shablonда `"bg_img": "nom.jpg"` — o'sha fon ishlatiladi.
- O'ZINGNING FONING: `assets/backgrounds/` ga rasm tashla, config'da nomini yoz — tayyor.
- Fon bo'lmasa, oddiy rang/gradient fon ishlatiladi (avtomatik).

## AI RASM (Pollinations — bepul, kalitsiz)
- Mavzuga mos rasm avtomatik yasaladi (sarlavha + image_text slaytlarga).
- Har shablonning o'z rasm uslubi bor (Neon → cyberpunk, Forest → tabiiy, ...).
- Kalit/karta SHART EMAS — Pollinations bepul.
- O'chirish: .env da RASM_YOQ=0 (unda placeholder ko'rinadi).
- Sekin bo'lsa yoki sifat kerak bo'lsa: IMG_MODEL yoki IMG_BASE ni o'zgartir.

## RASM PROVAYDERI (Pollinations vs Nano banana)
- pollinations (default): BEPUL, kalitsiz, cheksiz. Sifat o'rtacha.
- gemini (Nano banana): sifat yaxshi, lekin PULLIK (~$0.039/rasm) + billing/karta kerak.
  Ishlatish: .env da IMG_PROVIDER=gemini, va `pip install google-genai`.
  IMG_KEY bo'sh bo'lsa Gemini matn kaliti ishlatiladi.
- Xulosa slayti endi to'liq: sarlavha + asosiy fikrlar + yakuniy gap.

## RASMNI ALOHIDA SINASH
Botni ishga tushirmasdan rasm generatsiyani sinash uchun:
  python test_rasm.py
Muvaffaqiyatli bo'lsa test_natija.jpg yasaladi; xato bo'lsa aniq sabab chiqadi.

## NANO BANANA (pullik) ni yoqish — qadamlar
1. pip install google-genai
2. .env da: IMG_PROVIDER=gemini
3. Google AI Studio'da kalitga billing (karta) yoqing (rasm PULLIK)
4. python test_rasm.py  — ishlasa, bot ham ishlaydi

## TOGETHER AI (Flux) ni yoqish — arzon + sifatli
1. pip install together
2. together.ai da: Settings -> API Keys -> kalit ol
3. Together'da deposit qil (kalit faollashishi uchun ~$5-10)
4. .env da:
   IMG_PROVIDER=together
   IMG_TOGETHER_KEY=<kaliting>
   IMG_TOGETHER_MODEL=black-forest-labs/FLUX.2-dev   (yoki FLUX.2-pro sifatliroq)
5. python test_rasm.py  — ishlasa, bot ham ishlaydi

---

## ADMIN PANEL (botning o'zi ichida)

`.env` dagi `ADMIN_ID` bo'lgan odam Telegramda botga `/admin` yozsa, boshqa
hech kimga ko'rinmaydigan boshqaruv paneli ochiladi:

- **📊 Hisobot** — har xizmat necha marta ishlatilgani, pullik xizmatlar
  nechta to'lov va necha so'm keltirgani, botga jami necha kishi tashrif
  buyurgani.
- **⚙️ Sozlamalar**
  - **💰 Narxlar** — har pullik xizmat (Slayt yaratish, Ingliz yordamchisi)
    uchun ALOHIDA narx.
  - **🔓 Premium yoqish/o'chirish** — istalgan pullik xizmatni vaqtincha
    BEPUL qilib qo'yish mumkin (to'lov so'ralmaydi, darhol ishlaydi).
  - **💳 Karta ma'lumotlari** — talabalarga ko'rsatiladigan karta raqami/ism.
  - **🤖 AI sozlamalari** — Slayt, Matn tuzatish, Til bo'limi, Konspekt —
    har biri uchun ALOHIDA Gemini (yoki boshqa OpenAI-mos) base URL/kalit/model.
  - **🖼 Rasm sozlamalari** — rasm provayderi (pollinations/gemini/together)
    va uning kaliti/modeli.

**MUHIM:** shu paneldan o'zgartirilgan HAR NARSA `data/store.json` fayliga
yoziladi va **DARHOL** amal qiladi — botni serverda qayta ishga tushirish
SHART EMAS. `data/` papkasi `.gitignore`'da (unda API kalitlari bo'lishi
mumkin — git'ga tushmaydi, serverga alohida ko'chiring yoki admin panel
orqali qayta kiriting).
