#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot decoder comparison curves.")
    parser.add_argument("--input", required=True, help="Combined decoder CSV path")
    parser.add_argument("--out_dir", required=True, help="Output directory for figures")
    args = parser.parse_args()

    curves = {
        "mwpm": {"x": [], "y": [], "label": "MWPM", "linestyle": "-"},
        "uf": {"x": [], "y": [], "label": "UF", "linestyle": "--"},
        "neural": {"x": [], "y": [], "label": "Neural MWPM", "linestyle": "-."},
    }

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            decoder = row.get("decoder", "").strip()
            if decoder not in curves:
                continue
            try:
                p = float(row.get("pauli_p", "nan"))
                ler = float(row.get("ler", "nan"))
            except ValueError:
                continue
            if not math.isfinite(p) or not math.isfinite(ler):
                continue
            curves[decoder]["x"].append(p)
            curves[decoder]["y"].append(ler)

    plt.figure(figsize=(7.0, 4.8))
    for key in ("mwpm", "uf", "neural"):
        data = curves[key]
        pairs = sorted(zip(data["x"], data["y"]), key=lambda t: t[0])
        if not pairs:
            continue
        xs = [p for p, _ in pairs]
        ys = [ler for _, ler in pairs]
        plt.plot(xs, ys, marker="o", linewidth=2.0, linestyle=data["linestyle"], label=data["label"])

    plt.xlabel("Physical error rate p")
    plt.ylabel("Logical error rate (LER)")
    plt.title("Decoder Comparison (Surface Code, d=5)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    png = out_dir / "figure_decoder_comparison.png"
    pdf = out_dir / "figure_decoder_comparison.pdf"
    svg = out_dir / "figure_decoder_comparison.svg"

    plt.savefig(png, dpi=300)
    plt.savefig(pdf)
    plt.savefig(svg)
    print(f"Wrote figures: {png}, {pdf}, {svg}")


if __name__ == "__main__":
    main()
