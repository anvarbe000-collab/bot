"""
bot/admin.py — Telegram ICHIDAGI admin panel. FAQAT config.ADMIN_ID uchun
ishlaydi (boshqa hech kim buni ko'rmaydi ham, ishlata olmaydi ham).

/admin buyrug'i bilan ochiladi, keyingisi FAQAT inline tugmalar orqali
boshqariladi. Matn kiritish kerak bo'lgan joylarda (narx, API kalit va
h.k.) ctx.user_data["admin_tahrir"] orqali "keyingi xabarni kutyapman" holati
saqlanadi — buni bot/handlers.py:matn_router O'ZINING ENG BOSHIDA tekshiradi va
shu yerga (admin_matn_qabul) yo'naltiradi, aks holda oddiy foydalanuvchilar
oqimiga umuman ta'sir qilmaydi.

Bu yerda o'zgartirilgan HAR NARSA (narx, premium yoqiq/o'chiq, AI
sozlamalari) admin_store.py orqali data/store.json ga YOZILADI va KEYINGI
so'rovda DARHOL amal qiladi — botni qayta ishga tushirish SHART EMAS.
"""

import html
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import time

import config
import admin_store
import promo_store

log = logging.getLogger("admin")


def _esc(matn):
    return html.escape(str(matn or ""))


def _som(n):
    return f"{n:,}".replace(",", " ")


def _mask(qiymat):
    """API kalitni ekranda TO'LIQ ko'rsatmaydi — faqat boshi/oxiri.
    (standart holat matni HTML sifatida, kalit qismi esa xavfsizlashtirilib qaytariladi)."""
    if not qiymat:
        return "<i>(standart — .env dan)</i>"
    if len(qiymat) <= 10:
        return _esc("•" * len(qiymat))
    return _esc(f"{qiymat[:6]}···{qiymat[-4:]}")


def _admin_bolsa(update: Update) -> bool:
    return bool(config.ADMIN_ID) and update.effective_user.id == config.ADMIN_ID


# ---------- 1) Asosiy menu ----------

def _asosiy_klaviatura():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Hisobot", callback_data="adm:hisobot")],
        [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="adm:sozlash")],
        [InlineKeyboardButton("📢 Umumiy xabar", callback_data="adm:xabar")],
        [InlineKeyboardButton("🔗 Targ'ibot linklari", callback_data="adm:promo")],
        [InlineKeyboardButton("✖️ Yopish", callback_data="adm:yopish")],
    ])


def _asosiy_matni():
    """Foydalanuvchilar soni SHU YERDA — admin panelni HAR ochganda darhol
    ko'rinib turishi uchun (batafsil hisobot uchun 📊 Hisobot bosish shart emas)."""
    soni = len(admin_store.hisobot_ol()["tashrif_id_lar"])
    return f"🛡 <b>Admin panel</b>\n\n👥 Jami foydalanuvchilar: <b>{soni}</b>\n\nXush kelibsiz, admin!"


async def admin_komandasi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/admin buyrug'i — FAQAT ADMIN_ID uchun ishlaydi, boshqalarga jim
    o'tkazib yuboriladi (adminning mavjudligini oshkor qilmaslik uchun)."""
    if not _admin_bolsa(update):
        return
    ctx.user_data.pop("admin_tahrir", None)
    await update.message.reply_text(
        _asosiy_matni(), parse_mode=ParseMode.HTML, reply_markup=_asosiy_klaviatura())


async def _ekran_yangila(q, matn, klaviatura):
    try:
        await q.edit_message_text(matn, parse_mode=ParseMode.HTML, reply_markup=klaviatura)
    except Exception:
        pass


# ---------- 2) Hisobot ----------

def _hisobot_matni():
    st = admin_store.hisobot_ol()
    qatorlar = ["📊 <b>Umumiy hisobot</b>", "━━━━━━━━━━━━━━━", "",
               f"👥 Jami tashrif buyurganlar: <b>{len(st['tashrif_id_lar'])}</b>", ""]
    jami_tolov = 0
    for xizmat, nom in admin_store.XIZMATLAR.items():
        yoz = st["xizmatlar"].get(xizmat, {})
        ishlatilgan = yoz.get("ishlatilgan", 0)
        agar = "marta bosilgan" if xizmat == "test_link" else "marta ishlatilgan"
        qator = f"{nom}: <b>{ishlatilgan}</b> {agar}"
        if xizmat in admin_store.PULLIK_XIZMATLAR:
            soni = yoz.get("tolov_soni", 0)
            summa = yoz.get("tolov_summasi", 0)
            jami_tolov += summa
            qator += f"\n   💰 {soni} ta to'lov — <b>{_som(summa)}</b> so'm"
        qatorlar.append(qator)
    qatorlar += ["", "━━━━━━━━━━━━━━━", f"💵 Jami to'lov: <b>{_som(jami_tolov)}</b> so'm"]
    return "\n".join(qatorlar)


