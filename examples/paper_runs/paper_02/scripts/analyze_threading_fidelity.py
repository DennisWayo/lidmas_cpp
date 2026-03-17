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


def _load_curve(path: Path, mode: str):
    df = pd.read_csv(path)
    x_col = "pauli_p" if mode == "pauli" else "sigma"
    if x_col not in df.columns:
        x_col = "sigma" if "sigma" in df.columns else "pauli_p"
    key_cols = ["distance", x_col]
    merged = df[key_cols + ["ler", "decoder_fail_rate"]].copy()
    merged["distance"] = merged["distance"].astype(int)
    merged[x_col] = merged[x_col].astype(float)
    merged["ler"] = merged["ler"].astype(float)
    merged["decoder_fail_rate"] = merged["decoder_fail_rate"].astype(float)
    return merged, x_col


def _find_row(rows, label):
    for r in rows:
        if str(r.get("label", "")) == label:
            return r
    return None


def main():
    parser = argparse.ArgumentParser(description="Create serial-vs-threaded fidelity scatter checks.")
    parser.add_argument("--timings", required=True)
    parser.add_argument("--style", default="")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    if args.style:
        style_path = Path(args.style)
        if style_path.exists():
            plt.style.use(style_path)

    with Path(args.timings).open(newline="", encoding="utf-8") as f:
        timing_rows = list(csv.DictReader(f))
    if not timing_rows:
        raise RuntimeError("timings CSV is empty")

    modes = sorted(set(str(r.get("mode", "")) for r in timing_rows if r.get("mode")))
    summary = []

    fig, axes = plt.subplots(1, max(1, len(modes)), figsize=(6.0 * max(1, len(modes)), 5.0), squeeze=False)

    for idx, mode in enumerate(modes):
        ax = axes[0][idx]
        serial_row = _find_row(timing_rows, f"{mode}_serial")
        threaded_row = _find_row(timing_rows, f"{mode}_threaded")
        if serial_row is None or threaded_row is None:
            ax.set_title(f"{mode}: missing serial/threaded pair")
            ax.axis("off")
            continue

        serial_df, x_col = _load_curve(Path(serial_row["csv_path"]), mode)
        threaded_df, _ = _load_curve(Path(threaded_row["csv_path"]), mode)

        merged = serial_df.merge(
            threaded_df,
            on=["distance", x_col],
            suffixes=("_serial", "_threaded"),
        )

        if merged.empty:
            ax.set_title(f"{mode}: no overlap")
            ax.axis("off")
            continue

        x = merged["ler_serial"].to_numpy(dtype=float)
        y = merged["ler_threaded"].to_numpy(dtype=float)
        deltas = np.abs(y - x)
        mean_abs = float(np.mean(deltas))
        max_abs = float(np.max(deltas))
        corr = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else math.nan

        serial_seconds = float(serial_row.get("seconds", "nan"))
        threaded_seconds = float(threaded_row.get("seconds", "nan"))
        speedup = serial_seconds / threaded_seconds if threaded_seconds > 0.0 else math.nan

        summary.append(
            {
                "mode": mode,
                "points": str(len(merged)),
                "mean_abs_delta_ler": _fmt(mean_abs),
                "max_abs_delta_ler": _fmt(max_abs),
                "corr_serial_threaded": _fmt(corr),
                "serial_seconds": _fmt(serial_seconds),
                "threaded_seconds": _fmt(threaded_seconds),
                "speedup": _fmt(speedup),
            }
        )

        ax.scatter(x, y, s=36, alpha=0.85)
        lo = min(float(np.min(x)), float(np.min(y)))
        hi = max(float(np.max(x)), float(np.max(y)))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1.0, label="identity")
        ax.set_title(f"{mode}: serial vs threaded")
        ax.set_xlabel("LER (serial)")
        ax.set_ylabel("LER (threaded)")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")

    fig.suptitle("Threading Fidelity Check")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "mode",
        "points",
        "mean_abs_delta_ler",
        "max_abs_delta_ler",
        "corr_serial_threaded",
        "serial_seconds",
        "threaded_seconds",
        "speedup",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Threading Fidelity Summary\n\n")
        f.write("| mode | points | mean_abs_delta_ler | max_abs_delta_ler | corr_serial_threaded | serial_seconds | threaded_seconds | speedup |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for row in summary:
            f.write(
                f"| {row['mode']} | {row['points']} | {row['mean_abs_delta_ler']} | {row['max_abs_delta_ler']} | {row['corr_serial_threaded']} | {row['serial_seconds']} | {row['threaded_seconds']} | {row['speedup']} |\n"
            )

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
