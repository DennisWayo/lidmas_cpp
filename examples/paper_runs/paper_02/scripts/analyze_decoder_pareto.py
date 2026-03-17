#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _safe_float(value, default=math.nan):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "nan"
    return f"{float(value):.6g}"


def _load_metrics(decoder: str, csv_path: Path, seconds: float, sigma_ref: float):
    df = pd.read_csv(csv_path)
    if df.empty:
        return None
    if "sigma" not in df.columns:
        return None

    df = df.sort_values("sigma")
    sigmas = df["sigma"].astype(float).to_list()
    lers = df["ler"].astype(float).to_list()
    mean_ler = float(df["ler"].mean())

    sigma_min = min(sigmas)
    sigma_max = max(sigmas)
    auc = math.nan
    if sigma_max > sigma_min:
        area = 0.0
        for i in range(len(sigmas) - 1):
            dx = sigmas[i + 1] - sigmas[i]
            area += 0.5 * dx * (lers[i] + lers[i + 1])
        auc = area / (sigma_max - sigma_min)

    nearest_idx = min(range(len(sigmas)), key=lambda i: abs(sigmas[i] - sigma_ref))
    sigma_actual = sigmas[nearest_idx]
    ler_ref = lers[nearest_idx]

    distance = int(df["distance"].iloc[0]) if "distance" in df.columns else -1
    return {
        "decoder": decoder,
        "distance": distance,
        "runtime_seconds": float(seconds),
        "mean_ler": mean_ler,
        "auc_ler": auc,
        "sigma_ref_target": float(sigma_ref),
        "sigma_ref_actual": float(sigma_actual),
        "ler_at_sigma_ref": float(ler_ref),
        "points": int(len(df)),
    }


def _mark_pareto(rows):
    for i, row in enumerate(rows):
        dominated = False
        for j, other in enumerate(rows):
            if i == j:
                continue
            better_or_equal_runtime = other["runtime_seconds"] <= row["runtime_seconds"]
            better_or_equal_ler = other["ler_at_sigma_ref"] <= row["ler_at_sigma_ref"]
            strictly_better = (
                other["runtime_seconds"] < row["runtime_seconds"]
                or other["ler_at_sigma_ref"] < row["ler_at_sigma_ref"]
            )
            if better_or_equal_runtime and better_or_equal_ler and strictly_better:
                dominated = True
                break
        row["pareto_optimal"] = "no" if dominated else "yes"


def _write_md(path: Path, rows, columns):
    with path.open("w", encoding="utf-8") as f:
        f.write("# Decoder Pareto Summary\n\n")
        f.write("| " + " | ".join(columns) + " |\n")
        f.write("|" + "|".join(["---"] * len(columns)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |\n")


def main():
    parser = argparse.ArgumentParser(description="Build decoder Pareto runtime-vs-LER summary.")
    parser.add_argument("--timings", required=True, help="CSV with decoder,seconds,csv_path")
    parser.add_argument("--sigma-ref", type=float, default=0.20)
    parser.add_argument("--style", default="")
    parser.add_argument("--title", default="Decoder Pareto Frontier (GKP)")
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

    rows = []
    for tr in timing_rows:
        decoder = str(tr.get("decoder", "")).strip()
        seconds = _safe_float(tr.get("seconds"))
        csv_path = Path(str(tr.get("csv_path", "")).strip())
        if not decoder or math.isnan(seconds) or not csv_path.exists():
            continue
        metrics = _load_metrics(decoder, csv_path, seconds, args.sigma_ref)
        if metrics is not None:
            rows.append(metrics)

    if not rows:
        raise RuntimeError("no valid decoder timing rows found")

    _mark_pareto(rows)
    rows.sort(key=lambda r: (r["runtime_seconds"], r["ler_at_sigma_ref"]))

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "decoder",
        "distance",
        "runtime_seconds",
        "mean_ler",
        "auc_ler",
        "sigma_ref_target",
        "sigma_ref_actual",
        "ler_at_sigma_ref",
        "points",
        "pareto_optimal",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row[k]) if k not in ("decoder", "pareto_optimal") else row[k] for k in columns})

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    md_rows = []
    for row in rows:
        md_rows.append(
            {
                "decoder": row["decoder"],
                "distance": str(row["distance"]),
                "runtime_seconds": _fmt(row["runtime_seconds"]),
                "mean_ler": _fmt(row["mean_ler"]),
                "auc_ler": _fmt(row["auc_ler"]),
                "sigma_ref_target": _fmt(row["sigma_ref_target"]),
                "sigma_ref_actual": _fmt(row["sigma_ref_actual"]),
                "ler_at_sigma_ref": _fmt(row["ler_at_sigma_ref"]),
                "points": str(row["points"]),
                "pareto_optimal": row["pareto_optimal"],
            }
        )
    _write_md(out_md, md_rows, columns)

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for row in rows:
        x = row["runtime_seconds"]
        y = row["ler_at_sigma_ref"]
        marker = "D" if row["pareto_optimal"] == "yes" else "o"
        size = 80 if row["pareto_optimal"] == "yes" else 60
        ax.scatter([x], [y], marker=marker, s=size)
        ax.annotate(row["decoder"], (x, y), textcoords="offset points", xytext=(6, 4), fontsize=9)

    ax.set_xlabel("Runtime (seconds, full sigma sweep)")
    ax.set_ylabel(f"LER at sigma≈{args.sigma_ref:.3f}")
    ax.set_title(args.title)
    ax.grid(True, alpha=0.3)

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
