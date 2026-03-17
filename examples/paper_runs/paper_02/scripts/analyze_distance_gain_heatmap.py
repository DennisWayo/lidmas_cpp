#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PAIR_LIST = [(3, 5), (5, 7)]


def _fmt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "nan"
    if math.isnan(x):
        return "nan"
    return f"{x:.6g}"


def _heatmap(ax, mat, row_labels, col_labels, title):
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_title(title)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels([f"{x:.2f}" for x in col_labels], rotation=45, ha="right")
    ax.set_xlabel("Sigma")
    ax.set_ylabel("Decoder")
    return im


def main():
    parser = argparse.ArgumentParser(description="Generate distance-gain heatmaps from GKP multi-distance output.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--style", default="")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    if args.style:
        style_path = Path(args.style)
        if style_path.exists():
            plt.style.use(style_path)

    df = pd.read_csv(args.input)
    if df.empty:
        raise RuntimeError("input CSV is empty")

    df["sigma"] = df["sigma"].astype(float)
    df["distance"] = df["distance"].astype(int)
    df["ler"] = df["ler"].astype(float)

    decoders = sorted(df["decoder"].dropna().unique().tolist())
    sigmas = sorted(df["sigma"].dropna().unique().tolist())

    rows = []
    for decoder in decoders:
        sub = df[df["decoder"] == decoder]
        for s in sigmas:
            point = sub[sub["sigma"] == s]
            by_d = {int(r["distance"]): float(r["ler"]) for _, r in point.iterrows()}
            for d_low, d_high in PAIR_LIST:
                low = by_d.get(d_low, math.nan)
                high = by_d.get(d_high, math.nan)
                gain = math.nan
                if not math.isnan(low) and not math.isnan(high) and high > 0.0:
                    gain = low / high
                rows.append(
                    {
                        "decoder": decoder,
                        "sigma": _fmt(s),
                        "pair": f"d{d_low}_to_d{d_high}",
                        "gain_ratio": _fmt(gain),
                    }
                )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["decoder", "sigma", "pair", "gain_ratio"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Distance Gain Summary\n\n")
        f.write("| decoder | sigma | pair | gain_ratio |\n")
        f.write("|---|---|---|---|\n")
        for row in rows:
            f.write(f"| {row['decoder']} | {row['sigma']} | {row['pair']} | {row['gain_ratio']} |\n")

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), sharey=True)
    for ax_idx, (d_low, d_high) in enumerate(PAIR_LIST):
        mat = np.full((len(decoders), len(sigmas)), np.nan, dtype=float)
        for i, decoder in enumerate(decoders):
            sub = df[df["decoder"] == decoder]
            for j, sigma in enumerate(sigmas):
                point = sub[sub["sigma"] == sigma]
                by_d = {int(r["distance"]): float(r["ler"]) for _, r in point.iterrows()}
                low = by_d.get(d_low, math.nan)
                high = by_d.get(d_high, math.nan)
                if not math.isnan(low) and not math.isnan(high) and high > 0.0:
                    mat[i, j] = low / high

        im = _heatmap(axes[ax_idx], mat, decoders, sigmas, f"Gain LER(d={d_low}) / LER(d={d_high})")
        cbar = fig.colorbar(im, ax=axes[ax_idx], fraction=0.046, pad=0.04)
        cbar.set_label("Gain ratio")

    fig.suptitle("Distance-Gain Heatmaps")
    fig.tight_layout()

    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{out_prefix}.{ext}", bbox_inches="tight", dpi=180)
    plt.close(fig)

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    for ext in ("png", "pdf", "svg"):
        print(f"wrote {out_prefix}.{ext}")


if __name__ == "__main__":
    raise SystemExit(main())
