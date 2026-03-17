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


def _fmt(value):
    if value is None:
        return "nan"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "nan"
    if math.isnan(value):
        return "nan"
    return f"{value:.6g}"


def _estimate_crossing(sigmas, y_low, y_high):
    diff = y_low - y_high
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


def _load_decoder_rows(label_and_path):
    label, path = label_and_path.split("=", 1)
    df = pd.read_csv(path)
    if "sigma" not in df.columns or "distance" not in df.columns:
        raise RuntimeError(f"missing required columns in {path}")
    df["sigma"] = df["sigma"].astype(float)
    df["distance"] = df["distance"].astype(int)
    df["ler"] = df["ler"].astype(float)
    df["trials"] = df["trials"].astype(int)
    return label, df


def _bootstrap_decoder(df: pd.DataFrame, n_bootstrap: int, seed: int):
    rng = np.random.default_rng(seed)
    out = {pair: [] for pair in PAIR_LIST}

    by_distance = {d: sub.sort_values("sigma") for d, sub in df.groupby("distance")}

    for low_d, high_d in PAIR_LIST:
        if low_d not in by_distance or high_d not in by_distance:
            continue

        low_df = by_distance[low_d]
        high_df = by_distance[high_d]
        common_sigma = sorted(set(low_df["sigma"].to_list()) & set(high_df["sigma"].to_list()))
        if len(common_sigma) < 2:
            continue

        low_df = low_df[low_df["sigma"].isin(common_sigma)].sort_values("sigma")
        high_df = high_df[high_df["sigma"].isin(common_sigma)].sort_values("sigma")

        sigmas = low_df["sigma"].to_numpy(dtype=float)
        low_p = low_df["ler"].to_numpy(dtype=float)
        high_p = high_df["ler"].to_numpy(dtype=float)
        low_n = low_df["trials"].to_numpy(dtype=int)
        high_n = high_df["trials"].to_numpy(dtype=int)

        for _ in range(n_bootstrap):
            low_k = rng.binomial(low_n, low_p)
            high_k = rng.binomial(high_n, high_p)
            low_rate = low_k / np.maximum(low_n, 1)
            high_rate = high_k / np.maximum(high_n, 1)
            crossing = _estimate_crossing(sigmas, low_rate, high_rate)
            out[(low_d, high_d)].append(crossing)

    return out


def _write_md(path: Path, rows, fields):
    with path.open("w", encoding="utf-8") as f:
        f.write("# Crossing Bootstrap Summary\n\n")
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("|" + "|".join(["---"] * len(fields)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(row.get(field, "") for field in fields) + " |\n")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap crossing stability for decoder threshold crossings.")
    parser.add_argument("--input", action="append", required=True, help="decoder=path/to/results.csv")
    parser.add_argument("--bootstrap", type=int, default=1500)
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

    decoder_frames = [_load_decoder_rows(item) for item in args.input]

    all_distributions = {}
    summary_rows = []

    for idx, (decoder, df) in enumerate(decoder_frames):
        boot = _bootstrap_decoder(df, args.bootstrap, args.seed + 97 * idx)
        for pair in PAIR_LIST:
            samples = np.array([x for x in boot.get(pair, []) if not math.isnan(x)], dtype=float)
            key = (decoder, pair)
            all_distributions[key] = samples

            if samples.size == 0:
                summary_rows.append(
                    {
                        "decoder": decoder,
                        "pair": f"d{pair[0]}_d{pair[1]}",
                        "median_sigma": "nan",
                        "p05_sigma": "nan",
                        "p95_sigma": "nan",
                        "n_valid": "0",
                        "n_bootstrap": str(args.bootstrap),
                    }
                )
                continue

            summary_rows.append(
                {
                    "decoder": decoder,
                    "pair": f"d{pair[0]}_d{pair[1]}",
                    "median_sigma": _fmt(np.nanmedian(samples)),
                    "p05_sigma": _fmt(np.nanpercentile(samples, 5.0)),
                    "p95_sigma": _fmt(np.nanpercentile(samples, 95.0)),
                    "n_valid": str(int(samples.size)),
                    "n_bootstrap": str(args.bootstrap),
                }
            )

    fields = ["decoder", "pair", "median_sigma", "p05_sigma", "p95_sigma", "n_valid", "n_bootstrap"]

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _write_md(out_md, summary_rows, fields)

    decoders = [decoder for decoder, _ in decoder_frames]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), sharey=False)

    for ax_idx, pair in enumerate(PAIR_LIST):
        ax = axes[ax_idx]
        series = []
        labels = []
        for decoder in decoders:
            samples = all_distributions.get((decoder, pair), np.array([], dtype=float))
            if samples.size == 0:
                continue
            series.append(samples)
            labels.append(decoder)

        if series:
            ax.boxplot(series, tick_labels=labels, showfliers=False)
        ax.set_title(f"Crossing distribution: d={pair[0]} vs d={pair[1]}")
        ax.set_xlabel("Decoder")
        ax.set_ylabel("Crossing sigma")
        ax.grid(True, alpha=0.25)

    fig.suptitle("Bootstrap Crossing Stability")
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
