"""
bot/handlers.py — bot OLTITA xizmat ko'rsatadi, ctx.user_data["mode"] orqali
ajratiladi ("slayt" | "tuzat" | "davom" | "konspekt" | "ingliz" | "tarjima"),
har biri o'z "holat" (bosqich) zanjiriga ega:

  DOIMIY tugmalar (bosh_klaviatura, har doim pastda ko'rinadi):
    🎨 Slayt yaratish       -> mavzu -> [uslub] -> [varaq soni] -> reja (tahrirlanadi)
                            -> [✅ Yaratish] -> TO'LOV (Click, avtomatik)
                            -> to'lov tasdiqlangach -> rasm + render -> fayl yuboriladi
    🪄 Matn tuzatish        -> [daraja: imlo/ravon] -> .docx kutiladi
                            -> hisobot + tuzatilgan fayl qaytariladi
    🧩 Davom ettirish       -> necha so'z qo'shilsin? -> .docx/.pdf kutiladi
                            -> hisobot + davom ettirilgan fayl qaytariladi
    📋 Konspekt qilish      -> matn yoki .docx/.pdf kutiladi
                            -> qisqa, tuzilgan konspekt (matn yoki .docx, hajmiga qarab)
    🇬🇧 Ingliz yordamchisi  -> [IELTS/Grammatika/Ravon] -> matn yoki .docx kutiladi
                            -> TO'LOV (Click, avtomatik) -> to'lov tasdiqlangach
                            -> natija (IELTS — HAR DOIM matn; qolganlari matn/.docx)
    🌐 Ilmiy tarjima        -> [maqsad til: uz/en/ru] -> matn yoki .docx kutiladi
                            -> tarjima (matn yoki .docx, hajmiga qarab)

To'lov — Click (click.uz) orqali TO'LIQ AVTOMATIK: talaba «💳 Click orqali
to'lash» tugmasini bosadi, to'laydi, Click bizga webhook yuboradi
(bot/click_webhook.py) va xizmat DARHOL, admin ishtirokisiz boshlanadi.

Barcha tugmalar ISTALGAN bosqichda ham bosilishi mumkin — joriy oqimni tozalab,
yangi xizmatni boshlab yuboradi (bot/keyboards.py dagi *_TUGMA konstantalari).

Har bosqichda faqat BITTA "asosiy xabar" ko'rinadi: yangi bosqichga o'tishda
avvalgisi o'chiriladi, so'ng yangisi yuboriladi — eski tugmalar/matn hech
qachon eskirib osilib qolmaydi. Foydalanuvchi yuborgan oraliq (boshqaruv)
xabarlar ham tozalik uchun o'chiriladi.
"""

import os
import re
import html
import uuid
import shutil
import asyncio
import logging
import tempfile
import textwrap

from docx import Document
from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ai.content import mavzudan_json
from ai.images import rasmlarni_tayyorla
from ai.docx_tuzat import docx_ni_tuzat
from ai.davom_yoz import davom_ettir
from ai.docx_umumiy import docx_matnini_ol
from ai.docx_til import docx_grammar, docx_ravon, docx_tarjima
from ai.til import ingliz_ielts, ingliz_grammar, ingliz_ravon, tarjima
from ai.konspekt import konspekt_qil, fayldan_matn_ol as konspekt_fayldan_matn_ol
from slides.render import render
from slides.design import TEMPLATES
from bot.keyboards import (bosh_klaviatura, SLAYT_TUGMA, TUZAT_TUGMA, DAVOM_TUGMA,
                           KONSPEKT_TUGMA,
                           INGLIZ_TUGMA, TARJIMA_TUGMA, ORQAGA_TUGMA, TEST_TUGMA,
                           ADMIN_XABAR_TUGMA,
                           FILE_QUIZ_BOT_USERNAME,
                           DARAJA_LABEL_KEY, tuzat_daraja_reply_klaviatura,
                           shablon_reply_klaviatura, SHABLON_LABEL_KEY,
                           varaq_reply_klaviatura, varaq_dan_n, VARAQ_BEPUL_N,
                           INGLIZ_DARAJA_LABEL_KEY, ingliz_daraja_reply_klaviatura,
                           TARJIMA_TIL_LABEL_KEY, tarjima_til_reply_klaviatura,
                           YARATISH_TUGMA, BEKOR_TUGMA, reja_reply_klaviatura,
                           bekor_reply_klaviatura,
                           slayd_tahrir_tugmasi, tahrir_klaviatura,
                           tolov_amal_klaviaturasi)
import config
import admin_store
import click_pay
from bot.admin import admin_matn_qabul, admin_rasm_qabul
from config import GRID_IMAGE

# Admin ("Adminga xabar" javob-yo'naltirishda) O'ZI shu tugmalardan birini
# bossa — bu doim TANISH buyruq deb hisoblanadi, hech qachon talabaga javob
# sifatida yuborilmaydi (matn_router:matn_router ichida tekshiriladi).
_ADMIN_UZI_ISHLATADIGAN_TUGMALAR = (
    SLAYT_TUGMA, TUZAT_TUGMA, DAVOM_TUGMA, KONSPEKT_TUGMA, INGLIZ_TUGMA,
    TARJIMA_TUGMA, TEST_TUGMA, ADMIN_XABAR_TUGMA, ORQAGA_TUGMA, BEKOR_TUGMA,
)


def _esc(matn):
    """HTML xabarlarga qo'yishdan oldin xavfsizlashtiradi (< > & belgilari)."""
    return html.escape(str(matn or ""))


def _md_qalin_htmlga(matn):
    """AI ba'zan **qalin** (Markdown) formatda javob beradi — buni Telegram
    HTML'iga (<b>...</b>) aylantiradi, avval xavfsizlashtirib."""
    escaped = _esc(matn)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.DOTALL)

log = logging.getLogger(__name__)

DAVOM_SOZ_MIN, DAVOM_SOZ_MAX = 10, 2000
NATIJA_MATN_LIMIT = 3500   # shundan uzun natija matn o'rniga .docx qilib yuboriladi


def _matn_boklarga_bol(matn, limit):
    """Uzun matnni QATOR chegaralarida bo'laklarga ajratadi (raw belgi soni
    bo'yicha emas) — aks holda keyinroq HTML'ga o'girilganda <b> tegi bo'lak
    chegarasida o'rtadan kesilib qolishi va Telegram xabarni rad etishi mumkin."""
    boklar, joriy = [], ""
    for qator in matn.split("\n"):
        qoshilgan = f"{joriy}\n{qator}" if joriy else qator
        if len(qoshilgan) > limit and joriy:
            boklar.append(joriy)
            joriy = qator
        else:
            joriy = qoshilgan
    if joriy:
        boklar.append(joriy)
    return boklar or [""]


def _som(n):
    """3500 -> '3 500' (so'm summasini chiroyli formatlaydi)."""
    return f"{n:,}".replace(",", " ")


def _xizmat_sarlavha(xizmat, nom, bepul_emoji):
    """Xizmat nomini, JORIY (admin panelda o'zgartirilishi mumkin bo'lgan)
    premium holatiga qarab, mos belgi bilan qaytaradi."""
    if admin_store.premium_yoqilganmi(xizmat):
        narx = _som(admin_store.narx_ol(xizmat, config.TOLOV_SUM))
        return f"👑 <b>{nom}</b> <i>(premium, {narx} so'm)</i>"
    return f"{bepul_emoji} <b>{nom}</b>"


def _salom_matni():
    """Bosh (/start) xabari — narx SHU YERDA aniq ko'rsatiladi, toki foydalanuvchi
    pullik xizmatlar haqida oldindan, hech qanday ajablanmasdan bilsin."""
    return (
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "Men sizga 7 xil xizmat ko'rsataman:\n"
        f"{_xizmat_sarlavha('slayt', 'Slayt yaratish', '🎨')} — mavzu bo'yicha "
        "zamonaviy, professional AI taqdimot (.pptx)\n"
        f"{_xizmat_sarlavha('tuzat', 'Matn tuzatish', '🪄')} — .docx hujjatdagi "
        "imlo/grammatikani tuzatish (format saqlanadi)\n"
        f"{_xizmat_sarlavha('davom', 'Davom ettirish', '🧩')} — chala qolgan .docx/.pdf "
        "hujjatni xuddi shu uslubda davom ettirib, to'liq va mukammal holga keltirish\n"
        f"{_xizmat_sarlavha('konspekt', 'Konspekt qilish', '📋')} — uzun matn/ma'ruza "
        "(.docx/.pdf) dan imtihonga tayyor, qisqa va tuzilgan konspekt yasash\n"
        f"{_xizmat_sarlavha('ingliz', 'Ingliz yordamchisi', '🇬🇧')} — IELTS baholash, "
        "grammatika va ravonlashtirish\n"
        f"{_xizmat_sarlavha('tarjima', 'Ilmiy tarjima', '🌐')} — matn yoki hujjatni "
        "o'zbek/ingliz/rus tiliga ilmiy uslubda tarjima\n"
        "📚 <b>Filedan test yaratish</b> — Word/PDF fayldan Telegram test (quiz) yaratish\n\n"
        "💬 Savol yoki muammo bo'lsa — <b>Adminga xabar</b> tugmasi orqali "
        "administrator bilan to'g'ridan-to'g'ri yozishing mumkin.\n\n"
        "Kerakli xizmatni tanlang 👇"
    )

TUR_EMOJI = {"image_text": "🖼️", "image": "🖼️", "bullets": "📝", "cards": "🗂️",
            "icons": "🔹", "stats": "📈", "steps": "🪜", "callout": "💡"}


# ---------- yordamchilar ----------

