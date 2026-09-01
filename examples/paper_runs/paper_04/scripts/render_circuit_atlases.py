#!/usr/bin/env python3
"""Assemble circuit-only atlas figures for paper_04."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PRINT_ROOT = Path("examples/paper_runs/paper_04/results/03_analysis/circuit_prints")
OUT_ROOT = Path("examples/paper_runs/paper_04/results/03_analysis/circuit_figures")

TEXT_FONT = Path("./.venv/lib/python3.14/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono.ttf")
BOLD_FONT = Path("./.venv/lib/python3.14/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono-Bold.ttf")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-dir",
        default=str(PRINT_ROOT),
        help="Directory containing circuit text snapshots.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUT_ROOT),
        help="Directory for grouped atlas outputs.",
    )
    return parser.parse_args()


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        BOLD_FONT if bold else TEXT_FONT,
        Path("/System/Library/Fonts/Menlo.ttc"),
        Path("/System/Library/Fonts/SFNSMono.ttf"),
        Path("/System/Library/Fonts/Supplemental/Andale Mono.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _read_blocks(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8").rstrip()
    return [block.splitlines() for block in text.split("\n\n") if block.strip()]


def _text_size(lines: list[str], font: ImageFont.ImageFont, line_gap: int) -> tuple[int, int, int]:
    sample = "M"
    bbox = font.getbbox(sample)
    line_h = bbox[3] - bbox[1] + line_gap
    max_w = 1
    for line in lines:
        line_bbox = font.getbbox(line or " ")
        max_w = max(max_w, line_bbox[2] - line_bbox[0])
    return max_w, line_h * len(lines), line_h


def _render_text_panel(
    lines: list[str],
    *,
    label: str,
    font_size: int,
    pad: int = 24,
    line_gap: int = 3,
) -> Image.Image:
    font = _font(font_size)
    label_font = _font(max(13, font_size + 1), bold=True)
    text_w, text_h, line_h = _text_size(lines, font, line_gap)
    label_h = label_font.getbbox(label)[3] - label_font.getbbox(label)[1] + 16
    image = Image.new("RGB", (text_w + pad * 2, text_h + label_h + pad * 2), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1),
        radius=10,
        fill="#FFFFFF",
        outline="#CBD5E1",
        width=2,
    )
    draw.text((pad, pad - 2), label, fill="#111827", font=label_font)
    y = pad + label_h
    for line in lines:
        draw.text((pad, y), line, fill="#111827", font=font)
        y += line_h
    return image


def _paste(canvas: Image.Image, panel: Image.Image, x: int, y: int) -> None:
    canvas.paste(panel, (x, y))


def _widen_to(panel: Image.Image, target_width: int) -> Image.Image:
    if panel.width == target_width:
        return panel
    return panel.resize((target_width, panel.height), Image.Resampling.BICUBIC)


def _pennylane_row(print_dir: Path) -> tuple[str, list[Image.Image]]:
    blocks = _read_blocks(print_dir / "surface_pennylane_circuit.txt")
    panels = [
        _render_text_panel(
            block,
            label=f"PennyLane block {idx}/6, wires 0-80",
            font_size=13,
            pad=20,
            line_gap=3,
        )
        for idx, block in enumerate(blocks, start=1)
    ]
    return "PennyLane surface circuit unfolded left-to-right", panels


def _single_block_row(print_dir: Path, filename: str, title: str, font_size: int) -> tuple[str, list[Image.Image]]:
    block = _read_blocks(print_dir / filename)[0]
    panel = _render_text_panel(block, label=title, font_size=font_size, pad=22, line_gap=2)
    return title, [panel]


def _compose_surface_atlas(print_dir: Path, out_dir: Path) -> None:
    rows = [
        _pennylane_row(print_dir),
        _single_block_row(print_dir, "surface_qiskit_circuit.txt", "Qiskit surface circuit", 8),
        _single_block_row(print_dir, "surface_cirq_circuit.txt", "Cirq surface circuit", 10),
    ]

    margin = 70
    gap = 30
    row_gap = 72
    title_h = 86
    note_h = 58
    title_font = _font(34, bold=True)
    row_font = _font(22, bold=True)
    note_font = _font(18)

    penny_title, penny_panels = rows[0]
    penny_w = sum(panel.width for panel in penny_panels) + gap * (len(penny_panels) - 1)
    rows = [rows[0]] + [(title, [_widen_to(panels[0], penny_w)]) for title, panels in rows[1:]]
    max_w = penny_w

    width = margin * 2 + max_w
    height = margin + title_h
    for _, panels in rows:
        height += row_font.getbbox("M")[3] - row_font.getbbox("M")[1] + 22
        height += max(panel.height for panel in panels)
        height += row_gap
    height += note_h + margin - row_gap

    canvas = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    y = margin
    draw.text((margin, y), "Circuit-only atlas for surface-family runs", fill="#111827", font=title_font)
    y += title_h

    for row_title, panels in rows:
        draw.text((margin, y), row_title, fill="#1F2937", font=row_font)
        y += row_font.getbbox("M")[3] - row_font.getbbox("M")[1] + 22

        if len(panels) == 1:
            x = margin
            _paste(canvas, panels[0], x, y)
            y += panels[0].height + row_gap
            continue

        x = margin
        for panel in panels:
            _paste(canvas, panel, x, y)
            x += panel.width + gap
        y += max(panel.height for panel in panels) + row_gap

    note = (
        "Only framework-rendered circuit drawings are shown here; support maps, metadata, "
        "and GKP digitization tables are reported separately in the appendix tables."
    )
    draw.text((margin, height - margin - note_h + 12), note, fill="#374151", font=note_font)

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "figure_surface_circuit_atlas.png"
    pdf = out_dir / "figure_surface_circuit_atlas.pdf"
    canvas.save(png, optimize=True)
    canvas.save(pdf, "PDF", resolution=300.0)
    print(f"Wrote {png}")
    print(f"Wrote {pdf}")


def main() -> int:
    args = parse_args()
    _compose_surface_atlas(Path(args.print_dir), Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
