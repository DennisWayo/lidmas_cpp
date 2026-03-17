#!/usr/bin/env python3
import argparse
import csv
import itertools
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd


def _fmt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "nan"
    if math.isnan(x):
        return "nan"
    return f"{x:.6g}"


def _pair_bootstrap(a_df, b_df, bootstrap: int, seed: int):
    rng = np.random.default_rng(seed)
    common_sigma = sorted(set(a_df["sigma"].to_list()) & set(b_df["sigma"].to_list()))
    if not common_sigma:
        return np.array([], dtype=float)

    a = a_df[a_df["sigma"].isin(common_sigma)].sort_values("sigma")
    b = b_df[b_df["sigma"].isin(common_sigma)].sort_values("sigma")

    a_n = a["trials"].astype(int).to_numpy()
    a_p = a["ler"].astype(float).to_numpy()
    b_n = b["trials"].astype(int).to_numpy()
    b_p = b["ler"].astype(float).to_numpy()

    deltas = np.zeros(bootstrap, dtype=float)
    for i in range(bootstrap):
        a_rate = rng.binomial(a_n, a_p) / np.maximum(a_n, 1)
        b_rate = rng.binomial(b_n, b_p) / np.maximum(b_n, 1)
        deltas[i] = float(np.mean(a_rate - b_rate))
    return deltas


def main():
    parser = argparse.ArgumentParser(description="Pairwise bootstrap effect sizes between decoders.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1337)
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

    df = df.copy()
    df["sigma"] = df["sigma"].astype(float)
    df["ler"] = df["ler"].astype(float)
    df["trials"] = df["trials"].astype(int)

    decoders = sorted(df["decoder"].unique().tolist())

    rows = []
    mean_matrix = np.zeros((len(decoders), len(decoders)), dtype=float)

    pair_idx = 0
    for i, j in itertools.combinations(range(len(decoders)), 2):
        a = decoders[i]
        b = decoders[j]
        a_df = df[df["decoder"] == a]
        b_df = df[df["decoder"] == b]
        deltas = _pair_bootstrap(a_df, b_df, args.bootstrap, args.seed + 53 * pair_idx)
        pair_idx += 1
        if deltas.size == 0:
            continue

        mean_delta = float(np.mean(deltas))
        med_delta = float(np.median(deltas))
        p05 = float(np.percentile(deltas, 5.0))
        p95 = float(np.percentile(deltas, 95.0))
        win_rate = float(np.mean(deltas < 0.0))  # A better than B

        mean_matrix[i, j] = mean_delta
        mean_matrix[j, i] = -mean_delta

        rows.append(
            {
                "decoder_a": a,
                "decoder_b": b,
                "mean_delta_ler_a_minus_b": _fmt(mean_delta),
                "median_delta_ler_a_minus_b": _fmt(med_delta),
                "p05": _fmt(p05),
                "p95": _fmt(p95),
                "p_a_better": _fmt(win_rate),
                "bootstrap_samples": str(args.bootstrap),
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "decoder_a",
        "decoder_b",
        "mean_delta_ler_a_minus_b",
        "median_delta_ler_a_minus_b",
        "p05",
        "p95",
        "p_a_better",
        "bootstrap_samples",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Pairwise Effect Size Summary\n\n")
        f.write("| decoder_a | decoder_b | mean_delta_ler_a_minus_b | median_delta_ler_a_minus_b | p05 | p95 | p_a_better | bootstrap_samples |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['decoder_a']} | {row['decoder_b']} | {row['mean_delta_ler_a_minus_b']} | {row['median_delta_ler_a_minus_b']} | {row['p05']} | {row['p95']} | {row['p_a_better']} | {row['bootstrap_samples']} |\n"
            )

    vmax = float(np.nanmax(np.abs(mean_matrix))) if mean_matrix.size else 1.0
    if vmax == 0.0:
        vmax = 1.0

    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = ax.imshow(mean_matrix, cmap="coolwarm", norm=norm)
    ax.set_xticks(range(len(decoders)))
    ax.set_xticklabels(decoders, rotation=45, ha="right")
    ax.set_yticks(range(len(decoders)))
    ax.set_yticklabels(decoders)
    ax.set_title("Mean delta LER (row - column)")

    for i in range(len(decoders)):
        for j in range(len(decoders)):
            ax.text(j, i, f"{mean_matrix[i, j]:.3f}", ha="center", va="center", fontsize=8)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Mean delta LER")
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
