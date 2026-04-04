#!/usr/bin/env python3
"""Generate clean decoder-representation icons for talks."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2400, 1500
BG = (255, 255, 255)
TEXT = (30, 30, 30)
SUBTEXT = (80, 80, 80)
ACCENT = (36, 99, 235)
CARD_BG = (250, 252, 255)
CARD_BORDER = (205, 214, 228)
NODE = (255, 255, 255)
NODE_EDGE = (55, 65, 81)
EDGE = (196, 203, 214)
HILITE = (44, 123, 229)
SECOND = (22, 163, 74)
WARN = (245, 158, 11)
NEURAL = (14, 165, 233)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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


def line(draw: ImageDraw.ImageDraw, p0: tuple[int, int], p1: tuple[int, int], color=EDGE, width: int = 3) -> None:
    draw.line((p0[0], p0[1], p1[0], p1[1]), fill=color, width=width)


def circle(draw: ImageDraw.ImageDraw, c: tuple[int, int], r: int, fill=NODE, outline=NODE_EDGE, width: int = 3) -> None:
    draw.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=fill, outline=outline, width=width)


def rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=(255, 255, 255), outline=NODE_EDGE, width: int = 3, radius: int = 18) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw: ImageDraw.ImageDraw, p0: tuple[int, int], p1: tuple[int, int], color=HILITE, width: int = 4, head: int = 12) -> None:
    line(draw, p0, p1, color=color, width=width)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    h0 = (int(p1[0] - ux * head + px * (head * 0.55)), int(p1[1] - uy * head + py * (head * 0.55)))
    h1 = (int(p1[0] - ux * head - px * (head * 0.55)), int(p1[1] - uy * head - py * (head * 0.55)))
    draw.polygon([p1, h0, h1], fill=color)


def _icon_box_to_abs(box: tuple[int, int, int, int], u: float, v: float) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    return (int(x0 + (x1 - x0) * u), int(y0 + (y1 - y0) * v))


def draw_mwpm_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_small) -> None:
    pts = {
        "a": _icon_box_to_abs(box, 0.20, 0.28),
        "b": _icon_box_to_abs(box, 0.50, 0.18),
        "c": _icon_box_to_abs(box, 0.80, 0.30),
        "d": _icon_box_to_abs(box, 0.22, 0.74),
        "e": _icon_box_to_abs(box, 0.50, 0.82),
        "f": _icon_box_to_abs(box, 0.80, 0.72),
    }
    edges = [("a", "b"), ("b", "c"), ("a", "d"), ("b", "e"), ("c", "f"), ("d", "e"), ("e", "f"), ("a", "e"), ("b", "d"), ("b", "f"), ("c", "e")]
    for u, v in edges:
        line(draw, pts[u], pts[v], color=EDGE, width=3)
    match = [("a", "d"), ("b", "c"), ("e", "f")]
    for u, v in match:
        line(draw, pts[u], pts[v], color=HILITE, width=6)
        mx, my = (pts[u][0] + pts[v][0]) // 2, (pts[u][1] + pts[v][1]) // 2
        draw.text((mx + 4, my - 18), "w", fill=HILITE, font=f_small)
    for p in pts.values():
        circle(draw, p, 14, fill=NODE, outline=NODE_EDGE, width=3)


def draw_uf_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_small) -> None:
    left = {
        "n1": _icon_box_to_abs(box, 0.20, 0.24),
        "n2": _icon_box_to_abs(box, 0.34, 0.42),
        "n3": _icon_box_to_abs(box, 0.18, 0.64),
    }
    right = {
        "m1": _icon_box_to_abs(box, 0.66, 0.24),
        "m2": _icon_box_to_abs(box, 0.80, 0.42),
        "m3": _icon_box_to_abs(box, 0.64, 0.64),
    }
    root = _icon_box_to_abs(box, 0.50, 0.84)

    for a, b in [("n1", "n2"), ("n2", "n3")]:
        line(draw, left[a], left[b], color=SECOND, width=5)
    for a, b in [("m1", "m2"), ("m2", "m3")]:
        line(draw, right[a], right[b], color=WARN, width=5)

    for p in left.values():
        circle(draw, p, 13, fill=(236, 253, 245), outline=SECOND, width=3)
    for p in right.values():
        circle(draw, p, 13, fill=(255, 251, 235), outline=WARN, width=3)

    arrow(draw, _icon_box_to_abs(box, 0.38, 0.52), _icon_box_to_abs(box, 0.62, 0.52), color=HILITE, width=4, head=13)
    draw.text(_icon_box_to_abs(box, 0.45, 0.46), "union", fill=HILITE, font=f_small)

    for p in list(left.values()) + list(right.values()):
        line(draw, p, root, color=EDGE, width=2)
    circle(draw, root, 15, fill=(239, 246, 255), outline=HILITE, width=4)
    draw.text((root[0] - 10, root[1] - 9), "R", fill=HILITE, font=f_small)


def draw_bp_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_small) -> None:
    vars_pts = [_icon_box_to_abs(box, u, 0.68) for u in (0.18, 0.38, 0.58, 0.78)]
    fac_pts = [_icon_box_to_abs(box, u, 0.38) for u in (0.28, 0.48, 0.68)]
    for i, f in enumerate(fac_pts):
        line(draw, vars_pts[i], f, color=EDGE, width=3)
        line(draw, vars_pts[i + 1], f, color=EDGE, width=3)
        arrow(draw, vars_pts[i], f, color=NEURAL, width=3, head=10)
        arrow(draw, f, vars_pts[i + 1], color=NEURAL, width=3, head=10)
    for p in vars_pts:
        circle(draw, p, 13, fill=(255, 255, 255), outline=NODE_EDGE, width=3)
    for p in fac_pts:
        rect(draw, (p[0] - 12, p[1] - 12, p[0] + 12, p[1] + 12), fill=(239, 246, 255), outline=HILITE, width=3, radius=4)
    draw.text(_icon_box_to_abs(box, 0.08, 0.16), "messages pass iteratively", fill=SUBTEXT, font=f_small)


def draw_neural_mwpm_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_small) -> None:
    layers = [
        [_icon_box_to_abs(box, 0.16, v) for v in (0.30, 0.50, 0.70)],
        [_icon_box_to_abs(box, 0.34, v) for v in (0.24, 0.40, 0.56, 0.72)],
        [_icon_box_to_abs(box, 0.52, v) for v in (0.36, 0.52, 0.68)],
    ]
    for i in range(len(layers) - 1):
        for p in layers[i]:
            for q in layers[i + 1]:
                line(draw, p, q, color=(195, 229, 249), width=2)
    for lay in layers:
        for p in lay:
            circle(draw, p, 9, fill=(240, 249, 255), outline=NEURAL, width=2)

    arrow(draw, _icon_box_to_abs(box, 0.58, 0.50), _icon_box_to_abs(box, 0.70, 0.50), color=NEURAL, width=4, head=12)

    pts = {
        "a": _icon_box_to_abs(box, 0.76, 0.32),
        "b": _icon_box_to_abs(box, 0.92, 0.40),
        "c": _icon_box_to_abs(box, 0.78, 0.68),
        "d": _icon_box_to_abs(box, 0.94, 0.72),
    }
    for u, v in [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d")]:
        line(draw, pts[u], pts[v], color=EDGE, width=2)
    for u, v in [("a", "c"), ("b", "d")]:
        line(draw, pts[u], pts[v], color=HILITE, width=5)
    for p in pts.values():
        circle(draw, p, 10, fill=NODE, outline=NODE_EDGE, width=2)
    draw.text(_icon_box_to_abs(box, 0.72, 0.18), "NN guidance -> matching", fill=SUBTEXT, font=f_small)


def draw_icon_card(draw: ImageDraw.ImageDraw, card: tuple[int, int, int, int], title: str, subtitle: str, icon_fn, f_h2, f_body, f_small) -> None:
    x0, y0, x1, y1 = card
    rect(draw, card, fill=CARD_BG, outline=CARD_BORDER, width=3, radius=24)
    draw.text((x0 + 26, y0 + 20), title, fill=TEXT, font=f_h2)
    draw.text((x0 + 26, y0 + 68), subtitle, fill=SUBTEXT, font=f_body)
    icon_box = (x0 + 24, y0 + 110, x1 - 24, y1 - 28)
    icon_fn(draw, icon_box, f_small)


def export_single_icon(name: str, icon_fn, out_dir: Path, f_small) -> None:
    img = Image.new("RGBA", (560, 420), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    card = (8, 8, 552, 412)
    draw.rounded_rectangle(card, radius=20, fill=(251, 253, 255, 255), outline=(214, 222, 233, 255), width=3)
    icon_box = (32, 32, 528, 388)
    icon_fn(draw, icon_box, f_small)
    img.save(out_dir / f"{name}.png")


def main() -> None:
    out_dir = Path("talk_assets")
    out_dir.mkdir(parents=True, exist_ok=True)

    f_title = load_font(62, bold=True)
    f_sub = load_font(24, bold=False)
    f_h2 = load_font(36, bold=True)
    f_body = load_font(21, bold=False)
    f_small = load_font(18, bold=False)

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle((90, 32, 2310, 38), fill=ACCENT)
    draw.text((90, 56), "Decoder Representation Icons", fill=TEXT, font=f_title)
    draw.text(
        (90, 132),
        "Use these as conceptual visuals for MWPM, Union-Find, Belief Propagation, and Neural-guided MWPM.",
        fill=SUBTEXT,
        font=f_sub,
    )

    cards = {
        "mwpm": (90, 210, 1160, 820),
        "uf": (1240, 210, 2310, 820),
        "bp": (90, 870, 1160, 1480),
        "neural_mwpm": (1240, 870, 2310, 1480),
    }

    draw_icon_card(
        draw,
        cards["mwpm"],
        "MWPM Decoder",
        "Weighted graph matching of detection events",
        draw_mwpm_icon,
        f_h2,
        f_body,
        f_small,
    )
    draw_icon_card(
        draw,
        cards["uf"],
        "Union-Find Decoder",
        "Cluster growth and efficient component merging",
        draw_uf_icon,
        f_h2,
        f_body,
        f_small,
    )
    draw_icon_card(
        draw,
        cards["bp"],
        "Belief Propagation (BP)",
        "Iterative message passing on factor graphs",
        draw_bp_icon,
        f_h2,
        f_body,
        f_small,
    )
    draw_icon_card(
        draw,
        cards["neural_mwpm"],
        "Neural-guided MWPM",
        "Neural scoring/prior plus matching backend",
        draw_neural_mwpm_icon,
        f_h2,
        f_body,
        f_small,
    )

    panel_png = out_dir / "decoder_icons_panel.png"
    panel_pdf = out_dir / "decoder_icons_panel.pdf"
    image.save(panel_png)
    image.save(panel_pdf, "PDF", resolution=300.0)

    export_single_icon("decoder_icon_mwpm", draw_mwpm_icon, out_dir, f_small)
    export_single_icon("decoder_icon_union_find", draw_uf_icon, out_dir, f_small)
    export_single_icon("decoder_icon_bp", draw_bp_icon, out_dir, f_small)
    export_single_icon("decoder_icon_neural_mwpm", draw_neural_mwpm_icon, out_dir, f_small)

    print(f"Wrote {panel_png}")
    print(f"Wrote {panel_pdf}")
    print(f"Wrote {out_dir / 'decoder_icon_mwpm.png'}")
    print(f"Wrote {out_dir / 'decoder_icon_union_find.png'}")
    print(f"Wrote {out_dir / 'decoder_icon_bp.png'}")
    print(f"Wrote {out_dir / 'decoder_icon_neural_mwpm.png'}")


if __name__ == "__main__":
    main()
