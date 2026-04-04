#!/usr/bin/env python3
"""Generate a design-style Aurora/QCA/GKP data-source figure for paper_03."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2480, 1120
BG = (255, 255, 255)
TEXT = (30, 34, 39)
SUBTEXT = (88, 95, 104)
BORDER = (212, 218, 226)
ARROW = (45, 55, 72)

CARD_AURORA = (236, 246, 255)
CARD_QCA = (255, 245, 232)
CARD_GKP = (238, 251, 242)

HEAD_AURORA = (43, 123, 209)
HEAD_QCA = (217, 119, 6)
HEAD_GKP = (22, 163, 74)


@dataclass
class CardStats:
    name: str
    source_form: str
    fixture_requests: int | None
    real_slice_requests: int | None
    card_fill: tuple[int, int, int]
    head_color: tuple[int, int, int]
    note: str


def load_font(size: int, bold: bool = False):
    candidates: list[str] = []
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
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    p0: tuple[int, int],
    p1: tuple[int, int],
    color: tuple[int, int, int] = ARROW,
    width: int = 4,
    head: int = 12,
) -> None:
    draw.line((p0[0], p0[1], p1[0], p1[1]), fill=color, width=width)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    norm = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / norm, dy / norm
    px, py = -uy, ux
    h0 = (
        int(p1[0] - ux * head + px * (head * 0.55)),
        int(p1[1] - uy * head + py * (head * 0.55)),
    )
    h1 = (
        int(p1[0] - ux * head - px * (head * 0.55)),
        int(p1[1] - uy * head - py * (head * 0.55)),
    )
    draw.polygon([p1, h0, h1], fill=color)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def load_card_stats(paper_root: Path) -> list[CardStats]:
    fixture_path = paper_root / "results" / "01_prepare_fixture_requests" / "table_request_manifest.csv"
    real_path = paper_root / "results" / "05_real_data_analysis" / "table_real_data_decoder_matrix.csv"

    fixture_rows = read_csv(fixture_path)
    real_rows = read_csv(real_path)

    fixture_counts: dict[str, int] = {}
    for row in fixture_rows:
        ds = (row.get("dataset") or "").strip().lower()
        count = parse_int(row.get("request_lines"))
        if ds and count is not None:
            fixture_counts[ds] = count

    real_counts: dict[str, int] = {}
    for row in real_rows:
        ds = (row.get("dataset") or "").strip().lower()
        count = parse_int(row.get("request_lines"))
        if count is None:
            continue
        if ds.startswith("aurora"):
            real_counts["aurora"] = max(count, real_counts.get("aurora", 0))
        elif ds.startswith("qca"):
            real_counts["qca"] = max(count, real_counts.get("qca", 0))
        elif ds.startswith("gkp"):
            real_counts["gkp"] = max(count, real_counts.get("gkp", 0))

    return [
        CardStats(
            name="Aurora",
            source_form="aurora_switch_dir",
            fixture_requests=fixture_counts.get("aurora"),
            real_slice_requests=real_counts.get("aurora"),
            card_fill=CARD_AURORA,
            head_color=HEAD_AURORA,
            note="Switch-setting traces per QPU, binarized to event bits.",
        ),
        CardStats(
            name="QCA",
            source_form="shot_matrix",
            fixture_requests=fixture_counts.get("qca"),
            real_slice_requests=real_counts.get("qca"),
            card_fill=CARD_QCA,
            head_color=HEAD_QCA,
            note="Shot matrices mapped to stabilizer-event indices.",
        ),
        CardStats(
            name="GKP",
            source_form="count_table_json",
            fixture_requests=fixture_counts.get("gkp"),
            real_slice_requests=real_counts.get("gkp"),
            card_fill=CARD_GKP,
            head_color=HEAD_GKP,
            note="Count summaries expanded to line-oriented replay requests.",
        ),
    ]


def draw_aurora_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=14, fill=(255, 255, 255), outline=(188, 209, 232), width=2)
    base_y = y1 - 20
    left = x0 + 20
    width = (x1 - x0 - 40) // 6
    heights = [24, 54, 34, 64, 42, 58]
    for i, h in enumerate(heights):
        bx0 = left + i * width
        bx1 = bx0 + width - 8
        by0 = base_y - h
        draw.rounded_rectangle((bx0, by0, bx1, base_y), radius=6, fill=(224, 239, 252), outline=color, width=2)
    draw.text((x0 + 16, y0 + 10), "switch settings", fill=SUBTEXT, font=load_font(20))


def draw_qca_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=14, fill=(255, 255, 255), outline=(240, 214, 174), width=2)
    rows, cols = 5, 9
    gx0, gy0 = x0 + 16, y0 + 28
    gx1, gy1 = x1 - 16, y1 - 16
    cw = (gx1 - gx0) // cols
    ch = (gy1 - gy0) // rows
    mask = [
        "101001011",
        "010110001",
        "111000101",
        "001101010",
        "100011110",
    ]
    for r in range(rows):
        for c in range(cols):
            sx0 = gx0 + c * cw + 2
            sy0 = gy0 + r * ch + 2
            sx1 = sx0 + cw - 5
            sy1 = sy0 + ch - 5
            bit = mask[r][c] == "1"
            fill = (255, 244, 224) if bit else (251, 251, 251)
            draw.rectangle((sx0, sy0, sx1, sy1), fill=fill, outline=color if bit else (220, 220, 220), width=1)
    draw.text((x0 + 16, y0 + 6), "shot matrix", fill=SUBTEXT, font=load_font(20))


def draw_gkp_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=14, fill=(255, 255, 255), outline=(182, 226, 199), width=2)
    draw.text((x0 + 16, y0 + 6), "count table", fill=SUBTEXT, font=load_font(20))
    left = x0 + 26
    right = x1 - 26
    base_y = y1 - 20
    bar_w = (right - left) // 6
    heights = [20, 34, 52, 42, 30, 18]
    for i, h in enumerate(heights):
        bx0 = left + i * bar_w
        bx1 = bx0 + bar_w - 8
        by0 = base_y - h
        draw.rounded_rectangle((bx0, by0, bx1, base_y), radius=6, fill=(229, 248, 236), outline=color, width=2)
    draw.line((left - 6, base_y, right + 6, base_y), fill=(154, 199, 172), width=2)


def draw_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    stats: CardStats,
    f_h2,
    f_body,
    f_small,
) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=stats.card_fill, outline=BORDER, width=3)
    draw.rounded_rectangle((x0, y0, x1, y0 + 56), radius=18, fill=stats.head_color, outline=stats.head_color, width=0)
    draw.rectangle((x0, y0 + 40, x1, y0 + 58), fill=stats.head_color, outline=stats.head_color)
    draw.text((x0 + 18, y0 + 12), stats.name, fill=(255, 255, 255), font=f_h2)

    draw.text((x0 + 18, y0 + 78), f"Source form: {stats.source_form}", fill=TEXT, font=f_body)

    fr = "n/a" if stats.fixture_requests is None else str(stats.fixture_requests)
    draw.text((x0 + 18, y0 + 118), f"Fixture requests: {fr}", fill=SUBTEXT, font=f_small)

    if stats.real_slice_requests is None:
        real_text = "Real slice requests: not used in this run"
    else:
        real_text = f"Real slice requests: {stats.real_slice_requests}"
    draw.text((x0 + 18, y0 + 148), real_text, fill=SUBTEXT, font=f_small)

    draw.text((x0 + 18, y0 + 186), stats.note, fill=TEXT, font=f_small)

    icon_box = (x0 + 18, y0 + 232, x1 - 18, y1 - 22)
    if stats.name == "Aurora":
        draw_aurora_icon(draw, icon_box, stats.head_color)
    elif stats.name == "QCA":
        draw_qca_icon(draw, icon_box, stats.head_color)
    else:
        draw_gkp_icon(draw, icon_box, stats.head_color)

    return ((x0 + x1) // 2, y1)


def draw_contract_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_body, f_small) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(250, 252, 255), outline=(175, 195, 225), width=3)
    draw.text((x0 + 20, y0 + 12), "Normalized decoder IO request line", fill=(35, 82, 157), font=f_body)

    chips = [
        ("code_id / round_index / n_qubits", (236, 244, 255), (57, 104, 179)),
        ("events: (index, time_ns, type)", (239, 251, 244), (37, 122, 78)),
        ("noise: sigma + gate/meas/idle/loss", (255, 249, 235), (157, 105, 8)),
        ("metadata: provider/backend/source_id", (244, 246, 250), (80, 90, 103)),
    ]
    cx = x0 + 20
    cy = y0 + 54
    for text, fill, stroke in chips:
        tw = int(draw.textlength(text, font=f_small)) + 28
        draw.rounded_rectangle((cx, cy, cx + tw, cy + 30), radius=10, fill=fill, outline=stroke, width=2)
        draw.text((cx + 12, cy + 6), text, fill=stroke, font=f_small)
        cx += tw + 12
        if cx + 220 > x1:
            cx = x0 + 20
            cy += 38

    return (x1, (y0 + y1) // 2)


def draw_decoder_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    f_body,
    f_small,
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(255, 255, 255), outline=(171, 186, 204), width=3)
    draw.text((x0 + 14, y0 + 10), "Replay engines", fill=TEXT, font=f_body)
    decoders = [
        ("MWPM", (220, 234, 251), (38, 104, 190)),
        ("UF", (233, 245, 255), (49, 117, 203)),
        ("BP", (255, 236, 239), (183, 42, 64)),
        ("Neural-MWPM", (236, 249, 240), (20, 128, 66)),
    ]
    y = y0 + 48
    for label, fill, stroke in decoders:
        draw.rounded_rectangle((x0 + 14, y, x1 - 14, y + 30), radius=10, fill=fill, outline=stroke, width=2)
        draw.text((x0 + 26, y + 7), label, fill=stroke, font=f_small)
        y += 38
    draw.text((x0 + 14, y1 - 24), "same input contract, swappable decoder", fill=SUBTEXT, font=f_small)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    paper_root = script_dir.parent
    card_stats = load_card_stats(paper_root)

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_h2 = load_font(33, bold=True)
    f_body = load_font(25, bold=False)
    f_small = load_font(21, bold=False)

    margin_x = 78
    card_top = 70
    card_bottom = 680
    gap = 36
    card_w = (W - (2 * margin_x) - (2 * gap)) // 3

    arrow_starts: list[tuple[int, int]] = []
    for idx, stats in enumerate(card_stats):
        x0 = margin_x + idx * (card_w + gap)
        x1 = x0 + card_w
        arrow_starts.append(
            draw_card(draw, (x0, card_top, x1, card_bottom), stats, f_h2, f_body, f_small)
        )

    contract_box = (110, 740, 1905, 1020)
    contract_out = draw_contract_panel(draw, contract_box, f_body, f_small)
    decoder_box = (1950, 740, 2388, 1020)
    draw_decoder_panel(draw, decoder_box, f_body, f_small)

    for px, py in arrow_starts:
        draw_arrow(draw, (px, py + 8), (px, contract_box[1] - 10), color=ARROW, width=4, head=11)
    draw_arrow(draw, (contract_out[0] + 10, contract_out[1]), (decoder_box[0] - 12, (decoder_box[1] + decoder_box[3]) // 2), color=ARROW, width=4, head=12)

    out_png = paper_root / "figure_xanadu_data_sources_design.png"
    out_pdf = paper_root / "figure_xanadu_data_sources_design.pdf"
    image.save(out_png, "PNG")
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
