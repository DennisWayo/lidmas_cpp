#!/usr/bin/env python3
"""Generate a clean surface-code schematic using Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2200, 1220
BG = (255, 255, 255)
TEXT = (35, 35, 35)
ACCENT = (37, 99, 235)
GRID = (220, 224, 230)
DATA = (35, 35, 35)
XCHK = (44, 123, 229)
XCHK_EDGE = (22, 74, 146)
ZCHK = (245, 159, 0)
ZCHK_EDGE = (157, 101, 0)
ERR = (230, 57, 70)
ERR_EDGE = (138, 31, 41)
BOUNDARY = (105, 115, 130)


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
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_dashed_line(draw: ImageDraw.ImageDraw, p0: tuple[int, int], p1: tuple[int, int], dash: int = 10, gap: int = 7, fill=BOUNDARY, width: int = 2) -> None:
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return
    ux = dx / length
    uy = dy / length
    t = 0.0
    while t < length:
        t_end = min(t + dash, length)
        sx, sy = x0 + ux * t, y0 + uy * t
        ex, ey = x0 + ux * t_end, y0 + uy * t_end
        draw.line((sx, sy, ex, ey), fill=fill, width=width)
        t = t_end + gap


def panel_to_px(panel: tuple[int, int, int, int], d: int, gx: float, gy: float) -> tuple[int, int]:
    x0, y0, x1, y1 = panel
    pad = 86
    gw = x1 - x0 - 2 * pad
    gh = y1 - y0 - 2 * pad
    sx = x0 + pad + gx * (gw / (d - 1))
    sy = y1 - pad - gy * (gh / (d - 1))
    return int(round(sx)), int(round(sy))


def draw_panel(
    draw: ImageDraw.ImageDraw,
    panel: tuple[int, int, int, int],
    title: str,
    error_kind: str,
    d: int,
    f_title,
    f_body,
    side_label: str,
) -> None:
    x0, y0, x1, y1 = panel
    draw.rounded_rectangle((x0, y0, x1, y1), radius=22, outline=(205, 212, 222), width=2, fill=(252, 253, 255))
    tw = draw.textlength(title, font=f_title)
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + 16), title, fill=TEXT, font=f_title)

    # Boundary box.
    p_tl = panel_to_px(panel, d, -0.35, d - 1 + 0.35)
    p_tr = panel_to_px(panel, d, d - 1 + 0.35, d - 1 + 0.35)
    p_bl = panel_to_px(panel, d, -0.35, -0.35)
    p_br = panel_to_px(panel, d, d - 1 + 0.35, -0.35)
    draw_dashed_line(draw, p_tl, p_tr)
    draw_dashed_line(draw, p_tr, p_br)
    draw_dashed_line(draw, p_br, p_bl)
    draw_dashed_line(draw, p_bl, p_tl)

    top_label = "rough boundary (X)"
    side_text = "smooth (Z)"
    draw.text((int((p_bl[0] + p_br[0]) / 2 - 85), p_bl[1] + 8), top_label, fill=BOUNDARY, font=f_body)
    if side_label == "left":
        draw.text((p_tl[0] - 108, int((p_tl[1] + p_bl[1]) / 2 - 8)), side_text, fill=BOUNDARY, font=f_body)
    if side_label == "right":
        draw.text((p_tr[0] + 10, int((p_tr[1] + p_br[1]) / 2 - 8)), side_text, fill=BOUNDARY, font=f_body)

    # Data and checks.
    data_points = [(x, y) for x in range(d) for y in range(d)]
    checks: list[tuple[float, float, str]] = []
    for x in range(d - 1):
        for y in range(d - 1):
            checks.append((x + 0.5, y + 0.5, "X" if (x + y) % 2 == 0 else "Z"))

    # Coupling lines.
    for cx, cy, _ in checks:
        neighbors = [
            (cx - 0.5, cy - 0.5),
            (cx + 0.5, cy - 0.5),
            (cx - 0.5, cy + 0.5),
            (cx + 0.5, cy + 0.5),
        ]
        cpx = panel_to_px(panel, d, cx, cy)
        for nx, ny in neighbors:
            if 0 <= nx <= d - 1 and 0 <= ny <= d - 1:
                npx = panel_to_px(panel, d, nx, ny)
                draw.line((cpx[0], cpx[1], npx[0], npx[1]), fill=GRID, width=2)

    # Checks.
    for cx, cy, ctype in checks:
        px, py = panel_to_px(panel, d, cx, cy)
        r = 11
        if ctype == "X":
            draw.rectangle((px - r, py - r, px + r, py + r), fill=XCHK, outline=XCHK_EDGE, width=2)
        else:
            draw.polygon([(px, py - r), (px + r, py), (px, py + r), (px - r, py)], fill=ZCHK, outline=ZCHK_EDGE)

    # Data points.
    for dx, dy in data_points:
        px, py = panel_to_px(panel, d, dx, dy)
        r = 9
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 255), outline=DATA, width=2)

    # One injected data error at center.
    ex, ey = d // 2, d // 2
    epx, epy = panel_to_px(panel, d, ex, ey)
    draw.ellipse((epx - 12, epy - 12, epx + 12, epy + 12), fill=ERR, outline=ERR_EDGE, width=2)

    # Triggered syndrome checks.
    target = "X" if error_kind == "Z" else "Z"
    for sx in (-0.5, 0.5):
        for sy in (-0.5, 0.5):
            cx, cy = ex + sx, ey + sy
            if not (0 <= cx <= d - 1 and 0 <= cy <= d - 1):
                continue
            parity = (int(cx - 0.5) + int(cy - 0.5)) % 2
            ctype = "X" if parity == 0 else "Z"
            if ctype == target:
                px, py = panel_to_px(panel, d, cx, cy)
                rr = 18
                draw.ellipse((px - rr, py - rr, px + rr, py + rr), outline=ERR, width=4)
                draw.text((px + 13, py - 20), "s=1", fill=ERR, font=f_body)


def draw_legend(draw: ImageDraw.ImageDraw, f_body) -> None:
    y = H - 130
    x = 210
    gap = 340

    def put_data(ix: int, label: str, shape: str) -> None:
        px = x + ix * gap
        if shape == "data":
            draw.ellipse((px - 10, y - 10, px + 10, y + 10), fill=(255, 255, 255), outline=DATA, width=2)
        elif shape == "x":
            draw.rectangle((px - 10, y - 10, px + 10, y + 10), fill=XCHK, outline=XCHK_EDGE, width=2)
        elif shape == "z":
            draw.polygon([(px, y - 11), (px + 11, y), (px, y + 11), (px - 11, y)], fill=ZCHK, outline=ZCHK_EDGE)
        elif shape == "err":
            draw.ellipse((px - 11, y - 11, px + 11, y + 11), fill=ERR, outline=ERR_EDGE, width=2)
        elif shape == "trig":
            draw.ellipse((px - 14, y - 14, px + 14, y + 14), outline=ERR, width=3)
        draw.text((px + 20, y - 11), label, fill=TEXT, font=f_body)

    put_data(0, "Data qubit", "data")
    put_data(1, "X-check ancilla", "x")
    put_data(2, "Z-check ancilla", "z")
    put_data(3, "Data-qubit error", "err")
    put_data(4, "Triggered syndrome", "trig")


def main() -> None:
    out_dir = Path("talk_assets")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_base = out_dir / "surface_code_schematic_clean"

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    f_title = load_font(52, bold=True)
    f_sub = load_font(24, bold=False)
    f_panel = load_font(22, bold=True)
    f_body = load_font(20, bold=False)

    draw.text((84, 42), "Surface-Code Syndrome Intuition", fill=TEXT, font=f_title)
    draw.text(
        (84, 112),
        "Conceptual planar patch: Z errors excite X checks, and X errors excite Z checks.",
        fill=(72, 72, 72),
        font=f_sub,
    )
    draw.rectangle((84, 24, 2118, 28), fill=ACCENT)

    left_panel = (80, 170, 1060, 1010)
    right_panel = (1140, 170, 2120, 1010)
    draw_panel(
        draw,
        left_panel,
        "Phase-flip (Z) data error -> X-check syndromes",
        error_kind="Z",
        d=7,
        f_title=f_panel,
        f_body=f_body,
        side_label="left",
    )
    draw_panel(
        draw,
        right_panel,
        "Bit-flip (X) data error -> Z-check syndromes",
        error_kind="X",
        d=7,
        f_title=f_panel,
        f_body=f_body,
        side_label="right",
    )

    draw_legend(draw, f_body)

    image.save(out_base.with_suffix(".png"))
    image.save(out_base.with_suffix(".pdf"), "PDF", resolution=300.0)

    print(f"Wrote {out_base.with_suffix('.png')}")
    print(f"Wrote {out_base.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
