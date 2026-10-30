"""
render.py  —  BITTA DVIGATEL (config'ni o'qib ishlaydi)
Kirish: deck (JSON/dict) + shablon nomi. Chiqish: .pptx

deck = {
  "title": "...", "subtitle": "...", "tag": "...",
  "image": "sarlavha rasmi mazmuni",
  "template": "modern",
  "slides": [
    {"type":"image_text","tag":"...","title":"...","intro":"...",
     "points":[...], "image":"rasm mazmuni"},
    {"type":"cards","tag":"...","title":"...","intro":"...",
     "cards":[{"h":"...","d":"..."}]},
    {"type":"icons", ..., "rows":[{"icon":"dna","h":"...","d":"..."}]},
    {"type":"stats", ..., "stats":[{"num":"6","label":"..."}]},
    {"type":"steps", ..., "steps":["...","..."]},
    {"type":"callout", ..., "callout":"..."},
  ],
  "conclusion": {"title":"Xulosa","text":"..."}
}
"""

import os
import random
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

from slides.design import TEMPLATES

W, H = Inches(13.333), Inches(7.5)
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "icons")


# ---------- primitivlar ----------
def _rgb(h): return RGBColor.from_string(h)
def _blank(p): return p.slides.add_slide(p.slide_layouts[6])


def _rect(sl, x, y, w, h, color, rounded=False, radius=0.06, line=None, lw=1):
    s = sl.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = _rgb(color)
    if line: s.line.color.rgb = _rgb(line); s.line.width = Pt(lw)
    else: s.line.fill.background()
    if rounded:
        try: s.adjustments[0] = radius
        except Exception: pass
    return s


def _oval(sl, x, y, d, color):
    o = sl.shapes.add_shape(MSO_SHAPE.OVAL, x, y, d, d)
    o.fill.solid(); o.fill.fore_color.rgb = _rgb(color); o.line.fill.background()
    return o


def _grad(sl, c1, c2, ang):
    r = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    f = r.fill; f.gradient()
    try: f.gradient_angle = ang
    except Exception: pass
    f.gradient_stops[0].color.rgb = _rgb(c1)
    f.gradient_stops[1].color.rgb = _rgb(c2)
    r.line.fill.background()


def _t(sl, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line=None, alpha=None):
    b = sl.shapes.add_textbox(x, y, w, h); tf = b.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, (txt, sz, bd, col, fn, sp) in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(sp)
        if line: p.line_spacing = line
        r = p.add_run(); r.text = txt
        r.font.size = Pt(sz); r.font.bold = bd; r.font.name = fn
        r.font.color.rgb = _rgb(col)
        if alpha is not None:
            rPr = r._r.get_or_add_rPr(); fl = rPr.find(qn('a:solidFill'))
            if fl is not None:
                sr = fl.find(qn('a:srgbClr'))
                if sr is not None:
                    sr.append(sr.makeelement(qn('a:alpha'), {'val': str(alpha)}))
    return b



def _place_img(sl, path, x, y, w, h):
    """Rasmni box o'lchamiga MARKAZDAN kesib joylaydi (cho'zilmasin/buzilmasin)."""
    try:
        from PIL import Image as _PI
        im = _PI.open(path); iw, ih = im.size
        target = float(w) / float(h)   # EMU nisbat
        cur = iw / ih
        if cur > target:
            nw = int(ih * target); l = (iw - nw) // 2; im = im.crop((l, 0, l + nw, ih))
        else:
            nh = int(iw / target); t = (ih - nh) // 2; im = im.crop((0, t, iw, t + nh))
        tmp = path + ".fit.jpg"; im.convert("RGB").save(tmp, quality=90)
        sl.shapes.add_picture(tmp, x, y, w, h)
    except Exception:
        sl.shapes.add_picture(path, x, y, w, h)


def _icon_box_gradient(sl, x, y, d, c1, c2, shape="square"):
    """Ikonka ostidagi QUTI — ikki rangli (accent -> accent2) diagonal gradient,
    tekis bitta rangdan ko'ra chuqurroq, premium ko'rinish beradi."""
    if shape == "circle":
        s = sl.shapes.add_shape(MSO_SHAPE.OVAL, x, y, d, d)
    else:
        s = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, d, d)
        try: s.adjustments[0] = 0.26
        except Exception: pass
    f = s.fill; f.gradient()
    try: f.gradient_angle = 45
    except Exception: pass
    f.gradient_stops[0].color.rgb = _rgb(c1)
    f.gradient_stops[1].color.rgb = _rgb(c2)
    s.line.fill.background()
    return s


def _icon(sl, name, x, y, d, tint_box=None, shape="square"):
    """tint_box — bitta rang (string) yoki ikki rangli gradient (c1, c2) tuple."""
    p = os.path.join(ICON_DIR, f"{name}.png") if name else ""
    if tint_box:
        c1, c2 = tint_box if isinstance(tint_box, tuple) else (tint_box, tint_box)
        _icon_box_gradient(sl, x, y, d, c1, c2, shape=shape)
        pad = int(d * 0.26)
        if name and os.path.exists(p):
            sl.shapes.add_picture(p, x + pad, y + pad, d - 2*pad, d - 2*pad)
    elif name and os.path.exists(p):
        sl.shapes.add_picture(p, x, y, d, d)


# ---------- uslub yordamchilari (config'ni o'qiydi) ----------
_BG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "assets", "backgrounds")