async def _ochir(msg):
    """Xabarni o'chiradi (tozalik uchun) — xato bo'lsa e'tiborsiz qoldiradi."""
    try:
        await msg.delete()
    except Exception:
        pass


async def _bosqichga_ot(ctx, chat_id, text, reply_markup=None, photo=None):
    """Eski 'asosiy xabar'ni o'chirib, yangisini yuboradi.
    Shu tariqa har doim faqat JORIY bosqich ko'rinadi — eskisi yo'qoladi."""
    eski = ctx.user_data.get("asosiy_msg")
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    if photo and os.path.exists(photo):
        with open(photo, "rb") as f:
            xabar = await ctx.bot.send_photo(chat_id, photo=InputFile(f), caption=text,
                                             parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        xabar = await ctx.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                                           reply_markup=reply_markup)
    ctx.user_data["asosiy_msg"] = (xabar.chat_id, xabar.message_id)


def _slayd_izohi(s):
    typ = s.get("type", "bullets")
    if typ in ("image_text", "image", "bullets"):
        return "; ".join(s.get("points", [])) or s.get("intro", "")
    if typ == "cards":
        return " | ".join(f"{c.get('h','')}: {c.get('d','')}" for c in s.get("cards", []))
    if typ == "icons":
        return " | ".join(f"{r.get('h','')}: {r.get('d','')}" for r in s.get("rows", []))
    if typ == "stats":
        return " | ".join(f"{x.get('num','')} {x.get('label','')}" for x in s.get("stats", []))
    if typ == "steps":
        return " → ".join(s.get("steps", []))
    if typ == "callout":
        return s.get("callout", "")
    return ""


def _reja_bosh_matni(deck):
    qatorlar = [f"📋 <b>{_esc(deck.get('title',''))}</b>"]
    if deck.get("subtitle"):
        qatorlar.append(f"<i>{_esc(deck['subtitle'])}</i>")
    qatorlar.append("")
    qatorlar.append("Har bir slayd — alohida xabarda. Kerak bo'lsa, tagidagi ✏️ tugmasi orqali tahrirlang.")
    return "\n".join(qatorlar)


def _slayd_karta_matni(i, s):
    """Bitta slaytning o'z xabaridagi ko'rinishi (sarlavha + qisqa mazmun)."""
    em = TUR_EMOJI.get(s.get("type", "bullets"), "📝")
    qatorlar = [f"{em} <b>{i}-slayt — {_esc(s.get('title',''))}</b>"]
    izoh = textwrap.shorten(_slayd_izohi(s), width=500, placeholder="…")
    if izoh:
        qatorlar.append(_esc(izoh))
    return "\n".join(qatorlar)


def _slayd_matni(s):
    typ = s.get("type", "bullets")
    if typ in ("image_text", "image", "bullets"):
        satrlar = [s.get("title", "")]
        if s.get("intro"):
            satrlar.append(s["intro"])
        satrlar += list(s.get("points", []))
    else:
        satrlar = [s.get("title", ""), _slayd_izohi(s)]
    return _esc("\n".join(x for x in satrlar if x))


def _hisobot_matni(ozgarishlar, jami, nom_label, sarlavha="Tuzatish hisoboti"):
    """Qayta ishlangan hujjat haqida ISHONCH beruvchi hisobot — nechta joy
    tekshirilib, nechtasi o'zgartirilgani va aniq NAMUNALAR bilan (fayldan
    OLDIN yuboriladi). Matn tuzatish, ingliz grammatikasi va tarjima uchun
    umumiy — faqat sarlavha/turi nomi farqlanadi."""
    nom = nom_label
    n = len(ozgarishlar)
    qatorlar = [
        f"📊 <b>{sarlavha}</b>",
        "",
        f"📄 Jami <b>{jami}</b> paragraf tekshirildi",
        f"✏️ <b>{n}</b> joyda o'zgartirish kiritildi",
        f"🎯 Turi: <b>{nom}</b>",
    ]
    if n == 0:
        qatorlar.append("\n✨ <b>Ajoyib!</b> Hujjatda xatolik topilmadi — matn allaqachon toza edi.")
        return "\n".join(qatorlar)

    NAMUNA_SONI = 5
    qatorlar.append("\n🔎 <b>Namuna tuzatishlar:</b>")
    raqam_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for i, (eski, yangi) in enumerate(ozgarishlar[:NAMUNA_SONI]):
        eski_q = _esc(textwrap.shorten(eski, width=90, placeholder="…"))
        yangi_q = _esc(textwrap.shorten(yangi, width=90, placeholder="…"))
        qatorlar.append(f"\n{raqam_emoji[i]} ❌ <i>{eski_q}</i>\n   ✅ <i>{yangi_q}</i>")
    qolgan = n - min(n, NAMUNA_SONI)
    if qolgan > 0:
        qatorlar.append(f"\n➕ ...va yana <b>{qolgan}</b> joyda tuzatish kiritildi.")
    qatorlar.append("\n👇 Tuzatilgan hujjat quyida:")
    return "\n".join(qatorlar)


def _boshiga_qaytar(ud):
    """Flow o'zgaruvchilarini tozalaydi (asosiy_msg dan tashqari). To'lov
    kutilayotgan FAYL asosli ish (ingliz yoki umumiy) bekor qilinsa, vaqtinchalik
    faylni ham diskdan o'chiradi (aks holda abadiy qolib ketaveradi)."""
    for pending_kalit in ("pending_ingliz", "pending_umumiy"):
        pending = ud.pop(pending_kalit, None)
        if pending and pending.get("kirish_yol") and os.path.exists(pending["kirish_yol"]):
            try:
                os.remove(pending["kirish_yol"])
            except Exception:
                pass
    ud.pop("tolov_id", None)
    ud.pop("tolov_summa", None)
    click_order_id = ud.pop("click_order_id", None)
    if click_order_id:
        click_pay.buyurtma_bekor_qil(click_order_id)
    for k in ("mode", "mavzu", "shablon", "jami", "deck", "tahrir_idx", "daraja",
             "davom_soz", "ingliz_daraja", "tarjima_til"):
        ud.pop(k, None)


async def _tolov_amal_tozala(ctx):
    """To'lov ekranidagi qo'shimcha ('nusxalash/tekshirish/bekor qilish')
    inline tugmali xabarni o'chiradi (agar bor bo'lsa)."""
    m = ctx.user_data.pop("tolov_amal_msg", None)
    if m:
        try:
            await ctx.bot.delete_message(chat_id=m[0], message_id=m[1])
        except Exception:
            pass


async def _asosiyga_qayt(ctx, chat_id, xabar=None):
    """Joriy oqimni butunlay tozalab, bosh menyuga (doimiy tugmalar) qaytaradi."""
    await _reja_tozala(ctx)
    await _tolov_amal_tozala(ctx)
    _boshiga_qaytar(ctx.user_data)
    await _bosqichga_ot(ctx, chat_id, xabar or _salom_matni(), bosh_klaviatura())
    ctx.user_data["holat"] = "asosiy"


async def _rejani_yubor(ctx, chat_id, deck):
    """Har slaydni ALOHIDA xabar sifatida yuboradi — har birining ostida
    o'ziga tegishli ✏️ Tahrirlash tugmasi bo'ladi (faqat o'sha slayd o'zgaradi).
    Bosh xabar — asosiy 6 tugma o'rniga FAQAT ✅ Yaratish / 🔁 Bekor qilishni
    ko'rsatadi, toki tasodifan boshqa xizmat bosilib, joriy ish uzilib qolmasin."""
    bosh = await ctx.bot.send_message(chat_id, _reja_bosh_matni(deck), parse_mode=ParseMode.HTML,
                                      reply_markup=reja_reply_klaviatura())
    ctx.user_data["reja_bosh"] = (bosh.chat_id, bosh.message_id)

    slaydlar = []
    for i, s in enumerate(deck.get("slides", []), 1):
        xabar = await ctx.bot.send_message(
            chat_id, _slayd_karta_matni(i, s), parse_mode=ParseMode.HTML,
            reply_markup=slayd_tahrir_tugmasi(i))
        slaydlar.append((xabar.chat_id, xabar.message_id))
    ctx.user_data["reja_slaydlar"] = slaydlar

    oxiri = await ctx.bot.send_message(chat_id, "👆 Kerak bo'lsa tahrirlang, tayyor bo'lsa 👇")
    ctx.user_data["reja_oxiri"] = (oxiri.chat_id, oxiri.message_id)


_QUMSOAT = ["⏳", "⌛"]


async def _kutish_boshla(ctx, chat_id, message_id, matn):
    """Fon vazifasi: xabardagi qumsoatni ⏳ <-> ⌛ orasida almashtirib turadi —
    foydalanuvchi jarayon TO'XTAB QOLMAGANINI ko'rib turishi uchun."""
    async def _aylantir():
        i = 0
        while True:
            await asyncio.sleep(2.5)
            i += 1
            try:
                await ctx.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"{_QUMSOAT[i % 2]} {matn}", parse_mode=ParseMode.HTML)
            except Exception:
                pass
    return asyncio.create_task(_aylantir())


async def _kutish_toxtat(vazifa):
    vazifa.cancel()
    try:
        await vazifa
    except asyncio.CancelledError:
        pass


async def _reja_tozala(ctx):
    """Reja bosqichidagi BARCHA xabarlarni (sarlavha + har slayt + oxiri) o'chiradi."""
    for kalit in ("reja_bosh", "reja_oxiri"):
        m = ctx.user_data.pop(kalit, None)
        if m:
            try:
                await ctx.bot.delete_message(chat_id=m[0], message_id=m[1])
            except Exception:
                pass
    for m in ctx.user_data.pop("reja_slaydlar", []):
        try:
            await ctx.bot.delete_message(chat_id=m[0], message_id=m[1])
        except Exception:
            pass


