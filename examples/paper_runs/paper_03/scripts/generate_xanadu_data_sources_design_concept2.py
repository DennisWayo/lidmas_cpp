#!/usr/bin/env python3
"""Generate concept-2 data-source design figure for paper_03."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 2520, 1240
BG = (255, 255, 255)
TEXT = (29, 33, 39)
SUBTEXT = (93, 101, 111)
BORDER = (211, 218, 227)
ARROW = (49, 60, 78)


@dataclass
class SourceStats:
    name: str
    source_form: str
    fixture_requests: int | None
    real_requests: int | None
    accent: tuple[int, int, int]
    soft: tuple[int, int, int]
    note: str


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
    n = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    h0 = (int(p1[0] - ux * head + px * (head * 0.58)), int(p1[1] - uy * head + py * (head * 0.58)))
    h1 = (int(p1[0] - ux * head - px * (head * 0.58)), int(p1[1] - uy * head - py * (head * 0.58)))
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


def load_stats(paper_root: Path) -> list[SourceStats]:
    fixture_path = paper_root / "results" / "01_prepare_fixture_requests" / "table_request_manifest.csv"
    real_path = paper_root / "results" / "05_real_data_analysis" / "table_real_data_decoder_matrix.csv"

    fixture_rows = read_csv(fixture_path)
    real_rows = read_csv(real_path)

    fixture: dict[str, int] = {}
    for row in fixture_rows:
        ds = (row.get("dataset") or "").strip().lower()
        cnt = parse_int(row.get("request_lines"))
        if ds and cnt is not None:
            fixture[ds] = cnt

    real: dict[str, int] = {}
    for row in real_rows:
        ds = (row.get("dataset") or "").strip().lower()
        cnt = parse_int(row.get("request_lines"))
        if cnt is None:
            continue
        if ds.startswith("aurora"):
            real["aurora"] = max(real.get("aurora", 0), cnt)
        elif ds.startswith("qca"):
            real["qca"] = max(real.get("qca", 0), cnt)
        elif ds.startswith("gkp"):
            real["gkp"] = max(real.get("gkp", 0), cnt)

    return [
        SourceStats(
            name="Aurora",
            source_form="aurora_switch_dir",
            fixture_requests=fixture.get("aurora"),
            real_requests=real.get("aurora"),
            accent=(44, 121, 209),
            soft=(236, 246, 255),
            note="Switch settings mapped to binary event stream.",
        ),
        SourceStats(
            name="QCA",
            source_form="shot_matrix",
            fixture_requests=fixture.get("qca"),
            real_requests=real.get("qca"),
            accent=(219, 119, 12),
            soft=(255, 245, 232),
            note="Shot matrices converted to stabilizer events.",
        ),
        SourceStats(
            name="GKP",
            source_form="count_table_json",
            fixture_requests=fixture.get("gkp"),
            real_requests=real.get("gkp"),
            accent=(23, 157, 76),
            soft=(237, 251, 242),
            note="Count tables expanded to replay request lines.",
        ),
    ]


def draw_mini_icon(draw: ImageDraw.ImageDraw, kind: str, box: tuple[int, int, int, int], accent: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=10, fill=(255, 255, 255), outline=(201, 211, 223), width=2)
    if kind == "Aurora":
        bx = x0 + 14
        by = y1 - 16
        for h in [16, 30, 20, 34, 24]:
            draw.rounded_rectangle((bx, by - h, bx + 18, by), radius=4, fill=(228, 241, 255), outline=accent, width=2)
            bx += 24
    elif kind == "QCA":
        gx0, gy0 = x0 + 12, y0 + 12
        for r in range(4):
            for c in range(7):
                sx0 = gx0 + c * 15
                sy0 = gy0 + r * 15
                bit = (r + c) % 2 == 0
                draw.rectangle((sx0, sy0, sx0 + 10, sy0 + 10), fill=(255, 247, 235) if bit else (250, 251, 253), outline=accent if bit else (218, 220, 223), width=1)
    else:
        bx = x0 + 18
        by = y1 - 16
        for h in [12, 24, 36, 28, 18]:
            draw.rounded_rectangle((bx, by - h, bx + 16, by), radius=4, fill=(230, 248, 237), outline=accent, width=2)
            bx += 21


def draw_source_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    stats: SourceStats,
    f_h2,
    f_body,
    f_small,
) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(255, 255, 255), outline=BORDER, width=3)
    draw.rounded_rectangle((x0 + 8, y0 + 8, x0 + 18, y1 - 8), radius=6, fill=stats.accent, outline=stats.accent, width=0)

    draw.text((x0 + 30, y0 + 18), stats.name, fill=TEXT, font=f_h2)
    draw.text((x0 + 30, y0 + 56), f"source: {stats.source_form}", fill=SUBTEXT, font=f_body)

    fr = "n/a" if stats.fixture_requests is None else str(stats.fixture_requests)
    rr = "not used" if stats.real_requests is None else str(stats.real_requests)

    c1 = (x0 + 30, y0 + 92, x0 + 220, y0 + 124)
    c2 = (x0 + 230, y0 + 92, x0 + 430, y0 + 124)
    draw.rounded_rectangle(c1, radius=10, fill=stats.soft, outline=stats.accent, width=2)
    draw.rounded_rectangle(c2, radius=10, fill=(248, 250, 253), outline=BORDER, width=2)
    draw.text((c1[0] + 10, c1[1] + 8), f"fixture: {fr}", fill=stats.accent, font=f_small)
    draw.text((c2[0] + 10, c2[1] + 8), f"real: {rr}", fill=SUBTEXT, font=f_small)

    icon_box = (x0 + 30, y0 + 138, x0 + 170, y1 - 22)
    draw_mini_icon(draw, stats.name, icon_box, stats.accent)
    draw.text((x0 + 184, y0 + 150), stats.note, fill=TEXT, font=f_small)

    return (x1, (y0 + y1) // 2)


def draw_normalization_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_h2, f_body, f_small) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=20, fill=(250, 252, 255), outline=(178, 196, 222), width=3)
    draw.text((x0 + 24, y0 + 20), "Normalization Layer", fill=(39, 86, 158), font=f_h2)
    draw.text((x0 + 24, y0 + 58), "line-oriented decoder IO contract", fill=SUBTEXT, font=f_body)

    chips = [
        ("code_id | round_index | n_qubits", (236, 245, 255), (59, 106, 181)),
        ("events: index, time_ns, type", (239, 251, 244), (37, 122, 78)),
        ("noise: sigma + gate/meas/idle/loss", (255, 249, 235), (162, 106, 8)),
        ("metadata: provider, backend, source_id", (245, 247, 251), (85, 96, 110)),
    ]
    yy = y0 + 104
    for text, fill, stroke in chips:
        draw.rounded_rectangle((x0 + 24, yy, x1 - 24, yy + 42), radius=12, fill=fill, outline=stroke, width=2)
        draw.text((x0 + 36, yy + 11), text, fill=stroke, font=f_small)
        yy += 56

    # Plain-language contract summary (no math notation) to avoid empty space.
    section_y = yy + 8
    draw.text((x0 + 24, section_y), "normalization flow", fill=(56, 95, 151), font=f_body)
    flow_rows = [
        "1) read provider-native records",
        "2) map observables to event indices and event types",
        "3) stamp noise priors and provenance metadata",
        "4) emit one line-oriented decoder request per shot",
    ]
    ry = section_y + 36
    for row in flow_rows:
        draw.rounded_rectangle((x0 + 24, ry, x1 - 24, ry + 40), radius=11, fill=(255, 255, 255), outline=(191, 206, 228), width=2)
        draw.text((x0 + 36, ry + 10), row, fill=(72, 82, 95), font=f_small)
        ry += 50

    checks_title_y = ry + 4
    draw.text((x0 + 24, checks_title_y), "integrity checks", fill=(56, 95, 151), font=f_body)
    check_rows = [
        "request and response line counts stay matched",
        "request/response parse errors remain zero",
        "decoder-name mismatch count remains zero",
    ]
    cy = checks_title_y + 36
    for row in check_rows:
        draw.rounded_rectangle((x0 + 24, cy, x1 - 24, cy + 40), radius=11, fill=(247, 250, 254), outline=(198, 209, 224), width=2)
        draw.text((x0 + 36, cy + 10), row, fill=(80, 90, 103), font=f_small)
        cy += 50

    chip = (x0 + 24, y1 - 72, x1 - 24, y1 - 30)
    draw.rounded_rectangle(chip, radius=12, fill=(255, 255, 255), outline=(175, 195, 225), width=2)
    draw.text((chip[0] + 12, chip[1] + 11), "shared request stream for decoder-swap replay", fill=(56, 95, 151), font=f_small)

    return (x1, (y0 + y1) // 2)


def draw_decoder_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], f_h2, f_small) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=20, fill=(255, 255, 255), outline=BORDER, width=3)
    draw.text((x0 + 20, y0 + 20), "Replay Decoders", fill=TEXT, font=f_h2)

    rows = [
        ("MWPM", (220, 234, 251), (38, 104, 190)),
        ("UF", (233, 245, 255), (49, 117, 203)),
        ("BP", (255, 236, 239), (183, 42, 64)),
        ("Neural-MWPM", (236, 249, 240), (20, 128, 66)),
    ]
    yy = y0 + 70
    for label, fill, stroke in rows:
        draw.rounded_rectangle((x0 + 20, yy, x1 - 20, yy + 48), radius=12, fill=fill, outline=stroke, width=2)
        draw.text((x0 + 34, yy + 14), label, fill=stroke, font=f_small)
        yy += 62

    for k in range(3):
        gy = y0 + 76 + k * 62 + 24
        draw.line((x1 - 26, gy, x1 - 10, gy), fill=(210, 218, 227), width=1)

    chip = (x0 + 20, yy + 14, x1 - 20, yy + 56)
    draw.rounded_rectangle(chip, radius=12, fill=(248, 250, 253), outline=BORDER, width=2)
    draw.text((chip[0] + 12, chip[1] + 11), "same input, different correction policy", fill=SUBTEXT, font=f_small)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    paper_root = script_dir.parent
    stats = load_stats(paper_root)

    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    f_h2 = load_font(38, bold=True)
    f_body = load_font(22, bold=False)
    f_small = load_font(20, bold=False)

    # Left: three source cards (stacked)
    left_x0, left_x1 = 72, 742
    top = 66
    gap = 22
    h_card = (H - top - 74 - 2 * gap) // 3
    out_points: list[tuple[int, int]] = []
    for i, s in enumerate(stats):
        y0 = top + i * (h_card + gap)
        y1 = y0 + h_card
        out_points.append(draw_source_card(draw, (left_x0, y0, left_x1, y1), s, f_h2, f_body, f_small))

    # Middle: normalization panel
    mid_box = (810, 132, 1700, H - 210)
    mid_out = draw_normalization_panel(draw, mid_box, f_h2, f_body, f_small)

    # Right: decoder replay panel
    right_box = (1774, 355, 2448, 807)
    draw_decoder_panel(draw, right_box, f_h2, f_small)

    for p in out_points:
        draw_arrow(draw, (p[0] + 6, p[1]), (mid_box[0] - 12, p[1]), color=ARROW, width=4, head=11)
    draw_arrow(draw, (mid_out[0] + 10, mid_out[1]), (right_box[0] - 12, mid_out[1]), color=ARROW, width=4, head=12)

    out_png = paper_root / "figure_xanadu_data_sources_design_concept2.png"
    out_pdf = paper_root / "figure_xanadu_data_sources_design_concept2.pdf"
    image.save(out_png, "PNG")
    image.save(out_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
