#!/usr/bin/env python3
"""Generate a talk-ready hardware/noise representation figure with d={3,5,7} annotations."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2300, 1040
BG = (255, 255, 255)
TEXT = (28, 28, 28)
SUBTEXT = (88, 88, 88)
ACCENT = (37, 99, 235)
CARD_BG = (255, 255, 255)
CARD_BORDER = (214, 214, 214)
GRID = (202, 210, 222)
QUBIT = (255, 255, 255)
QUBIT_EDGE = (55, 65, 81)
ERR = (230, 57, 70)
PAULI = (44, 123, 229)
GKP = (22, 163, 74)
DIGI = (245, 158, 11)


@dataclass
class RunStats:
    distances: list[int]
    sigma_min: float
    sigma_max: float
    d_ler_band: dict[int, tuple[float, float]]
    p_min: float
    p_max: float
    pauli_ler_min: float
    pauli_ler_max: float


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


def draw_arrow(draw: ImageDraw.ImageDraw, p0: tuple[int, int], p1: tuple[int, int], color=(50, 50, 50), width: int = 4, head: int = 13) -> None:
    draw.line((p0[0], p0[1], p1[0], p1[1]), fill=color, width=width)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    h0 = (int(p1[0] - ux * head + px * (head * 0.55)), int(p1[1] - uy * head + py * (head * 0.55)))
    h1 = (int(p1[0] - ux * head - px * (head * 0.55)), int(p1[1] - uy * head - py * (head * 0.55)))
    draw.polygon([p1, h0, h1], fill=color)


def load_run_stats(root: Path) -> RunStats:
    gkp_table = root / "results" / "03_gkp_multidistance" / "table_gkp_multidistance.csv"
    pauli_table = root / "results" / "01_pauli_baseline" / "table_pauli_baseline.csv"

    if not gkp_table.exists():
        raise FileNotFoundError(f"Missing required table: {gkp_table}")
    if not pauli_table.exists():
        raise FileNotFoundError(f"Missing required table: {pauli_table}")

    distances: set[int] = set()
    sigma_min = 1e9
    sigma_max = -1e9
    d_ler_min: dict[int, float] = {}
    d_ler_max: dict[int, float] = {}
    with gkp_table.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = int(float(row["distance"]))
            distances.add(d)
            x_min = float(row["x_min"])
            x_max = float(row["x_max"])
            sigma_min = min(sigma_min, x_min)
            sigma_max = max(sigma_max, x_max)
            lmin = float(row["ler_min"])
            lmax = float(row["ler_max"])
            d_ler_min[d] = min(lmin, d_ler_min.get(d, 1e9))
            d_ler_max[d] = max(lmax, d_ler_max.get(d, -1e9))

    p_min = 1e9
    p_max = -1e9
    pauli_ler_min = 1e9
    pauli_ler_max = -1e9
    with pauli_table.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_min = min(p_min, float(row["x_min"]))
            p_max = max(p_max, float(row["x_max"]))
            pauli_ler_min = min(pauli_ler_min, float(row["ler_min"]))
            pauli_ler_max = max(pauli_ler_max, float(row["ler_max"]))

    ordered_d = sorted(distances)
    band = {d: (d_ler_min[d], d_ler_max[d]) for d in ordered_d}
    return RunStats(
        distances=ordered_d,
        sigma_min=sigma_min,
        sigma_max=sigma_max,
        d_ler_band=band,
        p_min=p_min,
        p_max=p_max,
        pauli_ler_min=pauli_ler_min,
        pauli_ler_max=pauli_ler_max,
    )


def draw_panel_frame(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, subtitle: str, f_h2, f_body) -> None:
    draw.rounded_rectangle(box, radius=22, fill=CARD_BG, outline=CARD_BORDER, width=3)
    x0, y0, _, _ = box
    draw.text((x0 + 24, y0 + 18), title, fill=TEXT, font=f_h2)
    draw.text((x0 + 24, y0 + 64), subtitle, fill=SUBTEXT, font=f_body)


def draw_pauli(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], stats: RunStats, f_body, f_small) -> None:
    x0, y0, x1, y1 = box
    gx0, gy0 = x0 + 62, y0 + 132
    gx1, gy1 = x1 - 62, y0 + 760
    nx, ny = 8, 8
    dx = (gx1 - gx0) / (nx - 1)
    dy = (gy1 - gy0) / (ny - 1)
    for i in range(nx):
        for j in range(ny):
            cx = int(round(gx0 + i * dx))
            cy = int(round(gy0 + j * dy))
            if i < nx - 1:
                nx2 = int(round(gx0 + (i + 1) * dx))
                draw.line((cx, cy, nx2, cy), fill=GRID, width=3)
            if j < ny - 1:
                ny2 = int(round(gy0 + (j + 1) * dy))
                draw.line((cx, cy, cx, ny2), fill=GRID, width=3)
            draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=QUBIT, outline=QUBIT_EDGE, width=3)

    for i, j, lbl in [(2, 2, "X"), (5, 3, "Z"), (3, 6, "Y")]:
        cx = int(round(gx0 + i * dx))
        cy = int(round(gy0 + j * dy))
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(255, 241, 242), outline=ERR, width=3)
        draw.text((cx - 6, cy - 10), lbl, fill=ERR, font=f_body)

    # Move annotation text below the panel to avoid crowding near the lattice bottom row.
    draw.text((gx0, y1 + 14), "Discrete qubits + sampled X/Y/Z flips", fill=PAULI, font=f_body)
    draw.text(
        (gx0, y1 + 46),
        f"run-aligned p range: {stats.p_min:.2f} to {stats.p_max:.2f}",
        fill=SUBTEXT,
        font=f_small,
    )
    draw.text(
        (gx0, y1 + 74),
        f"observed LER band: {stats.pauli_ler_min:.3f} to {stats.pauli_ler_max:.3f}",
        fill=SUBTEXT,
        font=f_small,
    )


def draw_gkp(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], stats: RunStats, f_body, f_small) -> None:
    x0, y0, x1, _ = box

    margin = 62
    gap = 34
    card_top = y0 + 232
    card_bottom = y0 + 650
    inner_w = (x1 - x0) - 2 * margin - 2 * gap
    card_w = inner_w // 3

    c1 = (x0 + margin, card_top, x0 + margin + card_w, card_bottom)
    c2 = (c1[2] + gap, card_top, c1[2] + gap + card_w, card_bottom)
    c3 = (c2[2] + gap, card_top, x1 - margin, card_bottom)

    # Stage badges
    badge_y0, badge_y1 = y0 + 194, y0 + 222
    badges = [
        (c1[0], c1[2], GKP, "1) analog CV noise"),
        (c2[0], c2[2], DIGI, "2) digitize / slice"),
        (c3[0], c3[2], PAULI, "3) binary decoder bits"),
    ]
    for bx0, bx1, clr, txt in badges:
        draw.rounded_rectangle((bx0, badge_y0, bx1, badge_y1), radius=10, fill=(255, 255, 255), outline=clr, width=2)
        draw.text((bx0 + 10, badge_y0 + 4), txt, fill=clr, font=f_small)

    # Cards
    draw.rounded_rectangle(c1, radius=16, fill=(236, 253, 245), outline=GKP, width=3)
    draw.rounded_rectangle(c2, radius=16, fill=(255, 251, 235), outline=DIGI, width=3)
    draw.rounded_rectangle(c3, radius=16, fill=(239, 246, 255), outline=PAULI, width=3)

    # Card 1 title + oscillator strip
    draw.text((c1[0] + 12, c1[1] + 10), "Analog displacement", fill=GKP, font=f_small)
    strip_y = c1[1] + 52
    osc_x = c1[0] + 18
    for i in range(4):
        cx = osc_x + i * 42
        cy = strip_y
        r = 10
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(238, 252, 242), outline=GKP, width=2)
        draw.line((cx - 5, cy, cx + 5, cy), fill=GKP, width=1)
        draw.line((cx, cy - 5, cx, cy + 5), fill=GKP, width=1)

    # Card 1 phase-space mini plot
    p1x0, p1y0, p1x1, p1y1 = c1[0] + 12, c1[1] + 74, c1[2] - 12, c1[3] - 54
    draw.rectangle((p1x0, p1y0, p1x1, p1y1), fill=(247, 255, 249), outline=(166, 227, 189), width=2)
    cx, cy = (p1x0 + p1x1) // 2, (p1y0 + p1y1) // 2
    for i in range(-3, 4):
        for j in range(-2, 3):
            gx = cx + i * 22
            gy = cy + j * 22
            draw.ellipse((gx - 2, gy - 2, gx + 2, gy + 2), fill=GKP, outline=GKP)
    a0 = (cx - 16, cy + 10)
    a1 = (cx + 22, cy - 18)
    draw.ellipse((a0[0] - 6, a0[1] - 6, a0[0] + 6, a0[1] + 6), fill=(255, 255, 255), outline=(16, 120, 53), width=2)
    draw.ellipse((a1[0] - 7, a1[1] - 7, a1[0] + 7, a1[1] + 7), fill=(255, 241, 242), outline=ERR, width=2)
    draw_arrow(draw, a0, (a1[0] - 8, a1[1] + 4), color=ERR, width=3, head=10)
    draw.text((p1x0 + 8, p1y1 + 8), "dq, dp ~ N(0, sigma^2)", fill=SUBTEXT, font=f_small)

    # Card 2 quantization
    draw.text((c2[0] + 12, c2[1] + 10), "Syndrome slicing", fill=DIGI, font=f_small)
    p2x0, p2y0, p2x1, p2y1 = c2[0] + 12, c2[1] + 52, c2[2] - 12, c2[3] - 76
    draw.rectangle((p2x0, p2y0, p2x1, p2y1), fill=(255, 255, 247), outline=(245, 195, 91), width=2)
    my = (p2y0 + p2y1) // 2
    draw.line((p2x0 + 12, my, p2x1 - 12, my), fill=(173, 116, 0), width=2)
    for frac in (0.30, 0.50, 0.70):
        vx = int(p2x0 + (p2x1 - p2x0) * frac)
        draw.line((vx, p2y0 + 10, vx, p2y1 - 10), fill=(240, 191, 84), width=2)
    dotx = int(p2x0 + (p2x1 - p2x0) * 0.62)
    draw.ellipse((dotx - 6, my - 6, dotx + 6, my + 6), fill=ERR, outline=ERR)
    draw_arrow(draw, (dotx + 8, my - 15), (int(p2x0 + (p2x1 - p2x0) * 0.70) - 8, my - 15), color=DIGI, width=3, head=10)
    draw.text((p2x0 + 8, p2y1 + 8), "nearest-bin quantization", fill=SUBTEXT, font=f_small)

    # Card 3 binary stream
    draw.text((c3[0] + 12, c3[1] + 10), "Binary decoder input", fill=PAULI, font=f_small)
    p3x0, p3y0, p3x1, p3y1 = c3[0] + 12, c3[1] + 52, c3[2] - 12, c3[3] - 86
    draw.rectangle((p3x0, p3y0, p3x1, p3y1), fill=(247, 251, 255), outline=(152, 199, 246), width=2)
    draw.text((p3x0 + 10, p3y0 + 10), "X_event = 1", fill=PAULI, font=f_body)
    draw.text((p3x0 + 10, p3y0 + 44), "Z_event = 0", fill=PAULI, font=f_body)
    bit_y = p3y0 + 92
    bit_x = p3x0 + 10
    for b in ["1", "0", "1", "0", "..."]:
        w = 24 if b != "..." else 34
        draw.rounded_rectangle((bit_x, bit_y, bit_x + w, bit_y + 24), radius=6, fill=(255, 255, 255), outline=(152, 199, 246), width=1)
        draw.text((bit_x + 7, bit_y + 3), b, fill=(55, 65, 81), font=f_small)
        bit_x += w + 8
    draw.text((p3x0 + 10, p3y1 + 10), "stream -> decoder", fill=SUBTEXT, font=f_small)

    draw_arrow(draw, (c1[2] + 6, (c1[1] + c1[3]) // 2), (c2[0] - 6, (c2[1] + c2[3]) // 2), color=(35, 35, 35), width=5, head=10)
    draw_arrow(draw, (c2[2] + 6, (c2[1] + c2[3]) // 2), (c3[0] - 6, (c3[1] + c3[3]) // 2), color=(35, 35, 35), width=5, head=10)

    # Distance chips d={3,5,7} + run-derived bands.
    chip_y0 = y0 + 694
    chip_y1 = chip_y0 + 50
    chip_w = 210
    chip_gap = 22
    start_x = x0 + 68
    draw.text((start_x, chip_y0 - 32), "run-aligned distance set and observed LER bands:", fill=SUBTEXT, font=f_small)
    for idx, d in enumerate(stats.distances):
        lx0 = start_x + idx * (chip_w + chip_gap)
        lx1 = lx0 + chip_w
        draw.rounded_rectangle((lx0, chip_y0, lx1, chip_y1), radius=12, fill=(255, 255, 255), outline=PAULI, width=2)
        lmin, lmax = stats.d_ler_band[d]
        draw.text((lx0 + 14, chip_y0 + 10), f"d={d}  LER {lmin:.2f}-{lmax:.2f}", fill=PAULI, font=f_small)

    draw.text(
        (x0 + 68, y0 + 756),
        f"sigma range in runs: {stats.sigma_min:.2f} to {stats.sigma_max:.2f} | conceptual pipeline with run-derived ranges",
        fill=SUBTEXT,
        font=f_small,
    )


def draw_legend(
    draw: ImageDraw.ImageDraw,
    left_box: tuple[int, int, int, int],
    right_box: tuple[int, int, int, int],
    f_small,
) -> None:
    # Single-row horizontal legend under the panel writeups for better readability.
    _, _, left_x1, left_y1 = left_box
    right_x0, _, _, _ = right_box
    y = left_y1 + 44
    start_x = left_x1 - 330
    gap = max(250, (right_x0 - start_x) // 3)

    def draw_item(cx: int, label: str, kind: str) -> None:
        if kind == "qubit":
            draw.ellipse((cx - 9, y - 9, cx + 9, y + 9), fill=QUBIT, outline=QUBIT_EDGE, width=2)
        elif kind == "mode":
            draw.ellipse((cx - 9, y - 9, cx + 9, y + 9), fill=(238, 252, 242), outline=GKP, width=2)
        elif kind == "digitize":
            draw.rectangle((cx - 9, y - 9, cx + 9, y + 9), fill=(255, 251, 235), outline=DIGI, width=2)
        elif kind == "error":
            draw.ellipse((cx - 10, y - 10, cx + 10, y + 10), fill=(255, 241, 242), outline=ERR, width=2)
        draw.text((cx + 16, y - 10), label, fill=TEXT, font=f_small)

    draw_item(start_x + 0 * gap, "Physical qubit", "qubit")
    draw_item(start_x + 1 * gap, "Bosonic mode", "mode")
    draw_item(start_x + 2 * gap, "Digitization stage", "digitize")
    draw_item(start_x + 3 * gap, "Qubit error", "error")


def save_png_near_target_size(image: Image.Image, out_path: Path, target_bytes: int = 2 * 1024 * 1024) -> None:
    """Save PNG choosing a scale that gets close to the target file size."""
    best_payload: bytes | None = None
    best_gap: int | None = None

    for scale in (1, 2, 3, 4):
        if scale == 1:
            candidate = image
        else:
            candidate = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        candidate.save(buf, format="PNG")
        payload = buf.getvalue()
        gap = abs(len(payload) - target_bytes)
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_payload = payload

    if best_payload is None:
        image.save(out_path)
        return

    out_path.write_bytes(best_payload)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    paper_root = script_dir.parent
    stats = load_run_stats(paper_root)

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_h2 = load_font(36, bold=True)
    f_body = load_font(21, bold=False)
    f_small = load_font(18, bold=False)

    left = (86, 70, 1098, 918)
    right = (1188, 70, 2214, 918)

    draw_panel_frame(draw, left, "Pauli Baseline (reference model)", "Discrete qubit lattice with sampled X/Y/Z errors", f_h2, f_body)
    draw_panel_frame(draw, right, "Digitized Native GKP (hardware-facing model)", "CV displacement noise then digitization to bits", f_h2, f_body)

    draw_pauli(draw, left, stats, f_body, f_small)
    draw_gkp(draw, right, stats, f_body, f_small)
    draw_legend(draw, left, right, f_small)

    out_png = paper_root / "figure_hardware_models_pauli_vs_gkp_d357.png"
    out_pdf = paper_root / "figure_hardware_models_pauli_vs_gkp_d357.pdf"
    save_png_near_target_size(image, out_png, target_bytes=2 * 1024 * 1024)
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