# ---------- /start ----------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    eski = ctx.user_data.get("asosiy_msg")
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    ctx.user_data.clear()
    ctx.user_data["holat"] = "asosiy"
    admin_store.tashrif_qayd_et(update.effective_user.id)
    await update.message.reply_text(_salom_matni(), parse_mode=ParseMode.HTML, reply_markup=bosh_klaviatura())


# ---------- bosh menyu (DOIMIY tugmalar orqali xizmat tanlash) ----------

async def _xizmat_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tanlov: str):
    """Doimiy tugma (🎨 Slayt / 🪄 Matn tuzatish / 🧩 Davom ettirish) bosilganda —
    istalgan bosqichda ham ishlaydi, joriy oqimni tozalab, yangi xizmatni boshlaydi."""
    await _ochir(update.message)
    await _reja_tozala(ctx)
    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    _boshiga_qaytar(ctx.user_data)
    ctx.user_data["mode"] = tanlov
    chat_id = update.effective_chat.id
    if tanlov == "slayt":
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('slayt', 'Slayt yaratish', '🎨')}\n\n"
            "✍️ <b>Mavzuni yozing</b> (masalan: «Vulqonlar»):")
        ctx.user_data["holat"] = "mavzu"
    elif tanlov == "tuzat":
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('tuzat', 'Matn tuzatish', '🪄')}\n\n"
            "🔍 <b>Imlo</b> — faqat xato harflar, tinish belgilari, kelishiklar "
            "tuzatiladi (ma'no o'zgarmaydi).\n"
            "🌟 <b>Ravon</b> — imlo tuzatiladi VA jumlalar adabiy, ravon tilga "
            "moslashtiriladi (ma'no saqlanadi, uslub yaxshilanadi).",
            tuzat_daraja_reply_klaviatura())
        ctx.user_data["holat"] = "tuzat_daraja"
    elif tanlov == "davom":
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('davom', 'Davom ettirish', '🧩')}\n\n"
            "Chala qolgan yoki to'liq bo'lmagan hujjatingizni tahlil qilib, "
            "xuddi shu uslubda davom ettirib beraman.\n\n"
            f"✍️ <b>Necha so'zlik davom qo'shilsin?</b> ({DAVOM_SOZ_MIN} dan {DAVOM_SOZ_MAX} gacha)\n"
            "<i>Masalan: 200</i>")
        ctx.user_data["holat"] = "davom_soz"
    elif tanlov == "konspekt":
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('konspekt', 'Konspekt qilish', '📋')}\n\n"
            "Uzun matn yoki ma'ruza hujjatingizni imtihonga tayyor, qisqa va "
            "tuzilgan KONSPEKTGA aylantiraman — asosiy fikrlar, ta'riflar va "
            "faktlar saqlanadi.\n\n"
            "✍️ Matningizni yuboring (matn sifatida yoki <b>.docx</b>/<b>.pdf</b> fayl).")
        ctx.user_data["holat"] = "konspekt_kutish"
    elif tanlov == "ingliz":
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('ingliz', 'Ingliz yordamchisi', '🇬🇧')}\n\n"
            "📝 <b>IELTS baholash</b> — essangizni rasmiy IELTS mezonlari bo'yicha "
            "baholaydi (ball + xatolar + maslahatlar).\n"
            "🔤 <b>Grammatika</b> — ingliz matningizdagi grammatik xatolarni tuzatadi.\n"
            "🌟 <b>Ravon</b> — matningizni tabiiy, native ingliz tiliga moslashtiradi.",
            ingliz_daraja_reply_klaviatura())
        ctx.user_data["holat"] = "ingliz_daraja"
    else:  # "tarjima"
        await _bosqichga_ot(
            ctx, chat_id,
            f"{_xizmat_sarlavha('tarjima', 'Ilmiy tarjima', '🌐')}\n\n"
            "Matningiz tilini avtomatik aniqlab, tanlagan tilingizga ilmiy-rasmiy "
            "uslubda tarjima qilaman.\n\n"
            "🎯 <b>Qaysi tilga tarjima qilay?</b>",
            tarjima_til_reply_klaviatura())
        ctx.user_data["holat"] = "tarjima_til"


async def _filedan_test_yaratish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """📚 Filedan test yaratish doimiy tugmasi bosilganda — joriy oqimga tegmaydi,
    faqat Word/PDF fayldan test yaratadigan alohida Quiz botga (@FileQuizMakerBot)
    o'tuvchi havolani yuboradi. Reply keyboard tugmasi URL ochib bera olmaydi
    (Telegram cheklovi), shu sabab qo'shimcha tugma chiqarmay — faqat toza havola
    yuboriladi, Telegram uni o'zi bosiladigan link qilib ko'rsatadi."""
    await _ochir(update.message)
    admin_store.xizmat_ishlatildi("test_link")
    await update.message.reply_text(
        "📚 Filedan test yaratish uchun havolani bosing — Quiz bot ochiladi va "
        "Start avtomatik bosiladi:\n"
        f"https://t.me/{FILE_QUIZ_BOT_USERNAME}?start=slaytbot")


# ---------- Adminga xabar (ikki tomonlama chat) ----------
#
# Admin javob yozganda ANIQLASH ikki bosqichda ishlaydi:
#   1) Agar Telegramning "Reply" funksiyasi orqali ANIQ bir xabarga javob
#      yozgan bo'lsa — O'SHA xabar egasi talabaga (xarita orqali, ANIQ).
#   2) Aks holda (oddiy, reply qilmasdan yozilgan matn) — ENG SO'NGGI
#      murojaat qilgan talabaga (_ADMIN_FAOL_TALABA orqali) — admin "Reply"
#      qilishni bilmasa/unutsa ham oddiy yozib javob bera olishi uchun.
# Bularning IKKALASI ham FAQAT xotirada — bot qayta ishga tushsa tozalanadi.

_ADMIN_XABAR_XARITA = {}
_ADMIN_XABAR_XARITA_LIMIT = 2000
_ADMIN_FAOL_TALABA = None   # eng so'nggi "adminga xabar" yuborgan talabaning chat_id'si


def _admin_xabar_xaritaga_qosh(admin_msg_id, talaba_chat_id):
    """Xarita cheksiz o'smasin deb, limitdan oshsa ENG ESKI yozuvni o'chiradi."""
    if len(_ADMIN_XABAR_XARITA) >= _ADMIN_XABAR_XARITA_LIMIT:
        eski_kalit = next(iter(_ADMIN_XABAR_XARITA), None)
        _ADMIN_XABAR_XARITA.pop(eski_kalit, None)
    _ADMIN_XABAR_XARITA[admin_msg_id] = talaba_chat_id


