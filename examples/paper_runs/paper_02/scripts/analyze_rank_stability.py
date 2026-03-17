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


def _fmt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "nan"
    if math.isnan(x):
        return "nan"
    return f"{x:.6g}"


def _bootstrap_ranks(df: pd.DataFrame, bootstrap: int, seed: int):
    rng = np.random.default_rng(seed)
    sigmas = sorted(df["sigma"].unique().tolist())
    decoders = sorted(df["decoder"].unique().tolist())

    rank_samples = {(decoder, sigma): [] for decoder in decoders for sigma in sigmas}

    by_sigma = {sigma: sub.copy() for sigma, sub in df.groupby("sigma")}

    for _ in range(bootstrap):
        for sigma in sigmas:
            sub = by_sigma[sigma]
            sampled = []
            for _, r in sub.iterrows():
                n = max(int(r["trials"]), 1)
                p = min(max(float(r["ler"]), 0.0), 1.0)
                k = rng.binomial(n, p)
                sampled.append((str(r["decoder"]), k / n))

            sampled.sort(key=lambda t: t[1])
            for rank, (decoder, _) in enumerate(sampled, start=1):
                rank_samples[(decoder, sigma)].append(float(rank))

    rows = []
    for decoder in decoders:
        for sigma in sigmas:
            samples = np.array(rank_samples[(decoder, sigma)], dtype=float)
            if samples.size == 0:
                rows.append(
                    {
                        "decoder": decoder,
                        "sigma": _fmt(sigma),
                        "rank_median": "nan",
                        "rank_p10": "nan",
                        "rank_p90": "nan",
                    }
                )
                continue
            rows.append(
                {
                    "decoder": decoder,
                    "sigma": _fmt(sigma),
                    "rank_median": _fmt(np.percentile(samples, 50.0)),
                    "rank_p10": _fmt(np.percentile(samples, 10.0)),
                    "rank_p90": _fmt(np.percentile(samples, 90.0)),
                }
            )
    return decoders, sigmas, rows


def main():
    parser = argparse.ArgumentParser(description="Compute decoder-rank stability vs sigma.")
    parser.add_argument("--input", required=True)
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

    df = pd.read_csv(args.input)
    if df.empty:
        raise RuntimeError("input CSV is empty")

    df = df.copy()
    df["sigma"] = df["sigma"].astype(float)
    df["trials"] = df["trials"].astype(int)
    df["ler"] = df["ler"].astype(float)

    decoders, sigmas, rows = _bootstrap_ranks(df, args.bootstrap, args.seed)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["decoder", "sigma", "rank_median", "rank_p10", "rank_p90"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Rank Stability Summary\n\n")
        f.write("| decoder | sigma | rank_median | rank_p10 | rank_p90 |\n")
        f.write("|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['decoder']} | {row['sigma']} | {row['rank_median']} | {row['rank_p10']} | {row['rank_p90']} |\n"
            )

    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    for decoder in decoders:
        sub = [r for r in rows if r["decoder"] == decoder]
        x = [float(r["sigma"]) for r in sub]
        y = [float(r["rank_median"]) for r in sub]
        y_lo = [float(r["rank_p10"]) for r in sub]
        y_hi = [float(r["rank_p90"]) for r in sub]
        ax.plot(x, y, marker="o", label=decoder)
        ax.fill_between(x, y_lo, y_hi, alpha=0.18)

    ax.invert_yaxis()
    ax.set_xlabel("Sigma")
    ax.set_ylabel("Decoder rank (1 = best)")
    ax.set_title("Decoder Rank Stability vs Sigma")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")

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
