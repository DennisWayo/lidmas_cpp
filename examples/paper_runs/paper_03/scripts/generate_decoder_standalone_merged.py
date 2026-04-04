#!/usr/bin/env python3
"""Merge the four standalone decoder visuals into one publication-ready figure."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2460, 1400
BG = (255, 255, 255)
TEXT = (29, 33, 39)
SUBTEXT = (88, 96, 106)
BORDER = (211, 217, 226)

STYLE = {
    "MWPM": ((220, 234, 251), (38, 104, 190)),
    "Union-Find": ((233, 245, 255), (49, 117, 203)),
    "Belief Propagation": ((255, 236, 239), (183, 42, 64)),
    "Neural-MWPM": ((236, 249, 240), (20, 128, 66)),
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


def paste_fit(
    base: Image.Image,
    img: Image.Image,
    box: tuple[int, int, int, int],
    max_pad: int = 14,
) -> None:
    x0, y0, x1, y1 = box
    bw = max(1, x1 - x0 - 2 * max_pad)
    bh = max(1, y1 - y0 - 2 * max_pad)
    scale = min(bw / img.width, bh / img.height)
    nw = max(1, int(img.width * scale))
    nh = max(1, int(img.height * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    px = x0 + (x1 - x0 - nw) // 2
    py = y0 + (y1 - y0 - nh) // 2
    if resized.mode == "RGBA":
        base.paste(resized, (px, py), resized)
    else:
        base.paste(resized, (px, py))


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[3]
    paper_root = script_dir.parent
    talk_assets = repo_root / "talk_assets"

    sources = [
        ("MWPM", talk_assets / "decoder_icon_mwpm.png"),
        ("Union-Find", talk_assets / "decoder_icon_union_find.png"),
        ("Belief Propagation", talk_assets / "decoder_icon_bp.png"),
        ("Neural-MWPM", talk_assets / "decoder_icon_neural_mwpm.png"),
    ]

    missing = [label for label, path in sources if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing decoder source files for: {', '.join(missing)}")

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    f_h2 = load_font(28, bold=True)
    f_small = load_font(21, bold=False)

    margin_x = 78
    top = 58
    gap = 26
    card_w = (W - 2 * margin_x - gap) // 2
    card_h = 620

    for idx, (label, path) in enumerate(sources):
        r = idx // 2
        c = idx % 2
        x0 = margin_x + c * (card_w + gap)
        y0 = top + r * (card_h + gap)
        x1 = x0 + card_w
        y1 = y0 + card_h
        fill, stroke = STYLE[label]

        draw.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=(255, 255, 255), outline=BORDER, width=3)
        draw.rounded_rectangle((x0, y0, x1, y0 + 58), radius=18, fill=fill, outline=fill, width=0)
        draw.rectangle((x0, y0 + 40, x1, y0 + 58), fill=fill, outline=fill)
        draw.text((x0 + 18, y0 + 14), label, fill=stroke, font=f_h2)

        panel_box = (x0 + 16, y0 + 76, x1 - 16, y1 - 18)
        draw.rounded_rectangle(panel_box, radius=12, fill=(255, 255, 255), outline=BORDER, width=2)
        src = Image.open(path).convert("RGBA")
        paste_fit(image, src, panel_box)

    out_png = paper_root / "figure_decoder_standalone_merged.png"
    out_pdf = paper_root / "figure_decoder_standalone_merged.pdf"
    image.save(out_png, "PNG")
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
