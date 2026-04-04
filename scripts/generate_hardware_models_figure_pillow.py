#!/usr/bin/env python3
"""Generate a simple comparison figure for Pauli baseline vs digitized GKP hardware."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2200, 1220
BG = (255, 255, 255)
TEXT = (28, 28, 28)
SUBTEXT = (80, 80, 80)
ACCENT = (37, 99, 235)
CARD_BG = (250, 252, 255)
CARD_BORDER = (206, 214, 226)
GRID = (201, 210, 225)
QUBIT = (255, 255, 255)
QUBIT_EDGE = (55, 65, 81)
ERR = (230, 57, 70)
PAULI = (44, 123, 229)
GKP = (22, 163, 74)
DIGI = (245, 158, 11)


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


def draw_arrow(draw: ImageDraw.ImageDraw, p0: tuple[int, int], p1: tuple[int, int], color=(40, 40, 40), width: int = 4, head: int = 14) -> None:
    draw.line((p0[0], p0[1], p1[0], p1[1]), fill=color, width=width)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    h0 = (int(p1[0] - ux * head + px * (head * 0.55)), int(p1[1] - uy * head + py * (head * 0.55)))
    h1 = (int(p1[0] - ux * head - px * (head * 0.55)), int(p1[1] - uy * head - py * (head * 0.55)))
    draw.polygon([p1, h0, h1], fill=color)


def draw_panel_frame(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, subtitle: str, f_h2, f_body) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=22, fill=CARD_BG, outline=CARD_BORDER, width=3)
    draw.text((x0 + 24, y0 + 18), title, fill=TEXT, font=f_h2)
    draw.text((x0 + 24, y0 + 64), subtitle, fill=SUBTEXT, font=f_body)


def draw_pauli_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_body, f_small) -> None:
    x0, y0, x1, y1 = box
    gx0, gy0 = x0 + 60, y0 + 130
    cell = 78
    n = 5

    # Grid and qubits.
    for i in range(n):
        for j in range(n):
            cx, cy = gx0 + i * cell, gy0 + j * cell
            if i < n - 1:
                draw.line((cx, cy, cx + cell, cy), fill=GRID, width=3)
            if j < n - 1:
                draw.line((cx, cy, cx, cy + cell), fill=GRID, width=3)
            draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=QUBIT, outline=QUBIT_EDGE, width=3)

    # Inject sample Pauli errors.
    sample = [(1, 1, "X"), (3, 2, "Z"), (2, 4, "Y")]
    for i, j, label in sample:
        cx, cy = gx0 + i * cell, gy0 + j * cell
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(255, 241, 242), outline=ERR, width=3)
        draw.text((cx - 6, cy - 10), label, fill=ERR, font=f_body)

    draw.text((gx0, gy0 + n * cell + 20), "Discrete qubits + Pauli channel", fill=PAULI, font=f_body)
    draw.text((gx0, gy0 + n * cell + 52), "Sampled X / Y / Z flips", fill=SUBTEXT, font=f_small)


def draw_oscillator(draw: ImageDraw.ImageDraw, center: tuple[int, int], r: int, color) -> None:
    cx, cy = center
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=3, fill=(238, 252, 242))
    draw.arc((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8), start=25, end=335, fill=color, width=2)
    draw.line((cx - r + 15, cy, cx + r - 15, cy), fill=color, width=2)
    draw.line((cx, cy - r + 15, cx, cy + r - 15), fill=color, width=2)


def draw_gkp_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_body, f_small) -> None:
    x0, y0, x1, y1 = box
    # Three-step GKP-to-binary pipeline.
    inner_left = x0 + 72
    inner_right = x1 - 72
    top = y0 + 170
    bottom = y0 + 490
    gap = 24
    step_w = int((inner_right - inner_left - 2 * gap) / 3)
    step1 = (inner_left, top, inner_left + step_w, bottom)
    step2 = (step1[2] + gap, top, step1[2] + gap + step_w, bottom)
    step3 = (step2[2] + gap, top, step2[2] + gap + step_w, bottom)

    draw.rounded_rectangle(step1, radius=16, fill=(236, 253, 245), outline=GKP, width=3)
    draw.rounded_rectangle(step2, radius=16, fill=(255, 251, 235), outline=DIGI, width=3)
    draw.rounded_rectangle(step3, radius=16, fill=(239, 246, 255), outline=PAULI, width=3)

    draw.text((step1[0] + 12, step1[1] + 12), "Step 1: CV noise", fill=GKP, font=f_small)
    draw.text((step2[0] + 12, step2[1] + 12), "Step 2: Digitize", fill=DIGI, font=f_small)
    draw.text((step3[0] + 12, step3[1] + 12), "Step 3: Bits", fill=PAULI, font=f_small)

    # Step 1: phase-space lattice concept + displacement sample.
    ps_x0, ps_y0, ps_x1, ps_y1 = step1[0] + 18, step1[1] + 60, step1[2] - 18, step1[3] - 44
    draw.rectangle((ps_x0, ps_y0, ps_x1, ps_y1), fill=(247, 255, 249), outline=(166, 227, 189), width=2)
    cx = (ps_x0 + ps_x1) // 2
    cy = (ps_y0 + ps_y1) // 2
    for k in range(-2, 3):
        x = cx + k * 36
        y = cy + k * 28
        draw.line((x, ps_y0 + 8, x, ps_y1 - 8), fill=(204, 232, 215), width=1)
        draw.line((ps_x0 + 8, y, ps_x1 - 8, y), fill=(204, 232, 215), width=1)
    for i in range(-2, 3):
        for j in range(-2, 3):
            px = cx + i * 36
            py = cy + j * 28
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=GKP, outline=GKP)
    p0 = (cx, cy)
    p1 = (cx + 38, cy - 24)
    draw.ellipse((p0[0] - 6, p0[1] - 6, p0[0] + 6, p0[1] + 6), fill=(255, 255, 255), outline=(16, 120, 53), width=2)
    draw.ellipse((p1[0] - 7, p1[1] - 7, p1[0] + 7, p1[1] + 7), fill=(255, 241, 242), outline=ERR, width=2)
    draw_arrow(draw, p0, (p1[0] - 8, p1[1] + 5), color=ERR, width=3, head=10)
    draw.text((ps_x0 + 10, ps_y1 + 6), "dq, dp ~ N(0, sigma^2)", fill=SUBTEXT, font=f_small)

    # Step 2: slicing/rounding into bins.
    dg_x0, dg_y0, dg_x1, dg_y1 = step2[0] + 20, step2[1] + 78, step2[2] - 20, step2[3] - 70
    draw.rectangle((dg_x0, dg_y0, dg_x1, dg_y1), fill=(255, 255, 247), outline=(245, 195, 91), width=2)
    midy = (dg_y0 + dg_y1) // 2
    draw.line((dg_x0 + 12, midy, dg_x1 - 12, midy), fill=(173, 116, 0), width=2)
    for b in (0.25, 0.5, 0.75):
        bx = int(dg_x0 + (dg_x1 - dg_x0) * b)
        draw.line((bx, dg_y0 + 12, bx, dg_y1 - 12), fill=(240, 191, 84), width=2)
    sample_x = int(dg_x0 + (dg_x1 - dg_x0) * 0.62)
    target_x = int(dg_x0 + (dg_x1 - dg_x0) * 0.75)
    draw.ellipse((sample_x - 6, midy - 6, sample_x + 6, midy + 6), fill=ERR, outline=ERR)
    draw_arrow(draw, (sample_x + 8, midy - 18), (target_x - 8, midy - 18), color=DIGI, width=3, head=10)
    draw.text((dg_x0 + 8, dg_y1 + 8), "round to nearest bin", fill=SUBTEXT, font=f_small)

    # Step 3: binary events for decoder input.
    bx0, by0, bx1, by1 = step3[0] + 16, step3[1] + 74, step3[2] - 16, step3[3] - 64
    draw.rectangle((bx0, by0, bx1, by1), fill=(247, 251, 255), outline=(152, 199, 246), width=2)
    draw.text((bx0 + 10, by0 + 10), "X_event = 1", fill=PAULI, font=f_body)
    draw.text((bx0 + 10, by0 + 44), "Z_event = 0", fill=PAULI, font=f_body)
    draw.text((bx0 + 10, by0 + 78), "bits: 1 0 1 0 ...", fill=(55, 65, 81), font=f_small)
    draw.text((bx0 + 10, by0 + 106), "to decoder stream", fill=SUBTEXT, font=f_small)

    # Arrows between steps.
    draw_arrow(
        draw,
        (step1[2] + 10, (step1[1] + step1[3]) // 2),
        (step2[0] - 10, (step2[1] + step2[3]) // 2),
        color=(64, 64, 64),
    )
    draw_arrow(
        draw,
        (step2[2] + 10, (step2[1] + step2[3]) // 2),
        (step3[0] - 10, (step3[1] + step3[3]) // 2),
        color=(64, 64, 64),
    )

    # Channel parameters strip.
    chip_y0 = y0 + 528
    chip_y1 = chip_y0 + 46
    chips = [
        ("sigma", GKP, (x0 + 60, chip_y0, x0 + 220, chip_y1)),
        ("p_gate", PAULI, (x0 + 236, chip_y0, x0 + 406, chip_y1)),
        ("p_meas", PAULI, (x0 + 422, chip_y0, x0 + 592, chip_y1)),
        ("p_idle", PAULI, (x0 + 608, chip_y0, x0 + 768, chip_y1)),
        ("p_loss", PAULI, (x0 + 784, chip_y0, x0 + 944, chip_y1)),
    ]
    for label, clr, cb in chips:
        draw.rounded_rectangle(cb, radius=12, fill=(255, 255, 255), outline=clr, width=2)
        draw.text((cb[0] + 14, cb[1] + 11), label, fill=clr, font=f_small)

    draw.text((x0 + 60, y0 + 600), "Hardware-facing assumption: continuous displacement noise mapped to discrete decoder events.", fill=SUBTEXT, font=f_small)


def draw_legend(draw: ImageDraw.ImageDraw, f_body) -> None:
    y = H - 110
    x = 180
    gap = 460

    draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=QUBIT, outline=QUBIT_EDGE, width=3)
    draw.text((x + 20, y - 12), "Physical qubit", fill=TEXT, font=f_body)

    x2 = x + gap
    draw.ellipse((x2 - 11, y - 11, x2 + 11, y + 11), fill=(238, 252, 242), outline=GKP, width=3)
    draw.text((x2 + 20, y - 12), "Bosonic mode", fill=TEXT, font=f_body)

    x3 = x2 + gap
    draw.rectangle((x3 - 11, y - 11, x3 + 11, y + 11), fill=(255, 251, 235), outline=DIGI, width=3)
    draw.text((x3 + 20, y - 12), "Digitization stage", fill=TEXT, font=f_body)


def main() -> None:
    out_dir = Path("talk_assets")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_base = out_dir / "hardware_models_pauli_vs_gkp"

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_title = load_font(56, bold=True)
    f_sub = load_font(24, bold=False)
    f_h2 = load_font(36, bold=True)
    f_body = load_font(24, bold=False)
    f_small = load_font(21, bold=False)

    draw.rectangle((86, 26, 2116, 32), fill=ACCENT)
    draw.text((86, 46), "Noise/Hardware Representation Used in This Study", fill=TEXT, font=f_title)
    draw.text((86, 114), "Left: Pauli baseline model | Right: digitized native GKP hardware-facing model", fill=SUBTEXT, font=f_sub)

    left = (86, 180, 1060, 1000)
    right = (1140, 180, 2114, 1000)

    draw_panel_frame(
        draw,
        left,
        "Pauli Baseline (reference model)",
        "Discrete qubit lattice with sampled X/Y/Z errors",
        f_h2,
        f_body,
    )
    draw_panel_frame(
        draw,
        right,
        "Digitized Native GKP (hardware-facing model)",
        "CV displacement noise then digitization to bits",
        f_h2,
        f_body,
    )

    draw_pauli_panel(draw, left, f_body, f_small)
    draw_gkp_panel(draw, right, f_body, f_small)
    draw_legend(draw, f_body)

    image.save(out_base.with_suffix(".png"))
    image.save(out_base.with_suffix(".pdf"), "PDF", resolution=300.0)
    print(f"Wrote {out_base.with_suffix('.png')}")
    print(f"Wrote {out_base.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
