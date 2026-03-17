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


def _estimate_crossing(sigmas, low_vals, high_vals):
    diff = low_vals - high_vals
    for i in range(len(sigmas) - 1):
        d0 = diff[i]
        d1 = diff[i + 1]
        s0 = sigmas[i]
        s1 = sigmas[i + 1]
        if math.isnan(d0) or math.isnan(d1):
            continue
        if d0 == 0.0:
            return float(s0)
        if d1 == 0.0:
            return float(s1)
        if d0 * d1 < 0.0:
            t = d0 / (d0 - d1)
            return float(s0 + t * (s1 - s0))
    return math.nan


def main():
    parser = argparse.ArgumentParser(description="Critical-window zoom plot with CI ribbons and crossing estimates.")
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

    df["decoder"] = df["decoder"].astype(str)
    df["distance"] = df["distance"].astype(int)
    df["sigma"] = df["sigma"].astype(float)
    df["ler"] = df["ler"].astype(float)
    df["ci_low"] = df["ci_low"].astype(float)
    df["ci_high"] = df["ci_high"].astype(float)

    decoders = sorted(df["decoder"].unique().tolist())
    distances = sorted(df["distance"].unique().tolist())

    crossing_rows = []
    for decoder in decoders:
        sub = df[df["decoder"] == decoder]
        for low_d, high_d in PAIR_LIST:
            low = sub[sub["distance"] == low_d].sort_values("sigma")
            high = sub[sub["distance"] == high_d].sort_values("sigma")
            common_sigma = sorted(set(low["sigma"].to_list()) & set(high["sigma"].to_list()))
            if len(common_sigma) < 2:
                crossing = math.nan
            else:
                low_v = low[low["sigma"].isin(common_sigma)].sort_values("sigma")["ler"].to_numpy(dtype=float)
                high_v = high[high["sigma"].isin(common_sigma)].sort_values("sigma")["ler"].to_numpy(dtype=float)
                sigmas = np.array(common_sigma, dtype=float)
                crossing = _estimate_crossing(sigmas, low_v, high_v)

            crossing_rows.append(
                {
                    "decoder": decoder,
                    "pair": f"d{low_d}_d{high_d}",
                    "estimated_crossing_sigma": _fmt(crossing),
                }
            )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["decoder", "pair", "estimated_crossing_sigma"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(crossing_rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Critical Window Crossing Summary\n\n")
        f.write("| decoder | pair | estimated_crossing_sigma |\n")
        f.write("|---|---|---|\n")
        for row in crossing_rows:
            f.write(f"| {row['decoder']} | {row['pair']} | {row['estimated_crossing_sigma']} |\n")

    n_cols = 2
    n_rows = math.ceil(len(decoders) / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6.4 * n_cols, 4.8 * n_rows), squeeze=False)
    axes_flat = axes.flatten()

    for idx, decoder in enumerate(decoders):
        ax = axes_flat[idx]
        sub = df[df["decoder"] == decoder]
        for d in distances:
            cur = sub[sub["distance"] == d].sort_values("sigma")
            if cur.empty:
                continue
            x = cur["sigma"].to_numpy(dtype=float)
            y = cur["ler"].to_numpy(dtype=float)
            y_lo = cur["ci_low"].to_numpy(dtype=float)
            y_hi = cur["ci_high"].to_numpy(dtype=float)
            ax.plot(x, y, marker="o", label=f"d={d}")
            ax.fill_between(x, y_lo, y_hi, alpha=0.18)

        ax.set_title(f"{decoder} critical-window zoom")
        ax.set_xlabel("Sigma")
        ax.set_ylabel("LER")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")

    for j in range(len(decoders), len(axes_flat)):
        axes_flat[j].axis("off")

    fig.suptitle("Critical-Window Zoom with CI Ribbons")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

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