async def _hisobot_korsat(q):
    klav = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")]])
    await _ekran_yangila(q, _hisobot_matni(), klav)


# ---------- 3) Sozlamalar — asosiy ----------

def _sozlash_klaviatura():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Narxlar", callback_data="adm:narxlar"),
         InlineKeyboardButton("🔓 Premium yoqish/o'chirish", callback_data="adm:premium")],
        [InlineKeyboardButton("🤖 AI sozlamalari", callback_data="adm:ai"),
         InlineKeyboardButton("🖼 Rasm sozlamalari", callback_data="adm:rasm")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")],
    ])


async def _sozlash_korsat(q):
    await _ekran_yangila(q, "⚙️ <b>Sozlamalar</b>\n\nKerakli bo'limni tanlang 👇", _sozlash_klaviatura())


# ---------- 4) Narxlar ----------

def _narxlar_matni():
    qatorlar = ["💰 <b>Narxlar</b>", ""]
    for xizmat in admin_store.PULLIK_XIZMATLAR:
        nom = admin_store.XIZMATLAR[xizmat]
        narx = admin_store.narx_ol(xizmat, config.TOLOV_SUM)
        qatorlar.append(f"{nom}: <b>{_som(narx)} so'm</b>")
    qatorlar.append("\nNarxni o'zgartirish uchun xizmatni tanlang 👇")
    return "\n".join(qatorlar)


def _narxlar_klaviatura():
    tugmalar = [[InlineKeyboardButton(f"✏️ {admin_store.XIZMATLAR[x]}", callback_data=f"adm:narx:{x}")]
               for x in admin_store.PULLIK_XIZMATLAR]
    tugmalar.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:sozlash")])
    return InlineKeyboardMarkup(tugmalar)


async def _narxlar_korsat(q):
    await _ekran_yangila(q, _narxlar_matni(), _narxlar_klaviatura())


# ---------- 5) Premium yoqish/o'chirish ----------

def _premium_klaviatura():
    tugmalar = []
    for x in admin_store.PULLIK_XIZMATLAR:
        yoqiq = admin_store.premium_yoqilganmi(x)
        belgi = "✅ Yoqilgan" if yoqiq else "❌ O'chirilgan"
        tugmalar.append([InlineKeyboardButton(
            f"{admin_store.XIZMATLAR[x]}: {belgi}", callback_data=f"adm:premium_t:{x}")])
    tugmalar.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:sozlash")])
    return InlineKeyboardMarkup(tugmalar)


async def _premium_korsat(q):
    matn = ("🔓 <b>Premium yoqish/o'chirish</b>\n\n"
           "✅ Yoqilgan — xizmat PULLIK, to'lov admin tomonidan tasdiqlanadi.\n"
           "❌ O'chirilgan — xizmat BEPUL, darhol (to'lovsiz) ishlaydi.\n\n"
           "O'zgartirish uchun bosing 👇")
    await _ekran_yangila(q, matn, _premium_klaviatura())


# ---------- 7) AI sozlamalari ----------

def _ai_modullar_klaviatura():
    tugmalar = [[InlineKeyboardButton(nom, callback_data=f"adm:ai_m:{modul}")]
               for modul, nom in admin_store.AI_MODULLAR.items()]
    tugmalar.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:sozlash")])
    return InlineKeyboardMarkup(tugmalar)


async def _ai_modullar_korsat(q):
    matn = ("🤖 <b>AI sozlamalari</b>\n\n"
           "Har bo'lim uchun ALOHIDA Gemini (yoki boshqa OpenAI-mos) sozlama. "
           "O'zgartirilsa BOTNI QAYTA ISHGA TUSHIRISH SHART EMAS — darhol amal qiladi.\n\n"
           "Bo'limni tanlang 👇")
    await _ekran_yangila(q, matn, _ai_modullar_klaviatura())


