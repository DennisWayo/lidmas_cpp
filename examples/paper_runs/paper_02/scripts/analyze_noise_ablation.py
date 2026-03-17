#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


COMPONENT_ORDER = ["gate", "meas", "idle", "loss"]


def _fmt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "nan"
    if math.isnan(x):
        return "nan"
    return f"{x:.6g}"


def _load_ler(csv_path: Path):
    df = pd.read_csv(csv_path)
    if df.empty or "ler" not in df.columns:
        return math.nan
    return float(df["ler"].mean())


def main():
    parser = argparse.ArgumentParser(description="Summarize GKP noise-component ablation sweeps.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--style", default="")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    if args.style:
        style_path = Path(args.style)
        if style_path.exists():
            plt.style.use(style_path)

    manifest = pd.read_csv(args.manifest)
    if manifest.empty:
        raise RuntimeError("ablation manifest is empty")

    manifest["level"] = manifest["level"].astype(float)

    point_rows = []
    for _, r in manifest.iterrows():
        csv_path = Path(str(r["csv_path"]))
        ler = _load_ler(csv_path) if csv_path.exists() else math.nan
        point_rows.append(
            {
                "decoder": str(r["decoder"]),
                "component": str(r["component"]),
                "level": float(r["level"]),
                "runtime_seconds": _fmt(r.get("seconds", math.nan)),
                "ler": _fmt(ler),
            }
        )

    points_df = pd.DataFrame(point_rows)

    summary_rows = []
    for (decoder, component), sub in points_df.groupby(["decoder", "component"]):
        sub = sub.sort_values("level")
        levels = sub["level"].astype(float).to_list()
        lers = [float(x) for x in sub["ler"].to_list()]
        if len(levels) < 2:
            slope = math.nan
        else:
            dx = levels[-1] - levels[0]
            slope = (lers[-1] - lers[0]) / dx if dx != 0.0 else math.nan
        summary_rows.append(
            {
                "decoder": decoder,
                "component": component,
                "min_level": _fmt(min(levels) if levels else math.nan),
                "max_level": _fmt(max(levels) if levels else math.nan),
                "ler_min_level": _fmt(lers[0] if lers else math.nan),
                "ler_max_level": _fmt(lers[-1] if lers else math.nan),
                "delta_ler": _fmt((lers[-1] - lers[0]) if len(lers) >= 2 else math.nan),
                "slope_dler_dnoise": _fmt(slope),
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "decoder",
            "component",
            "min_level",
            "max_level",
            "ler_min_level",
            "ler_max_level",
            "delta_ler",
            "slope_dler_dnoise",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Noise Ablation Summary\n\n")
        f.write("| decoder | component | min_level | max_level | ler_min_level | ler_max_level | delta_ler | slope_dler_dnoise |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for row in summary_rows:
            f.write(
                f"| {row['decoder']} | {row['component']} | {row['min_level']} | {row['max_level']} | {row['ler_min_level']} | {row['ler_max_level']} | {row['delta_ler']} | {row['slope_dler_dnoise']} |\n"
            )

    decoders = sorted(points_df["decoder"].unique().tolist())
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0), sharex=False, sharey=True)
    axes = axes.flatten()

    for i, component in enumerate(COMPONENT_ORDER):
        ax = axes[i]
        sub_c = points_df[points_df["component"] == component]
        for decoder in decoders:
            sub = sub_c[sub_c["decoder"] == decoder].sort_values("level")
            if sub.empty:
                continue
            x = sub["level"].astype(float).to_list()
            y = [float(v) for v in sub["ler"].to_list()]
            ax.plot(x, y, marker="o", label=decoder)
        ax.set_title(f"{component} noise ablation")
        ax.set_xlabel("Noise level")
        ax.set_ylabel("LER")
        ax.grid(True, alpha=0.25)

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=max(1, min(4, len(labels))))
    fig.suptitle("Noise-Component Ablation (Native GKP)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{out_prefix}.{ext}", bbox_inches="tight", dpi=180)
    plt.close(fig)

    points_csv = out_prefix.parent / "table_noise_ablation_points.csv"
    points_df.to_csv(points_csv, index=False)

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    print(f"Wrote {points_csv}")
    for ext in ("png", "pdf", "svg"):
        print(f"wrote {out_prefix}.{ext}")


if __name__ == "__main__":
    raise SystemExit(main())