async def _admin_xabar_boshla(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """💬 Adminga xabar doimiy tugmasi bosilganda — shu paytdan boshlab
    yozilgan HAR BIR xabar administratorga yuboriladi (admin javob yozsa, shu
    yerda ko'rinadi — ikki tomonlama chat, istalgancha davom etadi)."""
    await _ochir(update.message)
    await _reja_tozala(ctx)
    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    _boshiga_qaytar(ctx.user_data)
    ctx.user_data["mode"] = "admin_chat"
    chat_id = update.effective_chat.id
    await _bosqichga_ot(
        ctx, chat_id,
        "💬 <b>Adminga xabar</b>\n\n"
        "Yozgan xabaringiz to'g'ridan-to'g'ri administratorga yuboriladi. Admin "
        "javob bersa, shu yerda ko'rasiz — istalgancha yozishingiz mumkin.\n\n"
        "✍️ Xabaringizni yozing:")
    ctx.user_data["holat"] = "admin_chat_faol"


async def _admin_xabar_yubor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Talaba «💬 Adminga xabar» rejimida matn yozganda — adminga yuboradi.
    ADMIN'NING O'ZI (config.ADMIN_ID) buni HECH QACHON chaqirmasligi kerak —
    aks holda admin o'ziga o'zi xabar yuborib qo'yadi (matn_router buni yuqorida
    ushlab, admin uchun _admin_javob_yubor ga yo'naltiradi)."""
    global _ADMIN_FAOL_TALABA
    matn = (update.message.text or "").strip()
    if not matn:
        return
    chat_id = update.effective_chat.id
    if not config.ADMIN_ID:
        await update.message.reply_text(
            "😔 Kechirasiz, hozircha bu funksiya sozlanmagan. Keyinroq urinib ko'ring.")
        return
    if chat_id == config.ADMIN_ID:
        # Himoya qatlami: matn_router yuqorida buni allaqachon _admin_javob_yubor
        # ga yo'naltirishi kerak edi — shu yerga yetib kelsa, hali hech kim
        # murojaat qilmagan (faol suhbat yo'q) degani, o'ziga o'zi yubormaydi.
        await update.message.reply_text(
            "ℹ️ Hozircha sizga murojaat qilgan hech kim yo'q. Kimdir yozganda, "
            "shu yerga oddiy javob yozishingiz yetarli.")
        return
    user = update.effective_user
    ism = _esc(user.full_name or "Noma'lum")
    username = f"@{user.username}" if user.username else "(username yo'q)"
    izoh = (
        "💬 <b>Yangi xabar</b>\n\n"
        f"👤 {ism} {username}\n"
        f"🆔 <code>{chat_id}</code>\n\n"
        f"{_esc(matn)}"
    )
    try:
        yuborilgan = await ctx.bot.send_message(config.ADMIN_ID, izoh, parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("adminga xabar yuborishda xato")
        await update.message.reply_text("😔 Kechirasiz, xabar yuborilmadi. Qaytadan urinib ko'ring.")
        return
    _admin_xabar_xaritaga_qosh(yuborilgan.message_id, chat_id)
    _ADMIN_FAOL_TALABA = chat_id
    await update.message.reply_text("✅ Yuborildi. Javob kelsa, shu yerda ko'rasiz.")


def _admin_javob_talaba_id(update: Update):
    """Admin yozgan xabar QAYSI talabaga tegishli ekanini aniqlaydi:
    1) Aniq "Reply" qilingan bo'lsa — o'sha xabar egasi (ANIQ).
    2) Aks holda — eng so'nggi murojaat qilgan talaba (admin oddiy yozsa ham
       ishlashi uchun — "Reply" qilishni bilishi/eslashi shart emas)."""
    if update.message.reply_to_message:
        aniq = _ADMIN_XABAR_XARITA.get(update.message.reply_to_message.message_id)
        if aniq is not None:
            return aniq
    return _ADMIN_FAOL_TALABA


async def _admin_javob_yubor(update: Update, ctx: ContextTypes.DEFAULT_TYPE, talaba_id):
    """Admin (reply qilib yoki oddiy yozib) javob yozganda — aniqlangan
    talaba_id'ga yetkazadi."""
    matn = (update.message.text or "").strip()
    if not matn:
        return
    try:
        await ctx.bot.send_message(
            talaba_id, f"👨‍💼 <b>Admin javobi:</b>\n\n{_esc(matn)}", parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("talabaga admin javobini yuborishda xato (talaba_id=%s)", talaba_id)
        await update.message.reply_text(
            "😔 Yuborilmadi — foydalanuvchi botni bloklagan bo'lishi mumkin.")
        return
    await update.message.reply_text("✅ Javobingiz yuborildi.")


DARAJA_NOMI = {"imlo": "Imlo", "ravon": "Ravon"}


async def _daraja_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, daraja: str):
    """🔍 Imlo / 🌟 Ravon doimiy tugmasi bosilganda."""
    await _ochir(update.message)
    ctx.user_data["daraja"] = daraja
    nom = DARAJA_NOMI.get(daraja, daraja)
    chat_id = update.effective_chat.id
    await _bosqichga_ot(
        ctx, chat_id,
        f"✨ «{nom}» darajasi tanlandi.\n\n"
        f"📎 Endi tuzatish kerak bo'lgan <b>.docx</b> faylni yuboring.",
        bosh_klaviatura())
    ctx.user_data["holat"] = "tuzat_fayl"


INGLIZ_DARAJA_NOMI = {"ielts": "IELTS baholash", "grammar": "Grammatika", "ravon": "Ravon"}


async def _ingliz_daraja_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, daraja: str):
    """📝 IELTS / 🔤 Grammatika / 🌟 Ravon (ingliz) doimiy tugmasi bosilganda."""
    await _ochir(update.message)
    ctx.user_data["ingliz_daraja"] = daraja
    nom = INGLIZ_DARAJA_NOMI.get(daraja, daraja)
    chat_id = update.effective_chat.id
    await _bosqichga_ot(
        ctx, chat_id,
        f"✨ «{nom}» tanlandi.\n\n"
        f"✍️ Ingliz tilidagi matningizni yuboring (matn sifatida yoki <b>.docx</b> fayl).",
        bosh_klaviatura())
    ctx.user_data["holat"] = "ingliz_kutish"


TARJIMA_TIL_NOMI = {"uz": "O'zbekcha", "en": "Inglizcha", "ru": "Ruscha"}


async def _tarjima_til_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, til: str):
    """🇺🇿/🇬🇧/🇷🇺 maqsad til doimiy tugmasi bosilganda."""
    await _ochir(update.message)
    ctx.user_data["tarjima_til"] = til
    nom = TARJIMA_TIL_NOMI.get(til, til)
    chat_id = update.effective_chat.id
    await _bosqichga_ot(
        ctx, chat_id,
        f"✨ «{nom}»ga tarjima tanlandi.\n\n"
        f"✍️ Tarjima qilinadigan matnni yuboring (matn sifatida yoki <b>.docx</b> fayl).",
        bosh_klaviatura())
    ctx.user_data["holat"] = "tarjima_kutish"


async def _davom_soz_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Davom ettirish uchun 'necha so'z qo'shilsin' javobini qabul qiladi."""
    matn = update.message.text.strip()
    await _ochir(update.message)
    if not matn.isdigit() or not (DAVOM_SOZ_MIN <= int(matn) <= DAVOM_SOZ_MAX):
        await update.message.reply_text(
            f"Iltimos, {DAVOM_SOZ_MIN} dan {DAVOM_SOZ_MAX} gachasini son bilan yozing.\n"
            f"<i>Masalan: 200</i>", parse_mode=ParseMode.HTML)
        return
    ctx.user_data["davom_soz"] = int(matn)
    chat_id = update.effective_chat.id
    await _bosqichga_ot(
        ctx, chat_id,
        f"✨ Taxminan <b>{matn} so'z</b> qo'shiladi.\n\n"
        f"📎 Endi tugallanmagan hujjatingizni (<b>.docx</b> yoki <b>.pdf</b>) yuboring.",
        bosh_klaviatura())
    ctx.user_data["holat"] = "tuzat_fayl"


async def _natijani_yubor(ctx, chat_id, natija, majburiy_matn=False, fayl_nomi="natija"):
    """AI natijasini chatga yuboradi: qisqa bo'lsa (yoki majburiy_matn=True) —
    matn (**qalin** Markdown bo'lsa HTML'ga o'girib), aks holda — .docx fayl
    sifatida (Telegram xabar limitidan oshib ketmasin)."""
    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    if majburiy_matn or len(natija) <= NATIJA_MATN_LIMIT:
        # Avval RAW matnni bo'laklarga bo'lamiz (qator chegaralarida), so'ng
        # HAR BIR bo'lakni ALOHIDA HTML'ga o'giramiz — aks holda <b> tegi
        # bo'lak chegarasida o'rtadan kesilib, Telegram xabarni rad etishi mumkin.
        for bok in _matn_boklarga_bol(natija, NATIJA_MATN_LIMIT):
            await ctx.bot.send_message(chat_id, _md_qalin_htmlga(bok), parse_mode=ParseMode.HTML)
    else:
        doc = Document()
        for qator in natija.split("\n"):
            if qator.strip():
                doc.add_paragraph(qator.strip())
        yol = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_{fayl_nomi}.docx")
        try:
            doc.save(yol)
            with open(yol, "rb") as f:
                await ctx.bot.send_document(chat_id, document=InputFile(f),
                                            filename=f"{fayl_nomi}.docx",
                                            caption="✅ Natija tayyor.")
        finally:
            if os.path.exists(yol):
                os.remove(yol)
    await _asosiyga_qayt(ctx, chat_id, "🎉 Tayyor!\nYana nimadir qilmoqchimisiz? 👇")


async def _ingliz_matn_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ingliz yordamchisi rejimida MATN (fayl emas) qabul qilinganda — endi
    TO'LOV talab qiladi, tahlil FAQAT admin tasdiqlagach boshlanadi
    (_ingliz_natija_yarat_va_yubor)."""
    if ctx.user_data.get("ishlanmoqda"):
        await update.message.reply_text("⏳ Iltimos kuting, oldingi so'rov hali tayyorlanmoqda...")
        return
    matn = update.message.text.strip()
    daraja = ctx.user_data.get("ingliz_daraja", "grammar")
    chat_id = update.effective_chat.id
    await _ochir(update.message)
    ctx.user_data["pending_ingliz"] = {"daraja": daraja, "matn": matn, "kirish_yol": None, "nomi": None}
    await _tolov_sora(ctx, chat_id)


async def _tarjima_matn_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ilmiy tarjima rejimida MATN (fayl emas) qabul qilinganda — premium
    yoqiq bo'lsa TO'LOV so'raladi, o'chiq bo'lsa darhol ishlaydi (_tolov_sora
    ichida hal qilinadi, natijani _umumiy_natija_yarat_va_yubor beradi)."""
    if ctx.user_data.get("ishlanmoqda"):
        await update.message.reply_text("⏳ Iltimos kuting, oldingi so'rov hali tayyorlanmoqda...")
        return
    matn = update.message.text.strip()
    chat_id = update.effective_chat.id
    await _ochir(update.message)
    ctx.user_data["pending_umumiy"] = {"kirish_yol": None, "nomi": None, "matn": matn}
    await _tolov_sora(ctx, chat_id)


async def _konspekt_matn_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Konspekt qilish rejimida MATN (fayl emas) qabul qilinganda — premium
    yoqiq bo'lsa TO'LOV so'raladi, o'chiq bo'lsa darhol ishlaydi."""
    if ctx.user_data.get("ishlanmoqda"):
        await update.message.reply_text("⏳ Iltimos kuting, oldingi so'rov hali tayyorlanmoqda...")
        return
    matn = update.message.text.strip()
    chat_id = update.effective_chat.id
    await _ochir(update.message)
    ctx.user_data["pending_umumiy"] = {"kirish_yol": None, "nomi": None, "matn": matn}
    await _tolov_sora(ctx, chat_id)


# ---------- matn xabarlar (bitta router) ----------

# To'lov (Click) kutilayotgan bosqich uchun UMUMIY eslatma — istalgan pullik
# xizmat (slayt, ingliz, ...) shu holatdan o'tadi.
_TOLOV_ESLATMA = {
    "tolov_kutilmoqda": "💳 Iltimos, yuqoridagi «💳 Click orqali to'lash» tugmasini bosib "
                        "to'lovni yakunlang (yoki 🔁 Bekor qilish tugmasini bosing).",
}