_AI_STANDART = {
    "slayt": (config.AI_BASE_URL, config.AI_API_KEY, config.AI_MODEL),
    "tuzat": (config.TUZAT_BASE_URL, config.TUZAT_KEY, config.TUZAT_MODEL),
    "til": (config.TIL_BASE_URL, config.TIL_KEY, config.TIL_MODEL),
    "konspekt": (config.KONSPEKT_BASE_URL, config.KONSPEKT_KEY, config.KONSPEKT_MODEL),
}


def _ai_modul_matni(modul):
    standart_base, standart_key, standart_model = _AI_STANDART[modul]
    base, key, model = admin_store.ai_sozlama_ol(modul, standart_base, standart_key, standart_model)
    nom = admin_store.AI_MODULLAR[modul]
    return (
        f"{nom} — AI sozlamalari\n\n"
        f"Base URL: <code>{_esc(base)}</code>\n"
        f"Kalit: <code>{_mask(key)}</code>\n"
        f"Model: <code>{_esc(model)}</code>"
    )


def _ai_modul_klaviatura(modul):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Base URL", callback_data=f"adm:ai_f:{modul}:base_url"),
         InlineKeyboardButton("✏️ Kalit", callback_data=f"adm:ai_f:{modul}:key"),
         InlineKeyboardButton("✏️ Model", callback_data=f"adm:ai_f:{modul}:model")],
        [InlineKeyboardButton("♻️ Hammasini standartga qaytarish", callback_data=f"adm:ai_reset:{modul}")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="adm:ai")],
    ])


async def _ai_modul_korsat(q, modul):
    if modul not in admin_store.AI_MODULLAR:
        return
    await _ekran_yangila(q, _ai_modul_matni(modul), _ai_modul_klaviatura(modul))


# ---------- 8) Rasm sozlamalari ----------

_RASM_PROVIDERLAR = {"pollinations": "Pollinations (bepul, kalitsiz)",
                     "gemini": "Gemini Nano Banana (PULLIK, billing kerak)",
                     "together": "Together AI / Flux (arzon)"}


def _rasm_matni():
    ov = admin_store.rasm_sozlama_ol()
    provider = ov.get("provider") or config.IMG_PROVIDER
    qatorlar = ["🖼 <b>Rasm generatsiyasi sozlamalari</b>", "",
               f"Joriy provayder: <b>{_esc(provider)}</b>", ""]
    if provider == "gemini":
        qatorlar.append(f"Model: <code>{_esc(ov.get('model_g') or config.IMG_MODEL_G)}</code>")
        qatorlar.append(f"Kalit: <code>{_mask(ov.get('key') or config.IMG_KEY)}</code>")
    elif provider == "together":
        qatorlar.append(f"Model: <code>{_esc(ov.get('together_model') or config.IMG_TOGETHER_MODEL)}</code>")
        qatorlar.append(f"Kalit: <code>{_mask(ov.get('together_key') or config.IMG_TOGETHER_KEY)}</code>")
    else:
        qatorlar.append(f"Model: <code>{_esc(ov.get('model') or config.IMG_MODEL)}</code>")
        qatorlar.append(f"Base: <code>{_esc(ov.get('base') or config.IMG_BASE)}</code>")
    return "\n".join(qatorlar)


def _rasm_klaviatura():
    ov = admin_store.rasm_sozlama_ol()
    provider = ov.get("provider") or config.IMG_PROVIDER
    if provider == "gemini":
        maydon_tugmalari = [InlineKeyboardButton("✏️ Model", callback_data="adm:rasm_f:model_g"),
                            InlineKeyboardButton("✏️ Kalit", callback_data="adm:rasm_f:key")]
    elif provider == "together":
        maydon_tugmalari = [InlineKeyboardButton("✏️ Model", callback_data="adm:rasm_f:together_model"),
                            InlineKeyboardButton("✏️ Kalit", callback_data="adm:rasm_f:together_key")]
    else:
        maydon_tugmalari = [InlineKeyboardButton("✏️ Model", callback_data="adm:rasm_f:model"),
                            InlineKeyboardButton("✏️ Base URL", callback_data="adm:rasm_f:base")]
    return InlineKeyboardMarkup([
        maydon_tugmalari,
        [InlineKeyboardButton("🔄 Provayderni almashtirish", callback_data="adm:rasm_prov")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="adm:sozlash")],
    ])


