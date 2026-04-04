#!/usr/bin/env python3
"""Generate concept-3 standalone merged decoder figure for paper_03."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2520, 1460
BG = (255, 255, 255)
TEXT = (30, 34, 39)
SUBTEXT = (96, 104, 114)
CARD_EDGE = (212, 218, 227)


DECODER_SPEC = {
    "MWPM": {
        "subtitle": "matching graph policy",
        "accent": (43, 112, 203),
        "soft": (236, 246, 255),
        "icon": "decoder_icon_mwpm.png",
    },
    "Union-Find": {
        "subtitle": "cluster growth policy",
        "accent": (51, 129, 219),
        "soft": (237, 248, 255),
        "icon": "decoder_icon_union_find.png",
    },
    "Belief Propagation": {
        "subtitle": "message passing policy",
        "accent": (196, 52, 78),
        "soft": (255, 238, 243),
        "icon": "decoder_icon_bp.png",
    },
    "Neural-MWPM": {
        "subtitle": "learned guidance policy",
        "accent": (22, 141, 74),
        "soft": (236, 250, 242),
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
    """Prevent right-edge clipping in the legacy neural icon caption."""
    out = icon.copy().convert("RGBA")
    draw = ImageDraw.Draw(out)
    draw.rectangle((320, 74, 560, 128), fill=(232, 233, 235, 255), outline=None)
    draw.text((332, 86), "NN -> MWPM", fill=(74, 74, 74, 255), font=load_font(28))
    return out


def draw_corner_accent(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], accent: tuple[int, int, int]) -> None:
    x0, y0, _, _ = box
    draw.polygon([(x0 + 2, y0 + 2), (x0 + 132, y0 + 2), (x0 + 2, y0 + 132)], fill=accent)


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
    draw.rounded_rectangle(box, radius=20, fill=(255, 255, 255), outline=CARD_EDGE, width=3)
    draw_corner_accent(draw, box, accent)

    # Header block
    draw.rounded_rectangle((x0 + 36, y0 + 24, x1 - 28, y0 + 112), radius=14, fill=(250, 251, 253), outline=(227, 231, 238), width=2)
    draw.text((x0 + 52, y0 + 40), label, fill=TEXT, font=f_title)
    draw.text((x0 + 52, y0 + 76), subtitle, fill=SUBTEXT, font=f_sub)

    # Main visual block
    vis_box = (x0 + 30, y0 + 132, x1 - 30, y1 - 74)
    draw.rounded_rectangle(vis_box, radius=14, fill=(249, 251, 255), outline=(222, 228, 238), width=2)

    # tiny background dots for a different look
    dot_color = (234, 238, 244)
    for yy in range(vis_box[1] + 12, vis_box[3] - 8, 24):
        for xx in range(vis_box[0] + 12, vis_box[2] - 8, 24):
            draw.ellipse((xx, yy, xx + 2, yy + 2), fill=dot_color, outline=dot_color)

    paste_fit(base, icon, (vis_box[0] + 10, vis_box[1] + 10, vis_box[2] - 10, vis_box[3] - 10))

    # Bottom chips
    chip_y0 = y1 - 56
    chip_y1 = chip_y0 + 32
    chip1 = (x0 + 30, chip_y0, x0 + 210, chip_y1)
    chip2 = (x0 + 220, chip_y0, x0 + 430, chip_y1)
    draw.rounded_rectangle(chip1, radius=11, fill=soft, outline=accent, width=2)
    draw.text((chip1[0] + 10, chip1[1] + 8), "decoder engine", fill=accent, font=f_chip)
    draw.rounded_rectangle(chip2, radius=11, fill=(248, 250, 253), outline=(210, 218, 229), width=2)
    draw.text((chip2[0] + 10, chip2[1] + 8), "fixed input contract", fill=SUBTEXT, font=f_chip)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    paper_root = script_dir.parent
    repo_root = script_dir.parents[3]
    icon_root = repo_root / "talk_assets"

    order = ["MWPM", "Union-Find", "Belief Propagation", "Neural-MWPM"]
    icons: dict[str, Image.Image] = {}
    for label in order:
        p = icon_root / DECODER_SPEC[label]["icon"]
        if not p.exists():
            raise FileNotFoundError(f"Missing icon: {p}")
        im = Image.open(p).convert("RGBA")
        if label == "Neural-MWPM":
            im = patch_neural_icon(im)
        icons[label] = im

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_title = load_font(40, bold=True)
    f_sub = load_font(24)
    f_chip = load_font(19)

    margin_x = 66
    margin_y = 64
    gap_x = 24
    gap_y = 24
    card_w = (W - 2 * margin_x - gap_x) // 2
    card_h = (H - 2 * margin_y - gap_y) // 2

    for idx, label in enumerate(order):
        r = idx // 2
        c = idx % 2
        x0 = margin_x + c * (card_w + gap_x)
        y0 = margin_y + r * (card_h + gap_y)
        x1 = x0 + card_w
        y1 = y0 + card_h
        spec = DECODER_SPEC[label]
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

    out_png = paper_root / "figure_decoder_standalone_merged_concept3.png"
    out_pdf = paper_root / "figure_decoder_standalone_merged_concept3.pdf"
    image.save(out_png, "PNG")
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