async def matn_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Admin panelda ✏️ tugmasi bosilgach kutilayotgan matn (narx, karta, AI
    # kaliti va h.k.) — ENG BOSHIDA ushlanadi, oddiy foydalanuvchilar oqimiga
    # umuman tegmaydi (admin_tahrir faqat admin uchun va faqat shu holatda bor).
    if ctx.user_data.get("admin_tahrir"):
        await admin_matn_qabul(update, ctx)
        return

    matn = (update.message.text or "").strip()

    # Admin (config.ADMIN_ID) talabaga javob yozmoqchi bo'lsa — bu ENG BOSHIDA
    # ushlanadi. "Reply" qilingan bo'lsa ANIQ o'sha talabaga, aks holda ENG
    # SO'NGGI murojaat qilgan talabaga (admin "Reply" qilishni bilmasa/unutsa
    # ham oddiy yozib javob bera olishi uchun — aks holda o'ziga o'zi
    # yuborilib, talabaga hech narsa bormay qolar edi). Admin biror TANISH
    # tugmani (masalan o'zi biror xizmatni sinab ko'rmoqchi) bossa yoki
    # allaqachon boshqa xizmat oqimida bo'lsa (mode boshqa narsaga teng) — bu
    # ustunlik qilmaydi.
    if (config.ADMIN_ID and update.effective_user.id == config.ADMIN_ID
            and matn not in _ADMIN_UZI_ISHLATADIGAN_TUGMALAR
            and ctx.user_data.get("mode") in (None, "admin_chat")):
        talaba_id = _admin_javob_talaba_id(update)
        if talaba_id is not None:
            await _admin_javob_yubor(update, ctx, talaba_id)
            return

    if matn == SLAYT_TUGMA:
        await _xizmat_tanlandi(update, ctx, "slayt")
        return
    if matn == TUZAT_TUGMA:
        await _xizmat_tanlandi(update, ctx, "tuzat")
        return
    if matn == DAVOM_TUGMA:
        await _xizmat_tanlandi(update, ctx, "davom")
        return
    if matn == KONSPEKT_TUGMA:
        await _xizmat_tanlandi(update, ctx, "konspekt")
        return
    if matn == INGLIZ_TUGMA:
        await _xizmat_tanlandi(update, ctx, "ingliz")
        return
    if matn == TARJIMA_TUGMA:
        await _xizmat_tanlandi(update, ctx, "tarjima")
        return
    if matn == TEST_TUGMA:
        await _filedan_test_yaratish(update, ctx)
        return
    if matn == ADMIN_XABAR_TUGMA:
        await _admin_xabar_boshla(update, ctx)
        return
    # Orqaga / Bekor qilish — QAYSI mode/holatda bo'lishidan qat'iy nazar
    # (reja ko'rib chiqish, to'lov kutish va h.k.) doim bosh menyuga qaytaradi.
    # Bekor qilish faqat shu holatlarda ko'rsatiladigan klaviaturalarda bo'ladi,
    # shu sabab qaysi holatda ekanini alohida tekshirish shart emas.
    if matn in (ORQAGA_TUGMA, BEKOR_TUGMA):
        await _ochir(update.message)
        await _asosiyga_qayt(ctx, update.effective_chat.id)
        return

    mode = ctx.user_data.get("mode")
    holat = ctx.user_data.get("holat", "asosiy")

    if mode == "slayt":
        if holat == "mavzu":
            await _mavzu_qabul(update, ctx)
            return
        if holat == "shablon" and matn in SHABLON_LABEL_KEY:
            await _shablon_tanlandi(update, ctx, SHABLON_LABEL_KEY[matn])
            return
        if holat == "varaq":
            n = varaq_dan_n(matn)
            if n is not None:
                await _varaq_tanlandi(update, ctx, n)
                return
        if holat == "tahrir":
            await _tahrir_matni_qabul(update, ctx)
            return
        if holat == "reja" and matn == YARATISH_TUGMA:
            await _taqdimotni_yarat(update, ctx)
            return
        if holat in _TOLOV_ESLATMA:
            await update.message.reply_text(_TOLOV_ESLATMA[holat])
            return
        ESLATMALAR = {
            "shablon": "☝️ Iltimos, yuqoridagi uslublardan birini tanlang.",
            "varaq": "☝️ Iltimos, yuqoridagi varaq sonlaridan birini tanlang.",
            "reja": "☝️ ✏️ Tahrirlash, yoki pastdagi ✅ Yaratish / 🔁 Bekor qilish tugmasini bosing.",
        }
        await update.message.reply_text(ESLATMALAR.get(holat, "☝️ Yuqoridagi tugmalardan birini tanlang."))
        return

    if mode == "tuzat":
        if holat == "tuzat_daraja" and matn in DARAJA_LABEL_KEY:
            await _daraja_tanlandi(update, ctx, DARAJA_LABEL_KEY[matn])
            return
        if holat == "tuzat_fayl":
            await update.message.reply_text("📎 Iltimos, matn emas — <b>.docx</b> faylni yuboring.",
                                            parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("☝️ Yuqoridagi tugmalardan birini tanlang.")
        return

    if mode == "davom":
        if holat == "davom_soz":
            await _davom_soz_qabul(update, ctx)
            return
        if holat == "tuzat_fayl":
            await update.message.reply_text("📎 Iltimos, matn emas — <b>.docx</b> yoki <b>.pdf</b> faylni yuboring.",
                                            parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("☝️ Yuqoridagi ko'rsatmaga amal qiling.")
        return

    if mode == "konspekt":
        if holat == "konspekt_kutish":
            await _konspekt_matn_qabul(update, ctx)
            return
        await update.message.reply_text("☝️ Yuqoridagi ko'rsatmaga amal qiling.")
        return

    if mode == "ingliz":
        if holat == "ingliz_daraja" and matn in INGLIZ_DARAJA_LABEL_KEY:
            await _ingliz_daraja_tanlandi(update, ctx, INGLIZ_DARAJA_LABEL_KEY[matn])
            return
        if holat == "ingliz_kutish":
            await _ingliz_matn_qabul(update, ctx)
            return
        if holat in _TOLOV_ESLATMA:
            await update.message.reply_text(_TOLOV_ESLATMA[holat])
            return
        await update.message.reply_text("☝️ Yuqoridagi ko'rsatmaga amal qiling.")
        return

    if mode == "tarjima":
        if holat == "tarjima_til" and matn in TARJIMA_TIL_LABEL_KEY:
            await _tarjima_til_tanlandi(update, ctx, TARJIMA_TIL_LABEL_KEY[matn])
            return
        if holat == "tarjima_kutish":
            await _tarjima_matn_qabul(update, ctx)
            return
        await update.message.reply_text("☝️ Yuqoridagi ko'rsatmaga amal qiling.")
        return

    if mode == "admin_chat":
        if holat == "admin_chat_faol":
            await _admin_xabar_yubor(update, ctx)
            return
        await update.message.reply_text("☝️ Yuqoridagi ko'rsatmaga amal qiling.")
        return

    await update.message.reply_text("Boshlash uchun /start bosing 👇")


async def _mavzu_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mavzu = update.message.text.strip()
    await _ochir(update.message)
    if len(mavzu) < 3:
        await update.message.reply_text("Iltimos, mavzuni to'liqroq yozing.")
        return
    ctx.user_data["mavzu"] = mavzu
    await _bosqichga_ot(ctx, update.effective_chat.id,
                        f"🎯 Mavzu: «{_esc(mavzu)}»\n\n🎨 Qaysi uslubda yasay?",
                        shablon_reply_klaviatura(),
                        photo=GRID_IMAGE if os.path.exists(GRID_IMAGE) else None)
    ctx.user_data["holat"] = "shablon"


# ---------- doimiy tugmalar orqali ketma-ket tanlovlar ----------

async def _shablon_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, key: str):
    await _ochir(update.message)
    ctx.user_data["shablon"] = key
    nom = TEMPLATES.get(key, {}).get("nom", key)
    chat_id = update.effective_chat.id
    pullik = admin_store.premium_yoqilganmi("slayt")
    bepul_mavjudmi = pullik and not admin_store.bepul_slayt_ishlatganmi(chat_id)
    narx = admin_store.narx_ol("slayt", config.TOLOV_SUM) if pullik else 0
    matn = f"✨ «{nom}» tanlandi.\n\n📄 Nechta varaq bo'lsin?"
    if bepul_mavjudmi:
        matn += f"\n\n🎁 Birinchi marta — <b>{VARAQ_BEPUL_N} varoqli</b> taqdimot BEPUL!"
    await _bosqichga_ot(ctx, chat_id, matn,
                        varaq_reply_klaviatura(pullik, bepul_mavjudmi, narx))
    ctx.user_data["holat"] = "varaq"


async def _varaq_tanlandi(update: Update, ctx: ContextTypes.DEFAULT_TYPE, jami: int):
    if ctx.user_data.get("ishlanmoqda"):
        await update.message.reply_text("⏳ Iltimos kuting, reja allaqachon tuzilmoqda...")
        return
    mavzu = ctx.user_data.get("mavzu")
    if not mavzu:
        await update.message.reply_text("Avval mavzuni yozing.")
        return
    await _ochir(update.message)
    key = ctx.user_data.get("shablon", "modern")
    ctx.user_data["jami"] = jami
    chat_id = update.effective_chat.id
    await _bosqichga_ot(ctx, chat_id, "⏳ Taqdimot rejasi tuzilmoqda, biroz kuting...")

    ctx.user_data["ishlanmoqda"] = True
    cid, mid = ctx.user_data["asosiy_msg"]
    animatsiya = await _kutish_boshla(ctx, cid, mid, "Taqdimot rejasi tuzilmoqda, biroz kuting...")
    try:
        # AI chaqiruvi sinxron (bloklovchi) — event loop bo'shashishi uchun alohida oqimda ishlatamiz
        deck = await asyncio.to_thread(mavzudan_json, mavzu, jami - 2)  # sarlavha+xulosa
        deck["template"] = key
        ctx.user_data["deck"] = deck
    except Exception:
        log.exception("reja xato")
        await _kutish_toxtat(animatsiya)
        await _asosiyga_qayt(ctx, chat_id, "😔 Kechirasiz, reja tuzishda xatolik bo'ldi. Qaytadan urinib ko'ring 👇")
        return
    finally:
        ctx.user_data["ishlanmoqda"] = False
    await _kutish_toxtat(animatsiya)

    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    await _rejani_yubor(ctx, chat_id, deck)
    ctx.user_data["holat"] = "reja"


async def slayd_tahrir_bosildi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Faqat SHU slaytning xabari o'zgaradi — qolgan slayt xabarlari tegilmaydi."""
    q = update.callback_query
    deck = ctx.user_data.get("deck")
    if not deck:
        await q.answer("Avval yangi mavzu boshlang.", show_alert=True)
        return
    idx = int(q.data.split(":", 1)[1]) - 1
    slides = deck.get("slides", [])
    if not (0 <= idx < len(slides)):
        await q.answer()
        return
    await q.answer()
    ctx.user_data["tahrir_idx"] = idx
    joriy = _slayd_matni(slides[idx])
    await q.edit_message_text(
        f"✍️ <b>{idx + 1}-slayt</b> uchun yangi matn yuboring.\n"
        f"Birinchi qator — sarlavha, keyingi har bir qator — alohida band.\n\n"
        f"<i>Joriy holati:</i>\n{joriy}",
        parse_mode=ParseMode.HTML, reply_markup=tahrir_klaviatura())
    ctx.user_data["holat"] = "tahrir"


async def tahrir_bekor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tahrirlashni bekor qiladi — SHU slaytning xabarini avvalgi ko'rinishga qaytaradi."""
    q = update.callback_query; await q.answer()
    deck = ctx.user_data.get("deck")
    idx = ctx.user_data.get("tahrir_idx")
    if deck is None or idx is None:
        return
    slide = deck["slides"][idx]
    await q.edit_message_text(_slayd_karta_matni(idx + 1, slide), parse_mode=ParseMode.HTML,
                              reply_markup=slayd_tahrir_tugmasi(idx + 1))
    ctx.user_data["holat"] = "reja"


async def _tahrir_matni_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ochir(update.message)
    deck = ctx.user_data.get("deck")
    idx = ctx.user_data.get("tahrir_idx")
    reja_slaydlar = ctx.user_data.get("reja_slaydlar", [])
    if deck is None or idx is None or not (0 <= idx < len(reja_slaydlar)):
        ctx.user_data["holat"] = "asosiy"
        return
    satrlar = [s.strip() for s in update.message.text.split("\n") if s.strip()]
    if not satrlar:
        return
    sarlavha, bandlar = satrlar[0], satrlar[1:]
    slide = deck["slides"][idx]
    if slide.get("type") in ("bullets", "image_text", "image"):
        slide["title"] = sarlavha
        slide["points"] = bandlar
        slide.pop("intro", None)
    else:
        rasm = slide.get("image")
        yangi = {"type": "image_text" if rasm else "bullets",
                "tag": slide.get("tag", ""), "title": sarlavha, "points": bandlar}
        if rasm:
            yangi["image"] = rasm
        deck["slides"][idx] = yangi
        slide = yangi

    cid, mid = reja_slaydlar[idx]
    await ctx.bot.edit_message_text(
        chat_id=cid, message_id=mid, text=_slayd_karta_matni(idx + 1, slide),
        parse_mode=ParseMode.HTML, reply_markup=slayd_tahrir_tugmasi(idx + 1))
    ctx.user_data["holat"] = "reja"


class _CtxFor:
    """ctx.bot bir xil, lekin ctx.user_data BOSHQA foydalanuvchining lug'atiga
    almashtiriladi — admin to'lovni tasdiqlaganda talabaning shaxsiy holatiga
    yozish/o'qish uchun (mavjud yordamchi funksiyalarni — _bosqichga_ot,
    _kutish_boshla, _asosiyga_qayt va h.k. — o'zgartirmasdan qayta ishlatadi)."""
    def __init__(self, real_ctx, user_data):
        self.bot = real_ctx.bot
        self.application = real_ctx.application
        self.user_data = user_data


async def _pptx_render_va_yubor(ctx, chat_id):
    """ctx.user_data['deck'] allaqachon tayyor deb hisoblab, rasm+render ishlaydi
    va .pptx faylni yuboradi. To'lov tasdiqlangach (Click orqali) yoki to'lov
    talab qilinmasa (premium o'chirilgan YOKI bepul sinov, ikkalasida ham
    _taqdimotni_yarat shu funksiyani TO'G'RIDAN-TO'G'RI chaqiradi) ishlaydi."""
    deck = ctx.user_data.get("deck")
    if not deck:
        return
    bepul_sinov_edi = ctx.user_data.pop("bepul_sinov", False)
    await _reja_tozala(ctx)
    await _bosqichga_ot(ctx, chat_id, "⏳ Rasm va slaydlar tayyorlanmoqda...\n(1-2 daqiqa ketishi mumkin)")

    ctx.user_data["ishlanmoqda"] = True
    cid, mid = ctx.user_data["asosiy_msg"]
    animatsiya = await _kutish_boshla(ctx, cid, mid, "Rasm va slaydlar tayyorlanmoqda...\n(1-2 daqiqa ketishi mumkin)")
    yol = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.pptx")
    rasm_tmpdir = tempfile.mkdtemp(prefix="slayt_rasm_")
    try:
        # Rasm generatsiyasi va render sinxron (bloklovchi) — alohida oqimda ishlatamiz,
        # aks holda butun bot 1-2 daqiqaga muzlab qoladi va tugmalar ishlamay qoladi.
        await asyncio.to_thread(rasmlarni_tayyorla, deck, rasm_tmpdir)
        await asyncio.to_thread(render, deck, yol)
    except Exception:
        log.exception("render xato")
        await _kutish_toxtat(animatsiya)
        await _asosiyga_qayt(ctx, chat_id, "😔 Kechirasiz, taqdimotni yasashda xatolik bo'ldi. Qaytadan urinib ko'ring 👇")
        return
    finally:
        ctx.user_data["ishlanmoqda"] = False
        # Rasm papkasi endi kerak emas (pptx ichiga joylab bo'lindi) — o'chirilmasa
        # har bir taqdimotdan keyin diskda abadiy qolib ketaveradi.
        shutil.rmtree(rasm_tmpdir, ignore_errors=True)
    await _kutish_toxtat(animatsiya)

    nom = TEMPLATES.get(deck.get("template", "modern"), {}).get("nom", "")
    try:
        fnom = "".join(ch for ch in deck["title"] if ch.isalnum() or ch in " -_")[:40]
        with open(yol, "rb") as f:
            await ctx.bot.send_document(
                chat_id, document=InputFile(f),
                filename=f"{fnom or 'taqdimot'}.pptx",
                caption=f"👑 Tayyor: «{deck['title']}» — {nom}. Premium taqdimotingizdan yaxshi foydalaning! ✨")
    finally:
        if os.path.exists(yol):
            os.remove(yol)

    admin_store.xizmat_ishlatildi("slayt")
    if bepul_sinov_edi:
        admin_store.bepul_slayt_belgila(chat_id)
    await _asosiyga_qayt(ctx, chat_id, "🎉 Taqdimot tayyor!\nYana nimadir qilmoqchimisiz? 👇")


async def _ingliz_natija_yarat_va_yubor(ctx, chat_id):
    """ctx.user_data['pending_ingliz'] allaqachon tayyor deb hisoblab, tahlilni
    ishga tushiradi va natijani yuboradi. To'lov tasdiqlangach (admin orqali)
    chaqiriladi — mantiqi avvalgi hujjat_qabul/_ingliz_matn_qabul bilan bir xil,
    faqat AI chaqiruvi to'lov tasdiqlangunicha KECHIKTIRILGAN."""
    pending = ctx.user_data.get("pending_ingliz")
    if not pending:
        return
    daraja = pending.get("daraja", "grammar")
    kirish = pending.get("kirish_yol")
    nomi = pending.get("nomi") or "hujjat"
    matn_kirish = pending.get("matn")
    kutish_matni = "Tahlil qilinmoqda, biroz kuting..."

    await _bosqichga_ot(ctx, chat_id, f"⏳ {kutish_matni}")
    ctx.user_data["ishlanmoqda"] = True
    cid, mid = ctx.user_data["asosiy_msg"]
    animatsiya = await _kutish_boshla(ctx, cid, mid, kutish_matni)

    chiqish = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_natija.docx")
    oddiy_natija = None
    oddiy_majburiy_matn = False
    hisobot = None
    try:
        if matn_kirish is not None:
            if daraja == "ielts":
                oddiy_natija = await asyncio.to_thread(ingliz_ielts, matn_kirish)
                oddiy_majburiy_matn = True
            elif daraja == "grammar":
                oddiy_natija = await asyncio.to_thread(ingliz_grammar, matn_kirish)
            else:
                oddiy_natija = await asyncio.to_thread(ingliz_ravon, matn_kirish)
        else:
            if daraja == "ielts":
                matn = await asyncio.to_thread(docx_matnini_ol, kirish)
                if not matn.strip():
                    raise ValueError("hujjatdan matn topilmadi")
                oddiy_natija = await asyncio.to_thread(ingliz_ielts, matn)
                oddiy_majburiy_matn = True
            elif daraja == "grammar":
                _, ozgarishlar, jami = await asyncio.to_thread(docx_grammar, kirish, chiqish)
                hisobot = _hisobot_matni(ozgarishlar, jami, "Grammatika")
            else:
                _, ozgarishlar, jami = await asyncio.to_thread(docx_ravon, kirish, chiqish)
                hisobot = _hisobot_matni(ozgarishlar, jami, "Ravon (ingliz)")
    except Exception:
        log.exception("ingliz to'lovdan keyingi tahlil xato")
        await _kutish_toxtat(animatsiya)
        await _asosiyga_qayt(ctx, chat_id, "😔 Kechirasiz, xatolik bo'ldi. Qaytadan urinib ko'ring 👇")
        return
    finally:
        ctx.user_data["ishlanmoqda"] = False
        ctx.user_data.pop("pending_ingliz", None)
        if kirish and os.path.exists(kirish):
            os.remove(kirish)
    await _kutish_toxtat(animatsiya)

    admin_store.xizmat_ishlatildi("ingliz")

    if oddiy_natija is not None:
        # IELTS natijasi HAR DOIM matn — fayl hech qachon yuborilmaydi
        await _natijani_yubor(ctx, chat_id, oddiy_natija, majburiy_matn=oddiy_majburiy_matn,
                              fayl_nomi="ingliz_natija")
        return

    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    await ctx.bot.send_message(chat_id, hisobot, parse_mode=ParseMode.HTML)
    try:
        fnom = os.path.splitext(nomi)[0] or "hujjat"
        with open(chiqish, "rb") as f:
            await ctx.bot.send_document(
                chat_id, document=InputFile(f), filename=f"{fnom}_natija.docx",
                caption="✅ Tayyor (format saqlangan).")
    finally:
        if os.path.exists(chiqish):
            os.remove(chiqish)

    await _asosiyga_qayt(ctx, chat_id, "🎉 Tayyor!\nYana nimadir qilmoqchimisiz? 👇")


async def _umumiy_natija_yarat_va_yubor(ctx, chat_id):
    """Matn tuzatish / Davom ettirish / Konspekt qilish / Ilmiy tarjima uchun
    UMUMIY finalize — ctx.user_data['mode'] orqali qaysi xizmat ekanini va
    ctx.user_data['pending_umumiy'] dan kirish ma'lumotini oladi. Boshqa
    parametrlar (daraja, davom_soz, tarjima_til) allaqachon ctx.user_data'da
    turadi (_boshiga_qaytar chaqirilmaguncha o'chmaydi). To'lov tasdiqlangach
    (admin orqali) yoki to'lov talab qilinmasa bevosita chaqiriladi."""
    mode = ctx.user_data.get("mode")
    pending = ctx.user_data.get("pending_umumiy")
    if not pending:
        return
    kirish = pending.get("kirish_yol")
    nomi = pending.get("nomi") or "hujjat"
    matn_kirish = pending.get("matn")

    kutish_matni = {
        "tuzat": "Hujjat tuzatilmoqda, biroz kuting...",
        "davom": "Matn davom ettirilmoqda, biroz kuting...",
        "konspekt": "Konspekt tuzilmoqda, biroz kuting...",
        "tarjima": "Tarjima qilinmoqda, biroz kuting...",
    }.get(mode, "Ishlanmoqda, biroz kuting...")

    await _bosqichga_ot(ctx, chat_id, f"⏳ {kutish_matni}")
    ctx.user_data["ishlanmoqda"] = True
    cid, mid = ctx.user_data["asosiy_msg"]
    animatsiya = await _kutish_boshla(ctx, cid, mid, kutish_matni)

    chiqish = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_natija.docx")
    oddiy_natija = None
    hisobot = None
    try:
        if matn_kirish is not None:
            # Faqat konspekt/tarjima matn (fayl emas) sifatida kelishi mumkin
            if mode == "konspekt":
                oddiy_natija = await asyncio.to_thread(konspekt_qil, matn_kirish)
            else:  # "tarjima"
                til = ctx.user_data.get("tarjima_til", "uz")
                oddiy_natija = await asyncio.to_thread(tarjima, matn_kirish, til)
        elif mode == "tuzat":
            daraja = ctx.user_data.get("daraja", "imlo")
            _, ozgarishlar, jami = await asyncio.to_thread(docx_ni_tuzat, kirish, chiqish, daraja)
            hisobot = _hisobot_matni(ozgarishlar, jami, DARAJA_NOMI.get(daraja, daraja))
        elif mode == "davom":
            soz_soni = ctx.user_data.get("davom_soz")
            _, asl_soz, davom_soz = await asyncio.to_thread(davom_ettir, kirish, chiqish, soz_soni)
            hisobot = _davom_hisobot_matni(asl_soz, davom_soz)
        elif mode == "konspekt":
            matn = await asyncio.to_thread(konspekt_fayldan_matn_ol, kirish)
            oddiy_natija = await asyncio.to_thread(konspekt_qil, matn)
        else:  # "tarjima"
            til = ctx.user_data.get("tarjima_til", "uz")
            _, ozgarishlar, jami = await asyncio.to_thread(docx_tarjima, kirish, chiqish, til)
            hisobot = _hisobot_matni(ozgarishlar, jami, TARJIMA_TIL_NOMI.get(til, til),
                                     sarlavha="Tarjima hisoboti")
    except ValueError as e:
        log.warning("umumiy to'lovdan keyingi ishlov xato: %s", e)
        await _kutish_toxtat(animatsiya)
        await _asosiyga_qayt(ctx, chat_id, f"😔 Kechirasiz, {e}. Qaytadan urinib ko'ring.")
        return
    except Exception:
        log.exception("umumiy to'lovdan keyingi ishlov xato")
        await _kutish_toxtat(animatsiya)
        await _asosiyga_qayt(ctx, chat_id, "😔 Kechirasiz, xatolik bo'ldi. Qaytadan urinib ko'ring 👇")
        return
    finally:
        ctx.user_data["ishlanmoqda"] = False
        ctx.user_data.pop("pending_umumiy", None)
        if kirish and os.path.exists(kirish):
            os.remove(kirish)
    await _kutish_toxtat(animatsiya)
    admin_store.xizmat_ishlatildi(mode)

    if oddiy_natija is not None:
        await _natijani_yubor(ctx, chat_id, oddiy_natija, fayl_nomi=mode)
        return

    eski = ctx.user_data.pop("asosiy_msg", None)
    if eski:
        try:
            await ctx.bot.delete_message(chat_id=eski[0], message_id=eski[1])
        except Exception:
            pass
    await ctx.bot.send_message(chat_id, hisobot, parse_mode=ParseMode.HTML)
    try:
        fnom = os.path.splitext(nomi)[0] or "hujjat"
        with open(chiqish, "rb") as f:
            await ctx.bot.send_document(
                chat_id, document=InputFile(f), filename=f"{fnom}_natija.docx",
                caption="✅ Tayyor (format saqlangan).")
    finally:
        if os.path.exists(chiqish):
            os.remove(chiqish)

    await _asosiyga_qayt(ctx, chat_id, "🎉 Tayyor!\nYana nimadir qilmoqchimisiz? 👇")


# xizmat -> "bu xizmatning kutayotgan ishi tayyormi" va "uni bajaruvchi funksiya"
_TOLOV_BOR_ISH = {"slayt": lambda ud: ud.get("deck"),
                  "ingliz": lambda ud: ud.get("pending_ingliz"),
                  "tuzat": lambda ud: ud.get("pending_umumiy"),
                  "davom": lambda ud: ud.get("pending_umumiy"),
                  "konspekt": lambda ud: ud.get("pending_umumiy"),
                  "tarjima": lambda ud: ud.get("pending_umumiy")}
_TOLOV_BAJARUVCHI = {"slayt": _pptx_render_va_yubor,
                     "ingliz": _ingliz_natija_yarat_va_yubor,
                     "tuzat": _umumiy_natija_yarat_va_yubor,
                     "davom": _umumiy_natija_yarat_va_yubor,
                     "konspekt": _umumiy_natija_yarat_va_yubor,
                     "tarjima": _umumiy_natija_yarat_va_yubor}

TOLOV_MUDDATI_SONIYA = 5 * 60   # 5 daqiqa — shundan keyin to'lov (qilinmagan bo'lsa) avtomatik bekor bo'ladi


def _tolov_matni(ctx):
    summa = ctx.user_data.get("tolov_summa")
    daqiqa = TOLOV_MUDDATI_SONIYA // 60
    return (
        "📄 <b>To'lov ma'lumotlari</b>\n\n"
        f"💵 To'lanishi kerak: <b>{_som(summa)} so'm</b>\n\n"
        f"⏱ To'lov muddati: <b>{daqiqa} daqiqa</b>\n\n"
        "👇 Pastdagi «💳 Click orqali to'lash» tugmasini bosib to'lovni yakunlang.\n"
        "To'lov tasdiqlangach, xizmat AVTOMATIK boshlanadi — hech narsa yuborish shart emas."
    )


async def _tolov_muddat_tugadi(ctx: ContextTypes.DEFAULT_TYPE):
    """JobQueue orqali TOLOV_MUDDATI_SONIYA dan keyin chaqiriladi. Talaba hali
    ham to'lov QILMAGAN bo'lsa (holat hamon 'tolov_kutilmoqda') va bu ANIQ shu
    to'lov bo'lsa (tolov_id mos kelsa — talaba bekor qilib, yangi to'lov
    boshlagan bo'lishi mumkin), avtomatik bekor qiladi."""
    tolov_id = ctx.job.data
    ud = ctx.user_data
    if ud.get("tolov_id") != tolov_id or ud.get("holat") != "tolov_kutilmoqda":
        return
    chat_id = ctx.job.chat_id
    await _tolov_amal_tozala(ctx)
    await _asosiyga_qayt(
        ctx, chat_id,
        "⏰ <b>To'lov muddati tugadi</b> (5 daqiqa ichida to'lov qabul qilinmadi).\n"
        "Agar hali ham xohlasangiz, xizmatni qaytadan boshlang 👇")


async def _tolov_sora(ctx, chat_id):
    """Joriy xizmat (ctx.user_data['mode']) uchun to'lov TALAB qilinadimi
    tekshiradi (admin panel orqali premium O'CHIRILGAN bo'lsa — to'lovsiz
    DARHOL bajaradi). Yoqilgan bo'lsa — reja/slayd xabarlarini tozalab, Click
    orqali to'lov havolasini yaratadi va DARHOL to'lov ekraniga o'tkazadi (bu —
    istalgan pullik xizmat: slayt, ingliz, ... uchun UMUMIY). Click COMPLETE
    webhook kelgach (bot/click_webhook.py) xizmat AVTOMATIK topshiriladi —
    admin ishtirokisiz. Asosiy tugmalar o'rniga FAQAT Bekor qilish ko'rsatiladi,
    toki foydalanuvchi tasodifan boshqa xizmatga o'tib, to'lov jarayonini uzib
    qo'ymasin."""
    mode = ctx.user_data.get("mode")
    if not admin_store.premium_yoqilganmi(mode):
        bajaruvchi = _TOLOV_BAJARUVCHI.get(mode)
        if bajaruvchi:
            await bajaruvchi(ctx, chat_id)
        return
    if not config.click_sozlangan():
        log.warning("Click sozlanmagan (.env bo'sh) — pullik xizmat ishlamaydi (mode=%s)", mode)
        await _asosiyga_qayt(
            ctx, chat_id,
            "😔 Kechirasiz, hozircha to'lov tizimi sozlanmagan. Administratorga murojaat qiling.")
        return
    await _reja_tozala(ctx)
    tolov_id = uuid.uuid4().hex[:10]
    ctx.user_data["tolov_id"] = tolov_id
    summa = admin_store.narx_ol(mode, config.TOLOV_SUM)
    ctx.user_data["tolov_summa"] = summa
    click_order_id = click_pay.yangi_buyurtma(chat_id, mode, summa)
    ctx.user_data["click_order_id"] = click_order_id
    click_url = click_pay.pay_url(click_order_id, summa)
    await _bosqichga_ot(ctx, chat_id, _tolov_matni(ctx), bekor_reply_klaviatura())
    amal = await ctx.bot.send_message(
        chat_id, "👇 To'lovni yakunlash uchun bosing", parse_mode=ParseMode.HTML,
        reply_markup=tolov_amal_klaviaturasi(click_url))
    ctx.user_data["tolov_amal_msg"] = (amal.chat_id, amal.message_id)
    ctx.user_data["holat"] = "tolov_kutilmoqda"
    if getattr(ctx, "application", None) and ctx.application.job_queue:
        ctx.application.job_queue.run_once(
            _tolov_muddat_tugadi, when=TOLOV_MUDDATI_SONIYA, data=tolov_id,
            chat_id=chat_id, user_id=chat_id, name=f"tolov_muddat_{chat_id}_{tolov_id}")


async def _taqdimotni_yarat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """✅ Yaratish (reja bosqichidagi doimiy tugma) bosilganda — DARHOL to'lovga
    (Click) o'tkazadi; to'lov tasdiqlangach fayl avtomatik tayyorlanadi.
    ISTISNO: 3 varoqli taqdimot va bu foydalanuvchi hali BEPUL sinovdan
    foydalanmagan bo'lsa — to'lovsiz, DARHOL yaratiladi (faqat bir marta)."""
    await _ochir(update.message)
    chat_id = update.effective_chat.id
    if ctx.user_data.get("ishlanmoqda"):
        await ctx.bot.send_message(chat_id, "⏳ Iltimos kuting, taqdimot allaqachon tayyorlanmoqda...")
        return
    deck = ctx.user_data.get("deck")
    if not deck:
        await _asosiyga_qayt(ctx, chat_id, "Avval yangi mavzu boshlang 👇")
        return
    if (ctx.user_data.get("jami") == VARAQ_BEPUL_N
            and admin_store.premium_yoqilganmi("slayt")
            and not admin_store.bepul_slayt_ishlatganmi(chat_id)):
        ctx.user_data["bepul_sinov"] = True
        await _pptx_render_va_yubor(ctx, chat_id)
        return
    await _tolov_sora(ctx, chat_id)


def _tolov_kutilayotgan_ish_bormi(ud):
    """Joriy mode uchun to'lov kutayotgan haqiqiy ish bormi (deck/pending_ingliz)."""
    tekshir = _TOLOV_BOR_ISH.get(ud.get("mode"))
    return bool(tekshir(ud)) if tekshir else False


async def rasm_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """RASM yuborilganda ishga tushadi. To'lov ENDI avtomatik (Click) — talabadan
    chek/skrinshot so'ralmaydi, shu sabab bu FAQAT admin «📢 Umumiy xabar»
    kutilayotganda rasm yuborsa — admin_rasm_qabul ga (bot/admin.py)
    yo'naltiriladi. Boshqa hollarda e'tiborsiz qoldiriladi."""
    tahrir = ctx.user_data.get("admin_tahrir")
    if (tahrir and tahrir.get("turi") == "umumiy_xabar"
            and config.ADMIN_ID and update.effective_user.id == config.ADMIN_ID):
        await admin_rasm_qabul(update, ctx)




# ---------- Matn tuzatish (.docx) / Davom ettirish (.docx | .pdf) ----------

def _davom_hisobot_matni(asl_soz, davom_soz):
    """'Davom ettirish' natijasi haqida qisqa hisobot (fayldan OLDIN yuboriladi)."""
    return (
        "📊 <b>Davom ettirish hisoboti</b>\n\n"
        f"📄 Asl matningiz: <b>{asl_soz}</b> so'z\n"
        f"🧩 Qo'shilgan davomi: <b>{davom_soz}</b> so'z\n"
        f"📈 Yakuniy hujjat: <b>{asl_soz + davom_soz}</b> so'z\n\n"
        "👇 To'liq hujjat quyida:"
    )


_FAYL_KUTILAYOTGAN_HOLAT = {"tuzat": "tuzat_fayl", "davom": "tuzat_fayl",
                           "konspekt": "konspekt_kutish",
                           "ingliz": "ingliz_kutish", "tarjima": "tarjima_kutish"}


async def hujjat_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi fayl yuborganda ishga tushadi (mos rejim + fayl kutilayotgan
    bosqichda). mode=='davom'/'konspekt' bo'lsa .docx/.pdf, qolganlarida faqat
    .docx. To'lov (Click) kutilayotgan bo'lsa — fayl qabul qilinmaydi, to'lovni
    yakunlash haqida eslatiladi.

    Faylni yuklab olib, tegishli pending lug'atga (mode='ingliz' bo'lsa
    pending_ingliz, aks holda pending_umumiy) joylaydi va _tolov_sora ga
    topshiradi — u ICHKARIDA premium yoqiq/o'chiqligini tekshiradi: yoqiq
    bo'lsa to'lov so'raydi, o'chiq bo'lsa (bepul) DARHOL ishlaydi. Haqiqiy
    AI ishlovi endi bu yerda YO'Q — _ingliz_natija_yarat_va_yubor /
    _umumiy_natija_yarat_va_yubor da (to'lov tasdiqlangach yoki bevosita)."""
    if ctx.user_data.get("holat") == "tolov_kutilmoqda" and _tolov_kutilayotgan_ish_bormi(ctx.user_data):
        await update.message.reply_text(
            "💳 To'lov hali amalga oshirilmagan. Iltimos, yuqoridagi «💳 Click orqali to'lash» "
            "tugmasini bosib to'lovni yakunlang — tasdiqlangach xizmat avtomatik boshlanadi.")
        return
    mode = ctx.user_data.get("mode")
    kutilgan_holat = _FAYL_KUTILAYOTGAN_HOLAT.get(mode)
    if kutilgan_holat is None or ctx.user_data.get("holat") != kutilgan_holat:
        await update.message.reply_text("Hozircha fayl kutilmayapti. Boshlash uchun /start bosing.")
        return
    if ctx.user_data.get("ishlanmoqda"):
        await update.message.reply_text("⏳ Iltimos kuting, oldingi hujjat hali tayyorlanmoqda...")
        return

    hujjat = update.message.document
    nomi = hujjat.file_name or ""
    kengaytma = os.path.splitext(nomi.lower())[1]
    ruxsat_etilgan = (".docx", ".pdf") if mode in ("davom", "konspekt") else (".docx",)
    if kengaytma not in ruxsat_etilgan:
        matn = " yoki ".join(f"<b>{k}</b>" for k in ruxsat_etilgan)
        await update.message.reply_text(f"📎 Iltimos, faqat {matn} fayl yuboring.", parse_mode=ParseMode.HTML)
        return

    chat_id = update.effective_chat.id
    await _ochir(update.message)

    kirish = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_kirish{kengaytma}")
    try:
        tfile = await hujjat.get_file()
        await tfile.download_to_drive(kirish)
    except Exception:
        log.exception("fayl yuklab olishda xato")
        await update.message.reply_text("😔 Kechirasiz, faylni yuklab bo'lmadi. Qaytadan urinib ko'ring.")
        return

    if mode == "ingliz":
        daraja = ctx.user_data.get("ingliz_daraja", "grammar")
        ctx.user_data["pending_ingliz"] = {"daraja": daraja, "kirish_yol": kirish,
                                           "nomi": nomi, "matn": None}
    else:
        ctx.user_data["pending_umumiy"] = {"kirish_yol": kirish, "nomi": nomi, "matn": None}
    await _tolov_sora(ctx, chat_id)