async def _rasm_korsat(q):
    await _ekran_yangila(q, _rasm_matni(), _rasm_klaviatura())


def _rasm_provider_klaviatura():
    tugmalar = [[InlineKeyboardButton(nom, callback_data=f"adm:rasm_prov_t:{kalit}")]
               for kalit, nom in _RASM_PROVIDERLAR.items()]
    tugmalar.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:rasm")])
    return InlineKeyboardMarkup(tugmalar)


async def _rasm_provider_korsat(q):
    await _ekran_yangila(q, "🔄 <b>Qaysi provayderni ishlatamiz?</b>", _rasm_provider_klaviatura())


# ---------- 9) Umumiy xabar (broadcast) ----------

def _xabar_tasdiq_klaviaturasi():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yuborish", callback_data="adm:xabar_tasdiq")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="adm:xabar_bekor")],
    ])


async def _xabar_boshla(q, ctx):
    """📢 Umumiy xabar bosilganda — matn yoki rasm kutish holatiga o'tadi."""
    ctx.user_data["admin_tahrir"] = {"turi": "umumiy_xabar"}
    soni = len(admin_store.hisobot_ol()["tashrif_id_lar"])
    await _ekran_yangila(
        q,
        "📢 <b>Umumiy xabar yuborish</b>\n\n"
        f"Hozircha <b>{soni}</b> ta foydalanuvchi ro'yxatda.\n\n"
        "✍️ Yubormoqchi bo'lgan xabaringizni shu yerga yozing (matn) yoki "
        "rasm yuboring (rasmga izoh/caption ham qo'shishingiz mumkin).",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bekor qilish", callback_data="adm:menu")]]))


async def _xabar_yubor_hammaga(ctx, matn=None, photo_file_id=None, caption=None):
    """Umumiy xabarni tashrif_id_lar dagi BARCHA foydalanuvchilarga, BITTA-
    BITTA yuboradi. Kimdir botni bloklagan/o'chirgan bo'lsa, o'sha o'tkazib
    yuboriladi — qolganlarga yuborish TO'XTAMAYDI. Qaytaradi: (muvaffaqiyatli, xato).

    MUHIM: matn/caption HAR DOIM oddiy matn sifatida (parse_mode'siz) yuboriladi
    — admin yozgan matnda "<", ">", "&" kabi belgilar bo'lsa, HTML sifatida
    yuborilsa Telegram butun xabarni rad etib, HAMMA foydalanuvchiga yuborish
    barbod bo'lardi."""
    idlar = admin_store.hisobot_ol()["tashrif_id_lar"]
    muvaffaqiyatli, xato = 0, 0
    for uid in idlar:
        try:
            if photo_file_id:
                await ctx.bot.send_photo(uid, photo=photo_file_id, caption=caption or None)
            else:
                await ctx.bot.send_message(uid, matn)
            muvaffaqiyatli += 1
        except Exception:
            xato += 1
        await asyncio.sleep(0.05)   # Telegramning tezlik chegarasiga tegib ketmaslik uchun
    return muvaffaqiyatli, xato


async def admin_rasm_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin «Umumiy xabar» kutilayotganda RASM yuborganda ishga tushadi
    (bot/handlers.py:rasm_qabul FAQAT shu holatda shu yerga yo'naltiradi)."""
    ctx.user_data.pop("admin_tahrir", None)
    photo = update.message.photo[-1]
    caption = update.message.caption or ""
    ctx.user_data["umumiy_xabar_draft"] = {"matn": None, "photo_file_id": photo.file_id, "caption": caption}
    soni = len(admin_store.hisobot_ol()["tashrif_id_lar"])
    izoh_bor = " (izoh bilan)" if caption else ""
    await update.message.reply_text(
        f"📢 Yuqoridagi rasm{izoh_bor} <b>{soni}</b> ta foydalanuvchiga yuboriladi. Davom etamizmi?",
        parse_mode=ParseMode.HTML, reply_markup=_xabar_tasdiq_klaviaturasi())


# ---------- 10) Targ'ibot (promo) linklari ----------

def _promo_link_url(ctx, kod):
    return f"https://t.me/{ctx.bot.username}?start={promo_store.PREFIKS}{kod}"


def _promo_royxat_matni():
    linklar = promo_store.linklar_royxati()
    qatorlar = ["🔗 <b>Targ'ibot linklari</b>", "",
               f"Har bir YANGI foydalanuvchi uchun <b>{_som(promo_store.PROMO_HAQ)} so'm</b> hisoblanadi."]
    if not linklar:
        qatorlar += ["", "Hozircha link yo'q — «➕ Yangi link» bosing."]
        return "\n".join(qatorlar)
    qatorlar.append("")
    jami = 0
    for kod, nom, faol, soni in linklar:
        summa = soni * promo_store.PROMO_HAQ
        jami += summa
        belgi = "🟢" if faol else "🔴"
        qatorlar.append(f"{belgi} <b>{_esc(nom)}</b> — 👥 {soni} ta · 💰 {_som(summa)} so'm")
    qatorlar += ["", f"💵 Jami hisoblangan: <b>{_som(jami)} so'm</b>"]
    return "\n".join(qatorlar)


def _promo_royxat_klaviatura():
    tugmalar = [[InlineKeyboardButton(f"{'🟢' if faol else '🔴'} {nom}", callback_data=f"adm:promo_k:{kod}")]
               for kod, nom, faol, _ in promo_store.linklar_royxati()]
    tugmalar.append([InlineKeyboardButton("➕ Yangi link", callback_data="adm:promo_yangi")])
    tugmalar.append([InlineKeyboardButton("◀️ Orqaga", callback_data="adm:menu")])
    return InlineKeyboardMarkup(tugmalar)


async def _promo_royxat_korsat(q):
    await _ekran_yangila(q, _promo_royxat_matni(), _promo_royxat_klaviatura())


def _promo_link_matni(ctx, kod):
    link = promo_store.link_ol(kod)
    if not link:
        return "⚠️ Link topilmadi."
    kelganlar = link["kelganlar"]
    soni = len(kelganlar)
    holat = "🟢 faol" if link["faol"] else "🔴 o'chirilgan (yangi kelganlar hisoblanmaydi)"
    qatorlar = [
        f"🔗 <b>{_esc(link['nom'])}</b> — {holat}", "",
        f"<code>{_promo_link_url(ctx, kod)}</code>", "",
        f"👥 Kelganlar: <b>{soni}</b> ta",
        f"💰 Hisoblangan: <b>{_som(soni * promo_store.PROMO_HAQ)} so'm</b> "
        f"({_som(promo_store.PROMO_HAQ)} × {soni})",
    ]
    if kelganlar:
        qatorlar += ["", "<b>Oxirgi kelganlar:</b>"]
        for i, k in enumerate(reversed(kelganlar[-30:]), 1):
            username = f" @{_esc(k['username'])}" if k.get("username") else ""
            vaqt = time.strftime("%d.%m %H:%M", time.localtime(k["vaqt"]))
            qatorlar.append(f"{i}. {_esc(k['ism']) or 'Noma’lum'}{username} — {vaqt}")
        if soni > 30:
            qatorlar.append(f"… va yana {soni - 30} ta")
    return "\n".join(qatorlar)


def _promo_link_klaviatura(kod):
    link = promo_store.link_ol(kod)
    faol = bool(link and link["faol"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 O'chirish" if faol else "🟢 Qayta yoqish", callback_data=f"adm:promo_t:{kod}")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="adm:promo")],
    ])


async def _promo_link_korsat(q, ctx, kod):
    await _ekran_yangila(q, _promo_link_matni(ctx, kod), _promo_link_klaviatura(kod))


# ---------- Matn kiritish talab qiluvchi tahrirlar ----------

_TAHRIR_SOROVLARI = {
    "narx": "✍️ <b>{nom}</b> uchun yangi narxni yuboring (so'm, faqat butun son):",
    "ai": "✍️ <b>{nom}</b> uchun yangi «{maydon_nom}» qiymatini yuboring:",
    "rasm": "✍️ Rasm sozlamasi uchun yangi «{maydon_nom}» qiymatini yuboring:",
}

_MAYDON_NOMI = {"base_url": "Base URL", "key": "Kalit", "model": "Model",
               "model_g": "Model", "together_key": "Kalit", "together_model": "Model", "base": "Base URL"}


async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin panelning BARCHA inline tugmalari shu yerdan o'tadi."""
    q = update.callback_query
    if not _admin_bolsa(update):
        await q.answer("Bu tugma faqat administrator uchun.", show_alert=True)
        return
    await q.answer()
    data = q.data[len("adm:"):]

    if data == "menu":
        ctx.user_data.pop("admin_tahrir", None)
        ctx.user_data.pop("umumiy_xabar_draft", None)
        await _ekran_yangila(q, _asosiy_matni(), _asosiy_klaviatura())
    elif data == "hisobot":
        await _hisobot_korsat(q)
    elif data == "sozlash":
        await _sozlash_korsat(q)
    elif data == "narxlar":
        await _narxlar_korsat(q)
    elif data == "premium":
        await _premium_korsat(q)
    elif data == "ai":
        await _ai_modullar_korsat(q)
    elif data == "rasm":
        await _rasm_korsat(q)
    elif data == "rasm_prov":
        await _rasm_provider_korsat(q)
    elif data == "promo":
        await _promo_royxat_korsat(q)
    elif data == "promo_yangi":
        ctx.user_data["admin_tahrir"] = {"turi": "promo_nom"}
        await ctx.bot.send_message(
            q.message.chat_id,
            "✍️ Targ'ibotchining <b>ismini</b> yuboring (faqat sizga ko'rinadi, masalan: «Ali»):",
            parse_mode=ParseMode.HTML)
    elif data.startswith("promo_k:"):
        await _promo_link_korsat(q, ctx, data.split(":", 1)[1])
    elif data.startswith("promo_t:"):
        kod = data.split(":", 1)[1]
        promo_store.faol_almashtir(kod)
        await _promo_link_korsat(q, ctx, kod)
    elif data == "xabar":
        await _xabar_boshla(q, ctx)
    elif data == "xabar_tasdiq":
        draft = ctx.user_data.pop("umumiy_xabar_draft", None)
        if not draft:
            await _ekran_yangila(q, "⚠️ Yuboriladigan xabar topilmadi (eskirgan bo'lishi mumkin).",
                                 _asosiy_klaviatura())
            return
        await _ekran_yangila(q, "⏳ Yuborilmoqda, biroz kuting...", None)
        muvaffaqiyatli, xato = await _xabar_yubor_hammaga(
            ctx, matn=draft.get("matn"), photo_file_id=draft.get("photo_file_id"),
            caption=draft.get("caption"))
        await ctx.bot.send_message(
            q.message.chat_id,
            f"✅ <b>Yuborish tugadi.</b>\n\n👥 Muvaffaqiyatli: <b>{muvaffaqiyatli}</b>\n"
            f"⚠️ Yetib bormadi (bloklagan/o'chirgan): <b>{xato}</b>",
            parse_mode=ParseMode.HTML, reply_markup=_asosiy_klaviatura())
    elif data == "xabar_bekor":
        ctx.user_data.pop("umumiy_xabar_draft", None)
        await _ekran_yangila(q, "❌ Umumiy xabar bekor qilindi.", _asosiy_klaviatura())
    elif data == "yopish":
        ctx.user_data.pop("admin_tahrir", None)
        ctx.user_data.pop("umumiy_xabar_draft", None)
        await _ekran_yangila(q, "🛡 Admin panel yopildi. Qayta ochish uchun /admin yuboring.", None)
    elif data.startswith("narx:"):
        xizmat = data.split(":", 1)[1]
        if xizmat not in admin_store.PULLIK_XIZMATLAR:
            return
        ctx.user_data["admin_tahrir"] = {"turi": "narx", "xizmat": xizmat}
        nom = admin_store.XIZMATLAR[xizmat]
        await ctx.bot.send_message(q.message.chat_id,
                                   _TAHRIR_SOROVLARI["narx"].format(nom=_esc(nom)),
                                   parse_mode=ParseMode.HTML)
    elif data.startswith("premium_t:"):
        xizmat = data.split(":", 1)[1]
        if xizmat not in admin_store.PULLIK_XIZMATLAR:
            return
        admin_store.premium_almashtir(xizmat)
        await _premium_korsat(q)
    elif data.startswith("ai_m:"):
        modul = data.split(":", 1)[1]
        await _ai_modul_korsat(q, modul)
    elif data.startswith("ai_f:"):
        _, modul, maydon = data.split(":", 2)
        if modul not in admin_store.AI_MODULLAR:
            return
        ctx.user_data["admin_tahrir"] = {"turi": "ai", "modul": modul, "maydon": maydon}
        nom = admin_store.AI_MODULLAR[modul]
        matn = _TAHRIR_SOROVLARI["ai"].format(nom=_esc(nom), maydon_nom=_MAYDON_NOMI.get(maydon, maydon))
        await ctx.bot.send_message(q.message.chat_id, matn, parse_mode=ParseMode.HTML)
    elif data.startswith("ai_reset:"):
        modul = data.split(":", 1)[1]
        if modul not in admin_store.AI_MODULLAR:
            return
        for maydon in ("base_url", "key", "model"):
            admin_store.ai_sozlama_belgila(modul, maydon, None)
        await _ai_modul_korsat(q, modul)
    elif data.startswith("rasm_f:"):
        maydon = data.split(":", 1)[1]
        ctx.user_data["admin_tahrir"] = {"turi": "rasm", "maydon": maydon}
        matn = _TAHRIR_SOROVLARI["rasm"].format(maydon_nom=_MAYDON_NOMI.get(maydon, maydon))
        await ctx.bot.send_message(q.message.chat_id, matn, parse_mode=ParseMode.HTML)
    elif data.startswith("rasm_prov_t:"):
        provider = data.split(":", 1)[1]
        if provider not in _RASM_PROVIDERLAR:
            return
        admin_store.rasm_sozlama_belgila("provider", provider)
        await _rasm_korsat(q)


async def admin_matn_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin oldin bosgan ✏️ tugmasiga javoban yuborgan MATNni qabul qiladi
    (bot/handlers.py:matn_router chaqiradi, FAQAT admin_tahrir borida)."""
    tahrir = ctx.user_data.pop("admin_tahrir", None)
    if not tahrir or not _admin_bolsa(update):
        return
    matn = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    turi = tahrir["turi"]

    if turi == "narx":
        if not matn.isdigit() or int(matn) <= 0:
            await update.message.reply_text("😔 Iltimos, musbat butun son yuboring (masalan: 5000).")
            ctx.user_data["admin_tahrir"] = tahrir
            return
        admin_store.narx_belgila(tahrir["xizmat"], int(matn))
        await update.message.reply_text(f"✅ Narx yangilandi: {_som(int(matn))} so'm.",
                                        parse_mode=ParseMode.HTML,
                                        reply_markup=_narxlar_klaviatura())
        await update.message.reply_text(_narxlar_matni(), parse_mode=ParseMode.HTML)

    elif turi == "ai":
        modul, maydon = tahrir["modul"], tahrir["maydon"]
        admin_store.ai_sozlama_belgila(modul, maydon, matn)
        await update.message.reply_text("✅ Sozlama yangilandi (darhol amal qiladi).")
        await update.message.reply_text(_ai_modul_matni(modul), parse_mode=ParseMode.HTML,
                                        reply_markup=_ai_modul_klaviatura(modul))

    elif turi == "rasm":
        admin_store.rasm_sozlama_belgila(tahrir["maydon"], matn)
        await update.message.reply_text("✅ Sozlama yangilandi (darhol amal qiladi).")
        await update.message.reply_text(_rasm_matni(), parse_mode=ParseMode.HTML, reply_markup=_rasm_klaviatura())

    elif turi == "promo_nom":
        if not matn:
            ctx.user_data["admin_tahrir"] = tahrir
            return
        kod = promo_store.link_yarat(matn)
        await update.message.reply_text(
            "✅ Link yaratildi:\n\n" + _promo_link_matni(ctx, kod),
            parse_mode=ParseMode.HTML, reply_markup=_promo_link_klaviatura(kod))

    elif turi == "umumiy_xabar":
        if not matn:
            ctx.user_data["admin_tahrir"] = tahrir
            return
        ctx.user_data["umumiy_xabar_draft"] = {"matn": matn, "photo_file_id": None}
        soni = len(admin_store.hisobot_ol()["tashrif_id_lar"])
        await update.message.reply_text(
            f"📢 <b>Tasdiqlang</b>\n\n{_esc(matn)}\n\n"
            f"Yuqoridagi xabar <b>{soni}</b> ta foydalanuvchiga yuboriladi. Davom etamizmi?",
            parse_mode=ParseMode.HTML, reply_markup=_xabar_tasdiq_klaviaturasi())
