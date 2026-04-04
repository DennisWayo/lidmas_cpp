#!/usr/bin/env python3
"""Generate concept-2 standalone merged decoder figure for paper_03."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2520, 1020
BG = (255, 255, 255)
TEXT = (28, 32, 38)
SUBTEXT = (92, 99, 108)
CARD_BORDER = (214, 220, 228)
PANEL_BG = (252, 253, 255)

DECODER_STYLE = {
    "MWPM": {
        "subtitle": "matching graph policy",
        "accent": (39, 113, 204),
        "soft": (235, 245, 255),
        "icon": "decoder_icon_mwpm.png",
    },
    "Union-Find": {
        "subtitle": "cluster-growth policy",
        "accent": (58, 124, 205),
        "soft": (237, 246, 255),
        "icon": "decoder_icon_union_find.png",
    },
    "Belief Propagation": {
        "subtitle": "message-passing policy",
        "accent": (191, 53, 75),
        "soft": (255, 239, 243),
        "icon": "decoder_icon_bp.png",
    },
    "Neural-MWPM": {
        "subtitle": "learned-guidance policy",
        "accent": (22, 134, 72),
        "soft": (236, 249, 241),
        "icon": "decoder_icon_neural_mwpm.png",
    },
}


def load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            ]
        )
    else:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            ]
        )
    for p in candidates:
        try:
            return ImageFont.truetype(p, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def paste_fit(base: Image.Image, src: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)
    scale = min(bw / src.width, bh / src.height)
    nw = max(1, int(src.width * scale))
    nh = max(1, int(src.height * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    px = x0 + (bw - nw) // 2
    py = y0 + (bh - nh) // 2
    if resized.mode == "RGBA":
        base.paste(resized, (px, py), resized)
    else:
        base.paste(resized, (px, py))


def patch_neural_icon(icon: Image.Image) -> Image.Image:
    """Fix clipped top-right label in the legacy neural icon."""
    patched = icon.copy().convert("RGBA")
    draw = ImageDraw.Draw(patched)
    # Overpaint only the problematic area and rewrite a shorter label.
    draw.rectangle((320, 74, 560, 128), fill=(232, 233, 235, 255), outline=None)
    f = load_font(28, bold=False)
    draw.text((332, 86), "NN -> MWPM", fill=(74, 74, 74, 255), font=f)
    return patched


def draw_card(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    subtitle: str,
    accent: tuple[int, int, int],
    soft: tuple[int, int, int],
    icon: Image.Image,
    f_title,
    f_sub,
    f_chip,
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255), outline=CARD_BORDER, width=3)

    # Left accent rail
    draw.rounded_rectangle((x0 + 8, y0 + 8, x0 + 18, y1 - 8), radius=6, fill=accent, outline=accent, width=0)

    draw.text((x0 + 34, y0 + 20), label, fill=TEXT, font=f_title)
    draw.text((x0 + 34, y0 + 56), subtitle, fill=SUBTEXT, font=f_sub)

    image_box = (x0 + 22, y0 + 92, x1 - 22, y1 - 86)
    draw.rounded_rectangle(image_box, radius=12, fill=PANEL_BG, outline=CARD_BORDER, width=2)
    paste_fit(base, icon, (image_box[0] + 8, image_box[1] + 8, image_box[2] - 8, image_box[3] - 8))

    chip_h = 30
    chip_y0 = y1 - 52
    chip_y1 = chip_y0 + chip_h
    chip_x0 = x0 + 22
    chip_x1 = chip_x0 + 188
    draw.rounded_rectangle((chip_x0, chip_y0, chip_x1, chip_y1), radius=10, fill=soft, outline=accent, width=2)
    draw.text((chip_x0 + 10, chip_y0 + 7), "decoder engine", fill=accent, font=f_chip)

    chip2_x0 = chip_x1 + 10
    chip2_x1 = chip2_x0 + 208
    draw.rounded_rectangle((chip2_x0, chip_y0, chip2_x1, chip_y1), radius=10, fill=(248, 250, 253), outline=CARD_BORDER, width=2)
    draw.text((chip2_x0 + 10, chip_y0 + 7), "swappable policy", fill=SUBTEXT, font=f_chip)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    paper_root = script_dir.parent
    repo_root = script_dir.parents[3]
    icon_root = repo_root / "talk_assets"

    order = ["MWPM", "Union-Find", "Belief Propagation", "Neural-MWPM"]
    icons: dict[str, Image.Image] = {}
    for label in order:
        p = icon_root / DECODER_STYLE[label]["icon"]
        if not p.exists():
            raise FileNotFoundError(f"Missing icon: {p}")
        src = Image.open(p).convert("RGBA")
        if label == "Neural-MWPM":
            src = patch_neural_icon(src)
        icons[label] = src

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_title = load_font(32, bold=True)
    f_sub = load_font(21, bold=False)
    f_chip = load_font(18, bold=False)

    margin_x = 62
    margin_y = 64
    gap = 22
    card_w = (W - 2 * margin_x - 3 * gap) // 4
    card_h = H - 2 * margin_y

    for idx, label in enumerate(order):
        x0 = margin_x + idx * (card_w + gap)
        y0 = margin_y
        x1 = x0 + card_w
        y1 = y0 + card_h
        spec = DECODER_STYLE[label]
        draw_card(
            image,
            draw,
            (x0, y0, x1, y1),
            label,
            str(spec["subtitle"]),
            tuple(spec["accent"]),
            tuple(spec["soft"]),
            icons[label],
            f_title,
            f_sub,
            f_chip,
        )

    out_png = paper_root / "figure_decoder_standalone_merged_concept2.png"
    out_pdf = paper_root / "figure_decoder_standalone_merged_concept2.pdf"
    image.save(out_png, "PNG")
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
