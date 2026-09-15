"""
design.py  —  YANGI TIZIM: shablon = sozlama (config)
Har shablon bir nechta "token" bilan belgilanadi. Bitta dvigatel (render.py)
shu tokenlarni o'qib ishlaydi. Yangi shablon = yangi config (kod yozilmaydi).

Tokenlar:
  nom, emoji        — ko'rsatiladigan nom
  dark              — fon to'qmi (matn rangini belgilaydi)
  bg                — "solid" | "gradient" | "cream"
  bg1, bg2, gang    — fon ranglari (gradient bo'lsa 2 ta)
  ink, muted        — matn ranglari
  accent, accent2   — urg'u ranglari
  head, body        — shriftlar
  head_bold         — sarlavha qalinmi
  marker            — sarlavha bezagi: "tagbar"|"eyebrow"|"number"|"dot"|"neon"
  tag               — teg uslubi: "pill"|"outline"|"gray"|"neon"|"dot"|"plain"
  card              — karta uslubi: "border"|"filled"|"leftaccent"|"bartop"|"stagger"|"plain"
  card_bg, card_line
  img               — rasm uslubi: "panel"|"edge"|"small"|"banner"|"neonframe"|"round"
  img_bg
  stat              — statistika uslubi: "softcard"|"filled"|"plain"|"circle"
"""

TEMPLATES = {
    "modern": {
        "nom": "Modern", "img_prompt": "clean modern flat vector illustration, professional, soft colors", "bg_img": "modern.jpg", "emoji": "🔷", "dark": False,
        "bg": "solid", "bg1": "FFFFFF",
        "ink": "1A2130", "muted": "6B7280", "accent": "2563EB", "accent2": "60A5FA",
        "head": "Arial", "body": "Calibri", "head_bold": True,
        "marker": "tagbar", "tag": "pill", "card": "border",
        "card_bg": "FFFFFF", "card_line": "E4E7EC",
        "img": "panel", "img_bg": "F3F4F6", "stat": "softcard", "soft": "EEF3FE",
    },
    "editorial": {
        "nom": "Editorial", "img_prompt": "elegant painterly editorial illustration, muted sophisticated tones", "bg_img": "editorial.jpg", "emoji": "🖋️", "dark": True, "title_bg": True,
        "bg": "solid", "bg1": "16181D",
        "ink": "F5F6F7", "muted": "A8ADB7", "accent": "C9A227", "accent2": "E0C158",
        "head": "Georgia", "body": "Calibri", "head_bold": True,
        "marker": "eyebrow", "tag": "plain", "card": "filled",
        "card_bg": "23262E", "card_line": "23262E",
        "img": "edge", "img_bg": "2A2E37", "stat": "filled",
    },
    "minimal": {
        "nom": "Minimal", "img_prompt": "minimalist line illustration, lots of white space, simple", "bg_img": "minimal.jpg", "emoji": "🤍", "dark": False,
        "bg": "solid", "bg1": "FFFFFF",
        "ink": "1C1C1C", "muted": "8A8A8A", "accent": "9A6A4B", "accent2": "C4A88C",
        "head": "Calibri", "body": "Calibri", "head_bold": False,
        "marker": "number", "tag": "plain", "card": "plain",
        "card_bg": "FFFFFF", "card_line": "E8E8E8",
        "img": "small", "img_bg": "F2F0EC", "stat": "plain",
    },
    "corporate": {
        "nom": "Corporate", "img_prompt": "professional corporate 3d render, blue tones, business", "bg_img": "corporate.jpg", "emoji": "💼", "dark": True, "title_bg": True,
        "bg": "gradient", "bg1": "1E3A5F", "bg2": "0B1D33", "gang": 60,
        "ink": "FFFFFF", "muted": "AEBAC9", "accent": "3B82F6", "accent2": "60A5FA",
        "head": "Arial", "body": "Calibri", "head_bold": True,
        "marker": "tagbar", "tag": "outline", "card": "filled",
        "card_bg": "16304F", "card_line": "24405F",
        "img": "panel", "img_bg": "12263F", "stat": "filled",
    },
    "academic": {
        "nom": "Academic", "img_prompt": "detailed scientific illustration, muted academic style", "bg_img": "academic.jpg", "emoji": "🎓", "dark": False,
        "bg": "solid", "bg1": "FFFFFF",
        "ink": "1F2933", "muted": "5C6773", "accent": "486581", "accent2": "829AB1",
        "head": "Georgia", "body": "Calibri", "head_bold": True,
        "marker": "tagbar", "tag": "gray", "card": "bartop",
        "card_bg": "FFFFFF", "card_line": "D2D6DC", "slate": "3E4C59",
        "img": "panel", "img_bg": "EDEFF2", "stat": "filled",
    },
    "neon": {
        "nom": "Neon", "img_prompt": "cyberpunk neon digital art, dark background, glowing lines", "bg_img": "neon.jpg", "emoji": "🌌", "dark": True, "title_bg": True,
        "bg": "solid", "bg1": "1A1030",
        "ink": "F0ECFA", "muted": "A99FC4", "accent": "FF2E97", "accent2": "B14BF4",
        "head": "Consolas", "body": "Calibri", "head_bold": True,
        "marker": "neon", "tag": "neon", "card": "leftaccent",
        "card_bg": "251845", "card_line": "251845",
        "img": "neonframe", "img_bg": "120A24", "stat": "plain",
    },
    "forest": {
        "nom": "Forest", "img_prompt": "soft natural illustration, warm earthy tones, organic", "bg_img": "forest.jpg", "emoji": "🌿", "dark": False,
        "bg": "cream", "bg1": "F5F2E9",
        "ink": "22331F", "muted": "6E7A64", "accent": "5A8C4E", "accent2": "8FB07A",
        "head": "Georgia", "body": "Calibri", "head_bold": True,
        "marker": "dot", "tag": "dot", "card": "leftaccent",
        "card_bg": "FFFFFF", "card_line": "FFFFFF", "dark_c": "2C4A2E",
        "img": "round", "img_bg": "E4E8DC", "stat": "filled",
    },
    "coral": {
        "nom": "Coral", "img_prompt": "playful colorful flat illustration, cheerful, friendly", "bg_img": "coral.jpg", "emoji": "🪸", "dark": False,
        "bg": "gradient", "bg1": "FFE8D6", "bg2": "FFD9E0", "gang": 120,
        "ink": "3D2530", "muted": "8A6B72", "accent": "F0568C", "accent2": "FF8A5B",
        "head": "Arial", "body": "Calibri", "head_bold": True,
        "marker": "tagbar", "tag": "pill", "card": "stagger",
        "card_bg": "FFFFFF", "card_line": "FFFFFF", "ghost": "F5A5B8",
        "img": "round", "img_bg": "FFFFFF", "stat": "circle",
    },
}

RUYXAT = ["modern", "editorial", "minimal", "corporate",
          "academic", "neon", "forest", "coral"]
