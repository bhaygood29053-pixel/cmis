
"""
Liquidity Scout X1 Asset Template Renderer

Uses:
  graphics/templates/liquidity_scout_x1_asset_template.png

Outputs:
  graphics/generated/<SYMBOL>_report.png

The template artwork is permanent. Live XDEX values are painted over the
placeholder areas using deterministic data supplied by Liquidity Scout.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = BASE_DIR / "graphics" / "templates" / "liquidity_scout_x1_asset_template.png"
OUTPUT_DIR = BASE_DIR / "graphics" / "generated"
TOKEN_ART_DIR = BASE_DIR / "graphics" / "tokens"

CANVAS = (1536, 1024)

WHITE = (236, 242, 247)
CYAN = (67, 229, 242)
GREEN = (56, 226, 120)
RED = (255, 88, 88)
MUTED = (180, 194, 206)
DARK = (4, 15, 22)


def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _fit(draw, text, max_width, start_size, bold=False, min_size=12):
    text = str(text)
    for size in range(start_size, min_size - 1, -1):
        f = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=f)
        if box[2] - box[0] <= max_width:
            return f
    return _font(min_size, bold)


def _money(value):
    try:
        v = float(value)
    except Exception:
        return "N/A"
    if abs(v) >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v:,.2f}"
    if abs(v) >= 1:
        return f"${v:,.4f}"
    return f"${v:,.8f}"


def _pct(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "N/A"


def _int(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return "N/A"


def _safety_parts(safety):
    text = str(safety or "N/A").strip()
    grade = "?"
    score = ""
    if text:
        grade = text[0].upper()
    if "(" in text and ")" in text:
        score = text[text.find("(")+1:text.find(")")]
    return grade, score


def _erase(draw, box):
    # Template panels are close to black; use a dark opaque patch to clear
    # placeholder values while keeping the surrounding HUD visible.
    draw.rectangle(box, fill=DARK)


def _write_value(draw, xy, text, width, size=24, color=WHITE, bold=False):
    f = _fit(draw, str(text), width, size, bold=bold, min_size=13)
    draw.text(xy, str(text), font=f, fill=color)


def _wrap_text(draw, text, max_width, font, max_lines=3):
    words = str(text).split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        box = draw.textbbox((0, 0), test, font=font)
        if box[2] - box[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines


def _find_token_art(symbol):
    symbol = str(symbol or "").upper()
    if not symbol:
        return None
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = TOKEN_ART_DIR / f"{symbol}{ext}"
        if candidate.exists():
            return candidate
        candidate = TOKEN_ART_DIR / f"{symbol.lower()}{ext}"
        if candidate.exists():
            return candidate
    return None


def _place_token_art(base, symbol):
    art_path = _find_token_art(symbol)
    if not art_path:
        return

    art = Image.open(art_path).convert("RGBA")
    art = ImageOps.fit(art, (128, 128), method=Image.Resampling.LANCZOS)

    # Circular crop inside the generic asset-logo ring.
    mask = Image.new("L", (128, 128), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, 127, 127), fill=255)

    base.paste(art, (672, 92), mask)


def render_report(snap, bottom_line, output_path=None, template_path=None):
    template_path = Path(template_path or DEFAULT_TEMPLATE)
    if not template_path.exists():
        raise FileNotFoundError(
            f"Template not found: {template_path}\n"
            "Put liquidity_scout_x1_asset_template.png in graphics/templates/."
        )

    image = Image.open(template_path).convert("RGB")
    if image.size != CANVAS:
        image = image.resize(CANVAS, Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(image)

    symbol = str(snap.get("symbol") or snap.get("title") or "ASSET").upper()
    token_address = str(snap.get("token_address") or "N/A")
    pool_name = str(snap.get("pool") or "N/A")
    pool_address = str(snap.get("pool_address") or "N/A")

    # Clear and rewrite asset identity.
    _erase(draw, (836, 82, 1485, 142))
    _write_value(draw, (846, 90), symbol, 620, 47, WHITE, True)

    _erase(draw, (920, 148, 1470, 182))
    _write_value(draw, (925, 153), token_address, 535, 18, WHITE)

    _erase(draw, (920, 190, 1470, 224))
    pool_text = f"{pool_name} — {pool_address}"
    _write_value(draw, (925, 195), pool_text, 535, 17, WHITE)

    # Clear / write metric values.
    metric_specs = [
        ((945, 243, 1050, 285), (950, 248), snap.get("price", "N/A"), 100, WHITE),
        ((1330, 243, 1465, 285), (1340, 248), snap.get("age", "N/A"), 120, WHITE),
        ((955, 289, 1050, 330), (965, 294), _int(snap.get("holders")), 80, WHITE),
        ((1320, 289, 1465, 330), (1330, 294), _int(snap.get("txns24")), 125, WHITE),
        ((930, 333, 1050, 376), (940, 339), _money(snap.get("vol24")), 105, WHITE),
        ((1315, 333, 1465, 376), (1325, 339), _pct(snap.get("change1")), 130,
         GREEN if float(snap.get("change1") or 0) >= 0 else RED),
        ((930, 378, 1050, 421), (940, 384), _pct(snap.get("change24")), 105,
         GREEN if float(snap.get("change24") or 0) >= 0 else RED),
        ((930, 423, 1050, 466), (940, 429), _money(snap.get("liquidity")), 105, WHITE),
        ((930, 468, 1050, 508), (940, 474), _money(snap.get("market_cap")), 105, WHITE),
    ]

    for box, pos, value, width, color in metric_specs:
        _erase(draw, box)
        _write_value(draw, pos, value, width, 23, color, False)

    # Safety metric in table.
    grade, score = _safety_parts(snap.get("safety"))
    safety_text = grade + (f" ({score})" if score else "")
    _erase(draw, (1320, 378, 1472, 423))
    _write_value(draw, (1330, 384), safety_text, 135, 22, GREEN, True)

    # Safety shield panel.
    _erase(draw, (1312, 590, 1455, 741))
    _write_value(draw, (1350, 606), grade, 70, 62, GREEN, True)
    score_display = score or "N/A"
    _write_value(draw, (1335, 681), score_display, 105, 22, WHITE, True)

    # Bottom line.
    _erase(draw, (736, 810, 1465, 860))
    body_font = _font(18, False)
    lines = _wrap_text(draw, bottom_line, 700, body_font, max_lines=2)
    y = 812
    for line in lines:
        draw.text((744, y), line, font=body_font, fill=WHITE)
        y += 24

    # Optional token artwork.
    _place_token_art(image, symbol)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / f"{symbol}_report.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image.save(output_path, "PNG", optimize=True)
    return output_path