def _bg(sl, c):
    # 1) fon rasm bo'lsa (config yoki papkada nom bo'yicha) — uni qo'yamiz
    name = c.get("bg_img")
    if name:
        p = os.path.join(_BG_DIR, name)
        if os.path.exists(p):
            sl.shapes.add_picture(p, 0, 0, W, H)
            return
    # 2) aks holda oddiy fon
    if c["bg"] == "gradient":
        _grad(sl, c["bg1"], c["bg2"], c.get("gang", 60))
    else:
        _rect(sl, 0, 0, W, H, c["bg1"])


def _tag(sl, c, x, y, text):
    text = _clip(text, 22)
    st = c["tag"]
    if st == "plain" or not text:
        if text:
            _t(sl, x, y, Inches(6), Inches(0.3),
               [(text.upper(), 11, True, c["accent"], c["body"], 0)])
        return
    if st == "pill":
        w = Inches(0.3 + 0.098*len(text))
        soft = c.get("soft", c["accent"])
        fg = c["accent"] if "soft" in c else "FFFFFF"
        _rect(sl, x, y, w, Inches(0.34), soft if "soft" in c else c["accent"],
              rounded=True, radius=0.5)
        _t(sl, x, y, w, Inches(0.34), [(text.upper(), 10, True, fg, c["head"], 0)],
           align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    elif st == "outline":
        w = Inches(0.32 + 0.1*len(text))
        _rect(sl, x, y, w, Inches(0.34), c["bg2"] if c["bg"] == "gradient" else c["bg1"],
              line=c["accent"], lw=1)
        _t(sl, x, y, w, Inches(0.34), [(text.upper(), 10, True, c["accent"], c["head"], 0)],
           align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    elif st == "gray":
        w = Inches(0.28 + 0.092*len(text))
        _rect(sl, x, y, w, Inches(0.3), "E4E7EB")
        _t(sl, x, y, w, Inches(0.3), [(text.upper(), 10, True, c.get("slate", c["ink"]), c["body"], 0)],
           align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    elif st == "neon":
        _t(sl, x, y, Inches(7), Inches(0.35),
           [(f"// {text.upper()}", 11, True, c["accent"], c["head"], 0)])
    elif st == "dot":
        _oval(sl, x, y + Inches(0.04), Inches(0.15), c["accent"])
        _t(sl, x + Inches(0.28), y, Inches(6), Inches(0.3),
           [(text.upper(), 11, True, c["accent"], c["body"], 0)], anchor=MSO_ANCHOR.MIDDLE)


def _head(sl, c, tag, title, n=1):
    """Sarlavha bloki — marker uslubiga qarab (har shablonda boshqacha).
    Title XAVFSIZ uzunlikka qisqartiriladi VA haqiqiy balandligi HISOBLANADI —
    qaytarilgan qiymat (dyuymda, sarlavha TUGAYDIGAN joy) chaqiruvchi
    funksiyalarga (r_bullets, r_cards, r_icons, r_steps, r_callout) KASKADLI
    joylashuv uchun kerak: uzun sarlavha 2 qatorga yozilsa, pastdagi "intro"
    yoki birinchi qator ENDI avtomatik pastroqqa suriladi (ustma-ust tushmaydi)."""
    title = _clip(title, 70)
    m = c["marker"]
    tx = Inches(0.9)
    if m == "tagbar":
        _tag(sl, c, Inches(0.9), Inches(0.6), tag)
        _rect(sl, Inches(0.9), Inches(1.08), Inches(0.07), Inches(0.6), c["accent"])
        th = _lines_h_in(title, 30, 10.8, 2, 1.1)
        box_h = max(0.85, th + 0.1)
        _t(sl, Inches(1.12), Inches(1.03), Inches(11), Inches(box_h),
           [(title, 30, c["head_bold"], c["ink"], c["head"], 0)], anchor=MSO_ANCHOR.MIDDLE)
        bottom = 1.03 + box_h
    elif m == "eyebrow":
        _rect(sl, Inches(0.9), Inches(0.72), Inches(0.4), Pt(2), c["accent"])
        _t(sl, Inches(1.45), Inches(0.6), Inches(6), Inches(0.3),
           [(_clip(tag, 22).upper(), 11, True, c["accent"], c["body"], 0)], anchor=MSO_ANCHOR.MIDDLE)
        th = _lines_h_in(title, 32, 10.9, 2, 1.1)
        _t(sl, Inches(0.9), Inches(1.05), Inches(11), Inches(th + 0.1),
           [(title, 32, c["head_bold"], c["ink"], c["head"], 0)])
        bottom = 1.05 + th
    elif m == "number":
        _t(sl, Inches(1.3), Inches(0.85), Inches(2), Inches(0.4),
           [(f"{n:02d}", 13, False, c["accent"], c["head"], 0)])
        th = _lines_h_in(title, 30, 10.3, 2, 1.1)
        _t(sl, Inches(1.3), Inches(1.3), Inches(10.5), Inches(th + 0.1),
           [(title, 30, c["head_bold"], c["ink"], c["head"], 0)])
        bottom = 1.3 + th
    elif m == "dot":
        _tag(sl, c, Inches(0.9), Inches(0.6), tag)
        th = _lines_h_in(title, 30, 10.8, 2, 1.1)
        _t(sl, Inches(0.9), Inches(1.05), Inches(11), Inches(th + 0.1),
           [(title, 30, c["head_bold"], c.get("dark_c", c["ink"]), c["head"], 0)])
        bottom = 1.05 + th
    else:  # neon
        _tag(sl, c, Inches(0.9), Inches(0.55), tag)
        th = _lines_h_in(title, 28, 11.3, 2, 1.1)
        _t(sl, Inches(0.9), Inches(1.0), Inches(11.5), Inches(th + 0.1),
           [(title, 28, True, c["accent"], c["head"], 0)])
        bottom = 1.0 + th
    return bottom


def _content_x(c):
    return Inches(1.3) if c["marker"] == "number" else Inches(0.9)


def _image(sl, c, mazmun, x, y, w, h, path=None):
    """Haqiqiy rasm bo'lsa qo'yamiz; bo'lmasa placeholder (img uslubiga qarab)."""
    if path and os.path.exists(path):
        _place_img(sl, path, x, y, w, h)
        return
    st = c["img"]; ic = c["accent"]
    label = "AI RASM SHU YERGA TUSHADI"
    if st == "edge":
        _rect(sl, x, y, w, h, c["img_bg"])
    elif st == "neonframe":
        _rect(sl, x, y, w, h, c["img_bg"], line=ic, lw=1.25); label = "[ AI RASM ]"
    elif st == "round":
        _rect(sl, x, y, w, h, c["img_bg"], rounded=True, radius=0.06,
              line=ic if c["nom"] == "Coral" else None, lw=1.25); label = "AI RASM ✨"
    elif st == "small":
        _rect(sl, x, y, w, h, c["img_bg"]); label = "AI RASM"
    else:  # panel
        _rect(sl, x, y, w, h, c["img_bg"], rounded=(not c["dark"]), radius=0.04,
              line=(ic if not c["dark"] else None), lw=1.1)
    _t(sl, x + Inches(0.3), y + h/2 - Inches(0.5), w - Inches(0.6), Inches(1.0),
       [(label, 12, True, ic, c["head"], 4), (_clip(mazmun, 90), 10, False, c["muted"], c["body"], 0)],
       align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line=1.2)


def _card(sl, c, x, y, w, h, title, desc, idx=0):
    """Karta — card uslubiga qarab. Sarlavha/izoh uzunligi SHU YERDA, haqiqiy
    w/h ga qarab HISOBLAB, xavfsiz chegaraga qisqartiriladi — shu sabab
    karta matni hech qachon kartadan CHIQIB KETMAYDI yoki keyingi qatordagi
    kartaga ustma-ust TUSHMAYDI (fixed joylashuvda eng ko'p uchraydigan xato)."""
    w_in = w / 914400.0; h_in = h / 914400.0
    # Sarlavha BITTA QATORGA sig'adigan uzunlikka qisqartiriladi (2 qatorga
    # yozilsa, pastdagi izoh uchun ajratilgan FIKSIRLANGAN joyga kirib,
    # ustma-ust tushib qolardi — izoh bloki sarlavha balandligiga qarab
    # KASKADLI emas, shu sabab sarlavha 1 qatordan OSHMASLIGI SHART).
    title = _clip(title, max(14, int((w_in - 0.6) / (18 * 0.0122 * 1.15))))
    desc_lines = max(2, int((h_in - 0.9) / (16 * 1.25 / 72)))
    desc = _clip(desc, max(24, int((w_in - 0.6) / (16 * 0.0122)) * desc_lines))
    st = c["card"]
    dark_txt = "FFFFFF" if c["dark"] else c["ink"]
    if st == "border":
        _rect(sl, x, y, w, h, c["card_bg"], rounded=True, radius=0.05,
              line=c["card_line"], lw=1)
        _rect(sl, x, y + Inches(0.25), Inches(0.06), h - Inches(0.5), c["accent"])
        pad = Inches(0.35)
    elif st == "filled":
        _rect(sl, x, y, w, h, c["card_bg"], rounded=True, radius=0.05)
        _rect(sl, x + Inches(0.35), y + Inches(0.3), Inches(0.35), Pt(3), c["accent"])
        pad = Inches(0.35)
    elif st == "leftaccent":
        _rect(sl, x, y, w, h, c["card_bg"], rounded=(not c["dark"]), radius=0.07)
        _rect(sl, x, y, Inches(0.07), h, c["accent"])
        pad = Inches(0.35)
    elif st == "bartop":
        _rect(sl, x, y, w, h, c["card_bg"], rounded=True, radius=0.05,
              line=c["card_line"], lw=1)
        _rect(sl, x, y, w, Inches(0.09), c["accent"])
        pad = Inches(0.35)
    elif st == "stagger":
        _rect(sl, x, y, w, h, c["card_bg"], rounded=True, radius=0.12)
        _oval(sl, x + Inches(0.3), y + Inches(0.3), Inches(0.35),
              c["accent"] if idx % 2 == 0 else c["accent2"])
        _t(sl, x + Inches(0.9), y + Inches(0.28), w - Inches(1.2), Inches(0.45),
           [(title, 18, True, c["ink"], c["head"], 0)])
        _t(sl, x + Inches(0.9), y + Inches(0.8), w - Inches(1.2), Inches(0.8),
           [(desc, 16, False, c["muted"], c["body"], 0)], line=1.25)
        return
    else:  # plain (Minimal — kartasiz, chiziq bilan)
        _t(sl, x, y, w, Inches(0.45), [(title, 18, False, c["ink"], c["head"], 0)])
        _t(sl, x, y + Inches(0.42), w, Inches(0.55),
           [(desc, 16, False, c["muted"], c["body"], 0)], line=1.25)
        _rect(sl, x, y + h - Inches(0.1), w, Pt(1), c["card_line"])
        return
    _t(sl, x + pad, y + Inches(0.28), w - pad - Inches(0.25), Inches(0.5),
       [(title, 18, True, dark_txt, c["head"], 0)])
    _t(sl, x + pad, y + Inches(0.85), w - pad - Inches(0.25), h - Inches(0.9),
       [(desc, 16, False, c["muted"], c["body"], 0)], line=1.25)


# ---------- LAYOUT RENDERERLARI ----------

def _rect_a(sl, x, y, w, h, color, alpha):
    """Yarim shaffof to'rtburchak (overlay). alpha: 0-100000 (masalan 48000 = 48%)."""
    s = _rect(sl, x, y, w, h, color)
    sp = s._element.spPr
    fill = sp.find(qn('a:solidFill'))
    if fill is not None:
        srgb = fill.find(qn('a:srgbClr'))
        if srgb is not None:
            srgb.append(srgb.makeelement(qn('a:alpha'), {'val': str(alpha)}))
    return s


def _bg_image_title(sl, c, deck):
    """Butun ekran fon rasm + qoraytiruvchi overlay + matn (premium hero)."""
    base = c.get("img_bg", "12141A")
    ipath = deck.get("_img_path")
    if ipath and os.path.exists(ipath):
        _place_img(sl, ipath, 0, 0, W, H)
    else:
        _rect(sl, 0, 0, W, H, base)
        _t(sl, Inches(0.5), Inches(0.4), Inches(12.3), Inches(0.4),
           [("AI ORQA FON RASM  ·  " + deck.get("image", ""), 11, True, c["accent"], c["head"], 0)],
           align=PP_ALIGN.CENTER)
    _rect_a(sl, 0, 0, W, H, "0A0A0F", 50000)          # qoraytiruvchi qatlam (50%)
    # matn (oq, chapda)
    tx = Inches(0.9)
    tag = _clip(deck.get("tag", ""), 22)
    if c["tag"] == "neon" and tag:
        _t(sl, tx, Inches(2.7), Inches(8), Inches(0.4),
           [(f"// {tag.upper()}", 12, True, c["accent"], c["head"], 0)])
    elif tag:
        wtag = Inches(0.3 + 0.1*len(tag))
        _rect(sl, tx, Inches(2.7), wtag, Inches(0.36), c["accent"], rounded=True, radius=0.5)
        _t(sl, tx, Inches(2.7), wtag, Inches(0.36),
           [(tag.upper(), 10, True, "FFFFFF", c["head"], 0)],
           align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    title = _clip(deck.get("title", ""), 70)
    tsz = _tsize(title, 52, 44, 34)
    _th = _lines_h_in(title, tsz, 11.0, 3, 1.03)
    _t(sl, tx, Inches(3.3), Inches(11.5), Inches(_th + 0.15),
       [(title, tsz, c["head_bold"], "FFFFFF", c["head"], 0)], line=1.03)
    if deck.get("subtitle"):
        suby = min(3.3 + _th + 0.3, 5.6)
        _t(sl, tx + Inches(0.02), Inches(suby), Inches(9.5), Inches(1.6),
           [(_clip(deck["subtitle"], 150), 18, False, "E8E8EC", c["body"], 0)], line=1.4)



def _tsize(title, big, mid, small):
    n = len(title or "")
    return big if n <= 18 else (mid if n <= 30 else small)


def _est_lines(title, size, width_in):
    import math
    cpl = max(6, int(width_in / (size * 0.0122)))
    return max(1, math.ceil(len(title or "") / cpl))


def _line_h(size, mult=1.2):
    """Bitta qator balandligi (dyuymda) — kaskadli (bir-biridan keyin
    joylashadigan) matn bloklari uchun KEYINGI blok Y koordinatasini
    HISOBLAB chiqarish uchun (ustiga tushib qolish — overlap — oldini oladi,
    xuddi sarlavha/subtitle juftligida qilingani kabi, boshqa barcha matn
    bloklariga ham qo'llaniladi)."""
    return size * mult / 72.0


def _clip(text, max_chars):
    """Matnni XAVFSIZ uzunlikka qisqartiradi (so'z chegarasida, "…" bilan) —
    AI juda uzun matn qaytarsa ham, slaytdagi qutidan CHIQIB KETMASLIGI
    (boshqa elementlarga ustma-ust tushmasligi) uchun SO'NGGI himoya qatlami."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    if len(cut) < max_chars * 0.6:
        cut = text[:max_chars]
    return cut.rstrip(",.;:—- ") + "…"


def _lines_h_in(text, size, width_in, max_lines, mult=1.2):
    """Matn necha qatorga yozilishini baholab, UMUMIY balandligini (dyuymda)
    qaytaradi — max_lines bilan yuqori chegaralanadi (keyingi blok juda pastga
    tushib ketmasin deb)."""
    n = min(_est_lines(text, size, width_in), max_lines)
    return n * _line_h(size, mult)


def r_title(sl, c, deck):
    if c.get("title_bg"):
        _bg_image_title(sl, c, deck); return
    _bg(sl, c)
    img = deck.get("image")
    ipath = deck.get("_img_path")
    tx = Inches(0.9); tw = Inches(6.2)
    if img:
        st = c["img"]
        if st == "small":
            _image(sl, c, img, Inches(9.0), Inches(4.6), Inches(3.6), Inches(2.4), path=ipath)
            tx = Inches(1.3); tw = Inches(7.0)
        elif st == "edge":
            _image(sl, c, img, Inches(7.6), 0, W - Inches(7.6), H, path=ipath)
        elif st == "round":
            _image(sl, c, img, Inches(7.6), Inches(0.9), Inches(4.9), Inches(5.7), path=ipath)
        elif st == "neonframe":
            _image(sl, c, img, Inches(7.4), Inches(1.2), Inches(5.1), Inches(5.1), path=ipath)
        else:
            _image(sl, c, img, Inches(7.5), 0 if c["dark"] and c["bg"] == "gradient" else Inches(0.9),
                   W - Inches(7.6) if (c["dark"] and c["bg"] == "gradient") else Inches(5.0),
                   H if (c["dark"] and c["bg"] == "gradient") else Inches(5.7), path=ipath)
    marker = c["marker"]
    y0 = Inches(2.6)
    title = _clip(deck.get("title", ""), 60)
    if marker == "number":
        _t(sl, tx, y0, tw, Inches(0.4), [(_clip(deck.get("tag", ""), 22).upper(), 11, False, c["accent"], c["head"], 0)])
        _rect(sl, tx, y0 + Inches(0.42), Inches(0.5), Pt(2), c["accent"])
        tsz = _tsize(title, 46, 40, 32)
        _th = _lines_h_in(title, tsz, 6.0, 3, 1.04)
        _t(sl, tx, y0 + Inches(0.7), tw, Inches(_th + 0.15), [(title, tsz, c["head_bold"], c["ink"], c["head"], 0)], line=1.04)
        suby_in = 2.6 + 0.7 + _th + 0.35
    else:
        _tag(sl, c, tx, y0, deck.get("tag", ""))
        tsz = _tsize(title, 48, 40, 32)
        _th = _lines_h_in(title, tsz, tw.inches - 0.2, 3, 1.04)
        _t(sl, tx, y0 + Inches(0.55), tw, Inches(_th + 0.15),
           [(title, tsz, c["head_bold"], c["ink"] if c["nom"] != "Neon" else c["accent"], c["head"], 0)], line=1.04)
        suby_in = 2.6 + 0.55 + _th + 0.35
    if deck.get("subtitle"):
        suby_in = min(suby_in, 6.0)
        _t(sl, tx + Inches(0.02), Inches(suby_in), tw - Inches(0.2), Inches(1.6),
           [(_clip(deck["subtitle"], 150), 19, False, c["muted"], c["body"], 0)], line=1.4)


def r_image_text(sl, c, s, n, left=False):
    _bg(sl, c)
    st = c["img"]; iw = Inches(4.8)
    # "panel" uslubi normalda YUMALOQ BURCHAK + CHEGARA bilan chiziladi (_image()
    # ichida) — shu sababli chekka-chekkaga (iy=0, ih=H) cho'zilsa burchaklar
    # slayt qirrasida kesilib qoladi. Faqat dark+gradient shablonlarda (masalan
    # Corporate) panel chegarasiz/burchaksiz chiziladi, o'shanda chekka-chekkaga
    # cho'zish to'g'ri ko'rinadi (r_title dagi bir xil shart bilan mos).
    full_bleed = st in ("edge", "neonframe") or (st == "panel" and c["dark"] and c["bg"] == "gradient")
    if full_bleed:
        ix = 0 if left else W - iw
        iy = 0; ih = H
    else:
        iy = Inches(0.7); ih = Inches(6.1)
        ix = Inches(0.5) if left else W - iw - Inches(0.5)
    _image(sl, c, s.get("image", ""), ix, iy, iw, ih, path=s.get("_img_path"))
    tx = Inches(5.4) if left else Inches(0.9)
    tw = Inches(7.0)
    _tag(sl, c, tx, Inches(0.85), s.get("tag", ""))

    # KASKADLI joylashuv — har blok O'ZIDAN OLDINGI blokning HAQIQIY (hisoblangan)
    # balandligiga qarab boshlanadi, FIKSIRLANGAN Y emas — shu sabab uzun sarlavha/
    # kirish matni KEYINGI blokka hech qachon ustma-ust tushmaydi (eski versiyada
    # sarlavha 3 qatorga yozilsa, "intro" ustiga tushib qolishi mumkin edi).
    title = _clip(s.get("title", ""), 72)
    title_h = _lines_h_in(title, 31, tw.inches - 0.1, 3, 1.05)
    _t(sl, tx, Inches(1.4), tw, Inches(title_h + 0.1),
       [(title, 31, c["head_bold"], c["ink"], c["head"], 0)], line=1.05)
    y = 1.4 + title_h + 0.22

    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 170)
        intro_h = _lines_h_in(intro, 17, tw.inches - 0.3, 4, 1.35)
        _t(sl, tx, Inches(y), tw - Inches(0.3), Inches(intro_h + 0.1),
           [(intro, 17, False, c["muted"], c["body"], 0)], line=1.35)
        y = y + intro_h + 0.3

    box_h = max(Inches(1.3), H - Inches(y) - Inches(0.35))
    box = sl.shapes.add_textbox(tx, Inches(y), tw - Inches(0.3), box_h)
    tf = box.text_frame; tf.word_wrap = True
    points = [p for p in s.get("points", []) if p][:3]
    for i, pt in enumerate(points):
        pt = _clip(pt, 85)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(11); p.line_spacing = 1.25
        rm = p.add_run(); rm.text = "—  "
        rm.font.size = Pt(16); rm.font.name = c["body"]; rm.font.bold = True
        rm.font.color.rgb = _rgb(c["accent"])
        r = p.add_run(); r.text = pt
        r.font.size = Pt(16); r.font.name = c["body"]; r.font.color.rgb = _rgb(c["ink"])


def r_bullets(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x = _content_x(c)
    bar = Inches(0.22) if c["marker"] == "tagbar" else 0
    bx = x + bar
    bw_in = 11.0 - bar / 914400
    y = max(2.05, head_bottom + 0.3)
    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 150)
        _t(sl, bx, Inches(y), Inches(bw_in), Inches(1.5),
           [(intro, 16, False, c["muted"], c["body"], 0)], line=1.3)
        y = y + _lines_h_in(intro, 16, bw_in, 4, 1.3) + 0.35
    else:
        y = y + 0.55
    box_h = max(Inches(1.5), H - Inches(y) - Inches(0.4))
    box = sl.shapes.add_textbox(bx, Inches(y), Inches(10.8), box_h)
    tf = box.text_frame; tf.word_wrap = True
    points = [p for p in s.get("points", []) if p][:5]
    for i, pt in enumerate(points):
        pt = _clip(pt, 110)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(16); p.line_spacing = 1.25
        rm = p.add_run(); rm.text = "—  "
        rm.font.size = Pt(18); rm.font.name = c["body"]; rm.font.bold = True
        rm.font.color.rgb = _rgb(c["accent"])
        r = p.add_run(); r.text = pt
        r.font.size = Pt(18); r.font.name = c["body"]; r.font.color.rgb = _rgb(c["ink"])


def r_cards(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x0 = _content_x(c)
    y_in = max(1.95, head_bottom + 0.25)
    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 140)
        _t(sl, x0, Inches(y_in), Inches(11.4), Inches(0.8),
           [(intro, 16, False, c["muted"], c["body"], 0)], line=1.3)
        y_in = y_in + _lines_h_in(intro, 16, 11.4, 3, 1.3) + 0.35
    else:
        y_in = max(2.75, y_in + 0.3)
    cards = [cd for cd in s.get("cards", []) if cd.get("h")][:4]
    nn = len(cards)
    if not nn:
        return
    y = Inches(y_in)
    if c["card"] == "stagger":
        cw = Inches(5.7)
        pos = [(x0, y), (Emu(x0+cw), Emu(y+Inches(0.35))),
               (x0, Emu(y+Inches(2.0))), (Emu(x0+cw), Emu(y+Inches(2.35)))]
        for i, cd in enumerate(cards):
            xx, yy = pos[i]; _card(sl, c, xx, yy, cw, Inches(1.7), cd["h"], cd.get("d", ""), i)
        return
    if nn == 3:
        # Generik 2-ustunli panjarada 3 ta karta NOQULAY ko'rinadi (2 tepada +
        # 1 yolg'iz pastda, chapga tirilib) — BALANSLI ko'rinish uchun 3
        # tasini ham BITTA qatorga teng taqsimlab joylaymiz.
        gap = Inches(0.35)
        cw = Emu(int((Inches(11.5) - gap * 2) / 3))
        ch = Inches(3.6)
        for i, cd in enumerate(cards):
            xx = Emu(x0 + (cw + gap) * i)
            _card(sl, c, xx, y, cw, ch, cd["h"], cd.get("d", ""), i)
        return
    cw = Inches(5.7); ch = Inches(2.25); gap = Inches(0.45)
    for i, cd in enumerate(cards):
        col = i % 2; row = i // 2
        x = Emu(x0 + (cw + gap) * col)
        yy = Emu(y + (ch + Inches(0.4)) * row)
        _card(sl, c, x, yy, cw, ch, cd["h"], cd.get("d", ""), i)


def r_icons(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x = _content_x(c) + (Inches(0.22) if c["marker"] == "tagbar" else Inches(0))
    y = max(2.35, head_bottom + 0.3)
    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 140)
        _t(sl, x, Inches(y), Inches(11), Inches(0.8),
           [(intro, 16, False, c["muted"], c["body"], 0)], line=1.3)
        y = y + _lines_h_in(intro, 16, 11.0, 3, 1.3) + 0.35
    rows = [r for r in s.get("rows", []) if r.get("h")][:4]
    tw_in = 9.8
    for row in rows:
        # Qator sarlavhasi (h_txt) BITTA QATORGA sig'adigan uzunlikka
        # qisqartiriladi — izoh (d_txt) FIKSIRLANGAN y+0.45 joyda boshlanadi,
        # sarlavha 2 qatorga yozilsa aynan o'sha joyga kirib ketardi.
        h_txt = _clip(row["h"], max(14, int(tw_in / (18 * 0.0122 * 1.15))))
        d_txt = _clip(row.get("d", ""), 130)
        d_h = _lines_h_in(d_txt, 16, tw_in, 4, 1.2)
        _icon(sl, row.get("icon"), x, Inches(y), Inches(0.85),
              tint_box=(c["accent"], c.get("accent2", c["accent"])),
              shape=c.get("icon_shape", "square"))
        _t(sl, x + Inches(1.15), Inches(y - 0.02), Inches(10), Inches(0.5),
           [(h_txt, 18, True, c["ink"], c["head"], 0)])
        _t(sl, x + Inches(1.15), Inches(y + 0.45), Inches(tw_in), Inches(d_h + 0.1),
           [(d_txt, 16, False, c["muted"], c["body"], 0)], line=1.2)
        # QATOR balandligi MATN uzunligiga qarab DINAMIK — ikonka (0.85in) yoki
        # matn balandligidan (qaysi kattaroq) + bo'sh joy. Shu sabab uzun izoh
        # KEYINGI ikonka/matnga hech qachon ustma-ust TUSHMAYDI.
        y = y + max(0.85, 0.45 + d_h) + 0.3


def r_stats(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x0 = _content_x(c)
    stats = [stt for stt in s.get("stats", []) if stt.get("num")][:3]; nn = len(stats)
    if not nn: return
    total = Inches(11.5); gap = Inches(0.4); cw = int((total - gap*(nn-1))/nn)
    x = x0; y = Inches(max(3.15, head_bottom + 0.3)); st = c["stat"]
    for i, stt in enumerate(stats):
        num, lab = _clip(stt["num"], 7), _clip(stt.get("label", ""), 64)
        if st == "plain":
            _t(sl, x, y, cw, Inches(1.0), [(num, 54, c["head_bold"], c["ink"], c["head"], 0)])
            _rect(sl, x, y + Inches(1.15), Inches(0.5), Pt(2), c["accent"])
            _t(sl, x, y + Inches(1.35), cw - Inches(0.4), Inches(0.9),
               [(lab, 16, False, c["muted"], c["body"], 0)], line=1.25)
        elif st == "circle":
            _rect(sl, x, y, cw, Inches(2.7), c["card_bg"], rounded=True, radius=0.1)
            _oval(sl, x + Inches(0.35), y + Inches(0.35), Inches(0.6),
                  [c["accent"], c["accent2"], c["accent"]][i % 3])
            _t(sl, x + Inches(0.35), y + Inches(1.15), cw - Inches(0.7), Inches(0.9),
               [(num, 46, True, c["ink"], c["head"], 0)])
            _t(sl, x + Inches(0.35), y + Inches(2.0), cw - Inches(0.7), Inches(0.55),
               [(lab, 15, False, c["muted"], c["body"], 0)], line=1.2)
        else:  # softcard / filled
            bg = c.get("soft") if st == "softcard" else (c.get("dark_c") or c["card_bg"])
            numcol = c["accent"] if st == "softcard" else (c["accent2"] if c.get("dark_c") else c["accent"])
            labcol = c["ink"] if st == "softcard" else ("D8E0CE" if c.get("dark_c") else c["muted"])
            _rect(sl, x, y, cw, Inches(2.9), bg, rounded=True, radius=0.06)
            _t(sl, x + Inches(0.35), y + Inches(0.4), cw - Inches(0.7), Inches(1.0),
               [(num, 52, True, numcol, c["head"], 0)])
            _t(sl, x + Inches(0.35), y + Inches(1.7), cw - Inches(0.7), Inches(0.9),
               [(lab, 16, False, labcol, c["body"], 0)], line=1.2)
        x = Emu(x + cw + gap)


def r_steps(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x = _content_x(c) + (Inches(0.22) if c["marker"] == "tagbar" else Inches(0))
    y = max(2.5, head_bottom + 0.3)
    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 140)
        _t(sl, x, Inches(y), Inches(11), Inches(0.8),
           [(intro, 16, False, c["muted"], c["body"], 0)], line=1.3)
        y = max(3.15, y + _lines_h_in(intro, 16, 11.0, 3, 1.3) + 0.35)
    steps = [st for st in s.get("steps", []) if st][:5]
    tw_in = 10.0
    for i, stp in enumerate(steps, 1):
        stp = _clip(stp, 120)
        o = _oval(sl, x, Inches(y), Inches(0.72), c["accent"])
        tp = o.text_frame.paragraphs[0]; tp.alignment = PP_ALIGN.CENTER
        rr = tp.add_run(); rr.text = str(i)
        rr.font.size = Pt(26); rr.font.bold = True; rr.font.name = c["head"]
        rr.font.color.rgb = _rgb("FFFFFF")
        _t(sl, x + Inches(1.1), Inches(y + 0.02), Inches(tw_in), Inches(1.3),
           [(stp, 18, False, c["ink"], c["body"], 0)], anchor=MSO_ANCHOR.MIDDLE, line=1.15)
        # Bosqich matni uzun bo'lsa (2+ qator) KEYINGI bosqich doirasi bilan
        # ustma-ust tushmasin deb, qator balandligi MATNGA qarab o'sadi.
        txt_h = _lines_h_in(stp, 18, tw_in, 5, 1.15)
        y = y + max(0.72, txt_h) + 0.35


def r_callout(sl, c, s, n):
    _bg(sl, c)
    head_bottom = _head(sl, c, s.get("tag", ""), s["title"], n)
    x0 = _content_x(c)
    y_in = max(2.05, head_bottom + 0.3)
    intro = s.get("intro")
    if intro:
        intro = _clip(intro, 160)
        _t(sl, x0, Inches(y_in), Inches(11.2), Inches(1.5),
           [(intro, 17, False, c["muted"] if not c["dark"] else c["ink"], c["body"], 0)], line=1.35)
        y_in = y_in + _lines_h_in(intro, 17, 11.2, 4, 1.35) + 0.35
    y = Inches(max(3.9, y_in))
    bg = c.get("soft") or c["card_bg"]
    _rect(sl, x0, y, Inches(11.5), Inches(2.1), bg, rounded=True, radius=0.06)
    _rect(sl, x0, y + Inches(0.3), Inches(0.08), Inches(1.3), c["accent"])
    txtcol = c["ink"]
    callout = _clip(s.get("callout", ""), 110)
    _t(sl, Emu(x0 + Inches(0.35)), y + Inches(0.45), Inches(10.8), Inches(1.1),
       [(callout, 19, True, txtcol, c["body"], 0)], line=1.3)


DISPATCH = {"bullets": r_bullets, "cards": r_cards, "icons": r_icons,
            "stats": r_stats, "steps": r_steps, "callout": r_callout}



def r_conclusion(sl, c, concl, n):
    """Mukammal xulosa slayti: katta sarlavha + asosiy fikrlar + yakuniy gap."""
    _bg(sl, c)
    dark = c["dark"]
    ink = "FFFFFF" if dark else c["ink"]
    # katta sarlavha
    _t(sl, Inches(0.9), Inches(0.85), Inches(11.5), Inches(1.0),
       [(_clip(concl.get("title", "Xulosa"), 50), 40, c["head_bold"], c["accent"], c["head"], 0)])
    _rect(sl, Inches(0.9), Inches(1.85), Inches(1.0), Pt(3), c["accent"])
    # asosiy fikrlar (checkmark bilan)
    points = [p for p in concl.get("points", []) if p][:3]
    y = 2.4
    for pt in points:
        pt = _clip(pt, 90)
        o = _oval(sl, Inches(0.9), Inches(y + 0.03), Inches(0.42), c["accent"])
        tp = o.text_frame.paragraphs[0]; tp.alignment = PP_ALIGN.CENTER
        rr = tp.add_run(); rr.text = "✓"
        rr.font.size = Pt(16); rr.font.bold = True; rr.font.name = c["head"]
        rr.font.color.rgb = _rgb("FFFFFF")
        _t(sl, Inches(1.55), Inches(y - 0.02), Inches(10.8), Inches(0.9),
           [(pt, 17, False, ink, c["body"], 0)], anchor=MSO_ANCHOR.MIDDLE, line=1.2)
        txt_h = _lines_h_in(pt, 17, 10.8, 3, 1.2)
        y = y + max(0.85, txt_h + 0.2)
    # yakuniy gap (rangli quti)
    txt = _clip(concl.get("text", ""), 150)
    if txt:
        by = Inches(max(5.9, y + 0.3))
        bg = c.get("soft") or c.get("card_bg") or c["accent"]
        _rect(sl, Inches(0.9), by, Inches(11.5), Inches(1.2), bg, rounded=True, radius=0.08)
        _rect(sl, Inches(0.9), by + Inches(0.22), Inches(0.08), Inches(0.76), c["accent"])
        tcol = c["ink"] if not dark else "FFFFFF"
        _t(sl, Inches(1.25), by + Inches(0.28), Inches(10.8), Inches(0.7),
           [(txt, 16, True, tcol, c["body"], 0)], anchor=MSO_ANCHOR.MIDDLE, line=1.25)


def render(deck, out_path):
    base = TEMPLATES.get(deck.get("template", "modern"), TEMPLATES["modern"])
    # TEMPLATES ICHIDAGI lug'atni o'zgartirmaymiz (bir nechta foydalanuvchi BIR
    # VAQTDA slayt yaratishi mumkin — umumiy global holatni o'zgartirish xavfli).
    # Shu sabab NUSXA olib, FAQAT shu nusxada orqa fonni 3 variantdan TASODIFIY
    # tanlaymiz — bir xil shablonni qayta tanlasa ham ko'rinishi farq qiladi.
    c = dict(base)
    bg_imgs = c.get("bg_imgs") or ([c["bg_img"]] if c.get("bg_img") else [])
    if bg_imgs:
        c["bg_img"] = random.choice(bg_imgs)
    prs = Presentation(); prs.slide_width = W; prs.slide_height = H
    r_title(_blank(prs), c, deck)
    # Rasm chap/o'ngda almashinib turadi (n juft/toq) — QAYSI tomondan
    # BOSHLANISHI esa deck SARLAVHASIGA qarab "tasodifiy" (lekin TAKRORLANADIGAN)
    # tanlanadi, shu sabab BIR XIL mavzuni qayta yaratsangiz ham, slaydlar
    # joylashuvi har safar BIR XIL emas — har bir taqdimot o'ziga xos ko'rinadi.
    start_left = bool(hash(deck.get("title", "")) & 1)
    n = 1
    for s in deck.get("slides", []):
        typ = s.get("type", "bullets")
        sl = _blank(prs)
        if typ in ("image_text", "image"):
            r_image_text(sl, c, s, n, left=((n % 2 == 0) != start_left))
        else:
            DISPATCH.get(typ, r_bullets)(sl, c, s, n)
        n += 1
    concl = deck.get("conclusion")
    if concl:
        r_conclusion(_blank(prs), c, concl, n)
    prs.save(out_path)
    return out_path
