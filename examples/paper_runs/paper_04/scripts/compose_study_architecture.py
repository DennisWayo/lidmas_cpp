#!/usr/bin/env python3
"""Compose two Mermaid-rendered architecture panels into one paper figure."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("examples/paper_runs/paper_04/results/03_analysis")


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/ArialHB.ttc"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit_width(image: Image.Image, target_width: int) -> Image.Image:
    if image.width == target_width:
        return image
    scale = target_width / image.width
    return image.resize((target_width, round(image.height * scale)), Image.Resampling.LANCZOS)


def _orange_box(image: Image.Image) -> tuple[int, int, int, int]:
    """Return the largest orange outline component in a rendered Mermaid panel."""
    pixels = image.load()
    orange: set[tuple[int, int]] = set()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue = pixels[x, y]
            if red > 180 and 45 < green < 150 and blue < 90:
                orange.add((x, y))

    best: tuple[int, int, int, int, int] | None = None
    while orange:
        start = orange.pop()
        stack = [start]
        xs: list[int] = []
        ys: list[int] = []
        while stack:
            x, y = stack.pop()
            xs.append(x)
            ys.append(y)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in orange:
                    orange.remove((nx, ny))
                    stack.append((nx, ny))
        if len(xs) > 20:
            component = (len(xs), min(xs), min(ys), max(xs), max(ys))
            if best is None or component[0] > best[0]:
                best = component

    if best is None:
        raise RuntimeError("No orange contract box found in Mermaid panel.")
    _, left, top, right, bottom = best
    return left, top, right, bottom


def main() -> int:
    generation = Image.open(ROOT / "figure_study_architecture_generation.png").convert("RGB")
    replay = Image.open(ROOT / "figure_study_architecture_replay.png").convert("RGB")

    margin = 48
    arrow_gap = 96
    target_width = max(generation.width, replay.width, 1000)
    generation = _fit_width(generation, target_width)
    replay = _fit_width(replay, target_width)

    bridge_font = _font(34, bold=True)

    width = target_width + margin * 2
    height = margin + generation.height + arrow_gap + replay.height + margin
    canvas = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)

    y = margin
    generation_y = y
    canvas.paste(generation, (margin, generation_y))
    y += generation.height

    label = "contract-preserving replay"
    bbox = draw.textbbox((0, 0), label, font=bridge_font)
    label_w = bbox[2] - bbox[0]

    replay_y = y + arrow_gap
    canvas.paste(replay, (margin, replay_y))

    top_contract = _orange_box(generation)
    bottom_contract = _orange_box(replay)
    start_x = margin + (top_contract[0] + top_contract[2]) // 2
    start_y = generation_y + top_contract[3] + 4
    end_x = margin + (bottom_contract[0] + bottom_contract[2]) // 2
    end_y = replay_y + bottom_contract[1] - 2
    connector_y = generation_y + generation.height + 58

    label_x = end_x + (start_x - end_x - label_w) // 2
    draw.text((label_x, generation_y + generation.height + 8), label, fill="#334155", font=bridge_font)
    draw.line((start_x, start_y, start_x, connector_y, end_x, connector_y, end_x, end_y), fill="#334155", width=7)
    draw.polygon([(end_x - 20, end_y - 24), (end_x + 20, end_y - 24), (end_x, end_y + 4)], fill="#334155")
    y += arrow_gap

    out_png = ROOT / "figure_study_architecture.png"
    out_pdf = ROOT / "figure_study_architecture.pdf"
    canvas.save(out_png, optimize=True)
    canvas.save(out_pdf, "PDF", resolution=300.0)
    manuscript = ROOT / "manuscript_figures"
    manuscript.mkdir(exist_ok=True)
    manuscript_png = manuscript / "figure_study_architecture.png"
    manuscript_pdf = manuscript / "figure_study_architecture.pdf"
    canvas.save(manuscript_png, optimize=True)
    canvas.save(manuscript_pdf, "PDF", resolution=300.0)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")
    print(f"Wrote {manuscript_png}")
    print(f"Wrote {manuscript_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
