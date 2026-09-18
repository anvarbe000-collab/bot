"""
bot/click_webhook.py — Click (Shop API) uchun aiohttp web-server yo'llari
(/click/prepare, /click/complete). Botning O'ZI (python-telegram-bot
Application) bilan BIR XIL asyncio davrida ishlaydi (main.py da birga
ishga tushiriladi) — shu sababli to'lov tasdiqlanganda to'g'ridan-to'g'ri
application.bot.send_message() va application.user_data ishlatiladi,
alohida process/queue kerak emas.
"""

import logging

from aiohttp import web

import click_pay
import admin_store
import referal_store
from bot.handlers import _TOLOV_BAJARUVCHI, _CtxFor

log = logging.getLogger("click_webhook")


class _ApplicationCtx:
    """_CtxFor kutgan 'real_ctx' shaklini (`.bot`, `.application`) beradi —
    webhook so'rovida haqiqiy ptb ctx yo'q, faqat Application bor."""
    def __init__(self, application):
        self.bot = application.bot
        self.application = application


async def _prepare(request):
    d = dict(await request.post())
    log.info("Click PREPARE: %s", {k: v for k, v in d.items() if k != "sign_string"})
    javob, _ = click_pay.prepare_ishla(d)
    return web.json_response(javob)


async def _complete(request):
    d = dict(await request.post())
    log.info("Click COMPLETE: %s", {k: v for k, v in d.items() if k != "sign_string"})
    javob, order_id, muvaffaqiyatli = click_pay.complete_ishla(d)
    if muvaffaqiyatli and order_id:
        buyurtma = click_pay.buyurtma_ol(order_id)
        if buyurtma:
            application = request.app["ptb_application"]
            await _xizmatni_topshir(application, buyurtma)
    return web.json_response(javob)


async def _xizmatni_topshir(application, buyurtma):
    """Click COMPLETE muvaffaqiyatli bo'lgach — talabaning kutayotgan ishini
    (slayt render, ingliz tahlili va h.k.) admin qo'lda tasdiqlaganidagi BILAN
    AYNAN BIR XIL yo'l (_TOLOV_BAJARUVCHI) orqali bajaradi. Bu — REAL (Click
    orqali) pul bilan to'lov, shu sabab shu yerda (va FAQAT shu yerda) talaba
    referal orqali kirgan bo'lsa va bu uning BIRINCHI to'lovi bo'lsa, uni
    chaqirgan odamga bonus beriladi (referal_store O'ZI idempotent — bir xil
    chat_id uchun ikkinchi marta chaqirilsa hech narsa qilmaydi)."""
    chat_id = buyurtma["chat_id"]
    mode = buyurtma["mode"]
    talaba_ud = application.user_data[chat_id]
    bajaruvchi = _TOLOV_BAJARUVCHI.get(mode)
    if not bajaruvchi or talaba_ud.get("holat") != "tolov_kutilmoqda":
        log.warning("Click: xizmat topshirib bo'lmadi (mode=%s, chat_id=%s, holat mos emas)",
                    mode, chat_id)
        return
    admin_store.tolov_qayd_et(mode, buyurtma["summa"])
    referrer_id, bonus_berildi = referal_store.birinchi_tolov_va_bonus_qayta_ishla(chat_id)
    if bonus_berildi:
        try:
            await application.bot.send_message(
                referrer_id,
                "🎉 <b>Tabriklaymiz!</b> Do'stingiz birinchi to'lovni amalga oshirdi.\n"
                f"💰 Balansingizga <b>{referal_store.REFERAL_BONUS} so'm</b> qo'shildi.",
                parse_mode="HTML")
        except Exception:
            log.warning("Referrerga bonus xabarini yuborib bo'lmadi (referrer_id=%s)", referrer_id)
    talaba_ud.pop("click_order_id", None)
    try:
        await application.bot.send_message(chat_id, "✅ To'lov Click orqali qabul qilindi! Tayyorlanmoqda... ⏳")
        await bajaruvchi(_CtxFor(_ApplicationCtx(application), talaba_ud), chat_id)
    except Exception:
        log.exception("Click to'lovidan keyin xizmatni topshirishda xato (chat_id=%s)", chat_id)


async def _salomat(request):
    """Oddiy healthcheck — Railway (yoki boshqa PaaS) konteyner tirikligini
    shu orqali tekshiradi. Click bilan aloqasi yo'q, faqat server ishlab
    turganini ko'rsatadi."""
    return web.Response(text="OK")


def click_web_ilova(application):
    """aiohttp.web.Application yaratadi va /click/prepare, /click/complete
    yo'llarini ro'yxatdan o'tkazadi. main.py shu web-app'ni bot bilan bir xil
    asyncio davrasida (event loop) ishga tushiradi."""
    app = web.Application()
    app["ptb_application"] = application
    app.router.add_get("/", _salomat)
    app.router.add_post("/click/prepare", _prepare)
    app.router.add_post("/click/complete", _complete)
    return app
