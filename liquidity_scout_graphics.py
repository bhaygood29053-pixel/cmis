"""
Liquidity Scout dynamic graphics renderer.

Creates 1200x675 PNG asset cards from VERIFIED XDEX snapshot data.
No market data is fetched here; this module only renders values passed in.
"""

from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1200
HEIGHT = 675


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _fit_text(draw, text, max_width, size=24, bold=False, min_size=12):
    text = str(text)
    while size >= min_size:
        font = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        size -= 1
    return _font(min_size, bold)


def _short(value, left=8, right=8):
    value = str(value or "N/A")
    if value == "N/A" or len(value) <= left + right + 3:
        return value
    return f"{value[:left]}…{value[-right:]}"


def _metric(draw, x, y, w, h, label, value):
    # Card background/border
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=18,
        fill=(20, 29, 47),
        outline=(55, 73, 101),
        width=2,
    )
    label_font = _font(18, False)
    value_font = _fit_text(draw, value, w - 30, size=28, bold=True, min_size=17)

    draw.text((x + 16, y + 14), label.upper(), font=label_font, fill=(150, 164, 184))
    draw.text((x + 16, y + 48), str(value), font=value_font, fill=(240, 244, 250))


def render_asset_card(
    snap: dict,
    output_path,
    fields: Optional[Iterable[str]] = None,
    avatar_path: Optional[str] = None,
    subtitle: Optional[str] = None,
):
    """
    Render a Liquidity Scout asset graphic.

    snap expects keys used by moltgrid_signal_v12:
      symbol, title, token_address, pool, pool_address, price, age,
      holders, txns24, vol24, change1, change24, liquidity,
      market_cap, safety.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (WIDTH, HEIGHT), (9, 15, 27))
    draw = ImageDraw.Draw(img)

    # Header band
    draw.rectangle((0, 0, WIDTH, 115), fill=(13, 22, 38))
    draw.text((42, 24), "LIQUIDITY SCOUT", font=_font(27, True), fill=(234, 240, 248))

    symbol = str(snap.get("symbol") or snap.get("title") or "ASSET")
    pool = str(snap.get("pool") or "XDEX")
    title = f"{symbol}  •  {pool}"
    title_font = _fit_text(draw, title, 760, 38, True, 24)
    draw.text((42, 58), title, font=title_font, fill=(255, 255, 255))

    if subtitle:
        subfont = _fit_text(draw, subtitle, 350, 18, False, 13)
        draw.text((810, 70), subtitle, font=subfont, fill=(171, 185, 205))

    # Optional avatar on right.
    if avatar_path and Path(avatar_path).exists():
        try:
            avatar = Image.open(avatar_path).convert("RGB")
            avatar.thumbnail((92, 92))
            ax = WIDTH - avatar.width - 38
            ay = 12
            img.paste(avatar, (ax, ay))
        except Exception:
            pass

    metrics = {
        "price": ("Price", snap.get("price", "N/A")),
        "age": ("Age", snap.get("age", "N/A")),
        "holders": ("Holders", f"{int(snap.get('holders', 0)):,}"),
        "txns24": ("Txns 24h", f"{int(snap.get('txns24', 0)):,}"),
        "volume24": ("Volume 24h", _money(snap.get("vol24", 0))),
        "change1h": ("Change 1h", _pct(snap.get("change1", 0))),
        "change24h": ("Change 24h", _pct(snap.get("change24", 0))),
        "liquidity": ("Liquidity", _money(snap.get("liquidity", 0))),
        "market_cap": ("Market Cap", _money(snap.get("market_cap", 0))),
        "safety": ("Safety", snap.get("safety", "N/A")),
    }

    all_order = [
        "price", "age", "holders", "txns24", "volume24",
        "change1h", "change24h", "liquidity", "market_cap", "safety",
    ]

    selected = list(fields or all_order)
    selected = [f for f in all_order if f in selected]
    if not selected:
        selected = all_order

    # For a specific one-field question, still make a visually useful card
    # with the requested metric emphasized.
    if len(selected) <= 2:
        card_y = 150
        card_w = 520 if len(selected) == 1 else 510
        gap = 22
        total_w = len(selected) * card_w + max(0, len(selected) - 1) * gap
        start_x = (WIDTH - total_w) // 2
        for i, key in enumerate(selected):
            label, value = metrics[key]
            _metric(draw, start_x + i * (card_w + gap), card_y, card_w, 145, label, value)
        metrics_bottom = 320
    else:
        cols = 5
        gap = 14
        card_w = (WIDTH - 84 - gap * (cols - 1)) // cols
        card_h = 126
        start_x = 42
        start_y = 142
        for idx, key in enumerate(selected[:10]):
            row = idx // cols
            col = idx % cols
            x = start_x + col * (card_w + gap)
            y = start_y + row * (card_h + gap)
            label, value = metrics[key]
            _metric(draw, x, y, card_w, card_h, label, value)
        metrics_bottom = start_y + ((len(selected[:10]) - 1) // cols + 1) * (card_h + gap)

    # Identity footer: addresses are mandatory.
    footer_y = max(metrics_bottom + 20, 455)
    draw.rounded_rectangle(
        (42, footer_y, WIDTH - 42, HEIGHT - 38),
        radius=18,
        fill=(13, 22, 38),
        outline=(55, 73, 101),
        width=2,
    )

    token_address = str(snap.get("token_address") or "N/A")
    pool_address = str(snap.get("pool_address") or "N/A")

    draw.text((62, footer_y + 20), "TOKEN ADDRESS", font=_font(16, False), fill=(150, 164, 184))
    token_font = _fit_text(draw, token_address, WIDTH - 125, 19, False, 12)
    draw.text((62, footer_y + 46), token_address, font=token_font, fill=(236, 240, 247))

    draw.text((62, footer_y + 82), "POOL ADDRESS", font=_font(16, False), fill=(150, 164, 184))
    pool_font = _fit_text(draw, pool_address, WIDTH - 125, 19, False, 12)
    draw.text((62, footer_y + 108), pool_address, font=pool_font, fill=(236, 240, 247))

    draw.text(
        (42, HEIGHT - 26),
        "XDEX data • Liquidity Scout",
        font=_font(13, False),
        fill=(113, 128, 150),
    )

    img.save(output_path, "PNG", optimize=True)
    return str(output_path)


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
