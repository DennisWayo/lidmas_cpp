#!/usr/bin/env python3
"""Generate publication-quality threshold plots from LiDMaS CSV outputs."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Publication-quality plotting for LiDMaS CSV outputs")
    p.add_argument("--input", required=True, help="Path to input CSV")
    p.add_argument("--output-prefix", required=True, help="Output file prefix (without extension)")
    p.add_argument("--x-col", required=True, help="X-axis column name (e.g., sigma, pauli_p)")
    p.add_argument("--group-col", default="distance", help="Grouping column for separate curves")
    p.add_argument("--mode", default="", help="Optional mode filter (hybrid/pauli)")
    p.add_argument("--title", default="LiDMaS Threshold Curve", help="Figure title")
    p.add_argument("--xlabel", default="", help="X-axis label")
    p.add_argument("--ylabel", default="Logical Error Rate (LER)", help="Y-axis label")
    p.add_argument("--group-prefix", default="", help="Legend label prefix (e.g., d=, decoder=)")
    p.add_argument("--logy", action="store_true", help="Use logarithmic y-axis")
    p.add_argument("--style", default="", help="Optional .mplstyle file path")
    return p


def apply_style(style_path: str) -> None:
    if style_path:
        plt.style.use(style_path)
        return

    # Fallback style tuned for print + screen clarity.
    plt.rcParams.update(
        {
            "figure.figsize": (8.0, 5.2),
            "figure.dpi": 120,
            "savefig.dpi": 600,
            "font.family": "serif",
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 13,
            "axes.linewidth": 1.1,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "legend.frameon": True,
            "legend.framealpha": 0.9,
            "legend.fontsize": 11,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
        }
    )


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input CSV not found: {input_path}")
        return 1

    df = pd.read_csv(input_path)
    if args.mode:
        if "mode" not in df.columns:
            print("error: requested --mode filter but CSV has no 'mode' column")
            return 1
        df = df[df["mode"] == args.mode]

    required = [args.x_col, args.group_col, "ler"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"error: missing required column(s): {', '.join(missing)}")
        return 1
    if df.empty:
        print("error: filtered CSV is empty; nothing to plot")
        return 1

    apply_style(args.style)

    fig, ax = plt.subplots()
    # Colorblind-friendly palette.
    palette = [
        "#0072B2",
        "#D55E00",
        "#009E73",
        "#CC79A7",
        "#E69F00",
        "#56B4E9",
        "#000000",
    ]

    grouped = sorted(df[args.group_col].dropna().unique())
    for idx, g in enumerate(grouped):
        sub = df[df[args.group_col] == g].copy()
        sub = sub.sort_values(by=args.x_col)
        color = palette[idx % len(palette)]
        label = f"{args.group_prefix}{g}" if args.group_prefix else str(g)
        ax.plot(
            sub[args.x_col],
            sub["ler"],
            marker="o",
            markersize=4.8,
            linewidth=2.0,
            color=color,
            label=label,
        )
        if "ci_low" in sub.columns and "ci_high" in sub.columns:
            ax.fill_between(
                sub[args.x_col],
                sub["ci_low"],
                sub["ci_high"],
                color=color,
                alpha=0.16,
                linewidth=0.0,
            )

    if args.logy:
        ax.set_yscale("log")
        ax.set_ylim(bottom=1e-4)

    ax.set_title(args.title)
    ax.set_xlabel(args.xlabel or args.x_col)
    ax.set_ylabel(args.ylabel)
    ax.grid(True, which="major")
    ax.grid(True, which="minor", alpha=0.15)
    ax.legend(loc="best")
    fig.tight_layout()

    out_prefix = Path(args.output_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    png_path = out_prefix.with_suffix(".png")
    pdf_path = out_prefix.with_suffix(".pdf")
    svg_path = out_prefix.with_suffix(".svg")
    fig.savefig(png_path, dpi=600)
    fig.savefig(pdf_path)
    fig.savefig(svg_path)
    print(f"wrote {png_path}")
    print(f"wrote {pdf_path}")
    print(f"wrote {svg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
