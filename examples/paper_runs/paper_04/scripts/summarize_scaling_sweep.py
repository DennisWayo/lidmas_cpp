#!/usr/bin/env python3
"""Summarize paper_04 scaling sweep runs and export publication-ready scaling figures."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Scaling sweep manifest CSV.")
    parser.add_argument("--out-csv", required=True, help="Aggregated per-shot summary CSV.")
    parser.add_argument("--out-md", required=True, help="Aggregated per-shot summary Markdown.")
    parser.add_argument("--out-decoder-csv", required=True, help="Per-shot per-decoder summary CSV.")
    parser.add_argument("--out-prefix", required=True, help="Figure output prefix without extension.")
    return parser.parse_args()


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _fmt(value: Any) -> str:
    x = _f(value)
    if np.isnan(x):
        return "nan"
    return f"{x:.6f}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _group_values(rows: list[dict[str, str]], key: str, value_key: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for row in rows:
        k = (row.get(key) or "").strip()
        if not k:
            continue
        v = _f(row.get(value_key))
        if np.isnan(v):
            continue
        out.setdefault(k, []).append(v)
    return out


def _summarize_run(matrix_csv: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not matrix_csv.exists():
        return (
            {
                "status": "missing_matrix",
                "n_rows": 0,
                "n_datasets": 0,
                "n_decoders": 0,
                "mean_avg_flip_count": float("nan"),
                "mean_warning_rate": float("nan"),
                "mean_response_ratio": float("nan"),
                "mean_decoder_spread_per_dataset": float("nan"),
            },
            [],
        )

    rows = _read_csv(matrix_csv)
    ok_rows = [r for r in rows if (r.get("status") or "").strip() == "ok"]
    if not ok_rows:
        return (
            {
                "status": "no_ok_rows",
                "n_rows": 0,
                "n_datasets": 0,
                "n_decoders": 0,
                "mean_avg_flip_count": float("nan"),
                "mean_warning_rate": float("nan"),
                "mean_response_ratio": float("nan"),
                "mean_decoder_spread_per_dataset": float("nan"),
            },
            [],
        )

    datasets = sorted({(r.get("dataset") or "").strip() for r in ok_rows if (r.get("dataset") or "").strip()})
    decoders = sorted({(r.get("decoder") or "").strip() for r in ok_rows if (r.get("decoder") or "").strip()})

    mean_avg_flip = float(np.mean([_f(r.get("avg_flip_count")) for r in ok_rows]))
    mean_warning = float(np.mean([_f(r.get("warning_no_syndrome_rate")) for r in ok_rows]))
    mean_response_ratio = float(np.mean([_f(r.get("response_ratio")) for r in ok_rows]))

    spreads: list[float] = []
    per_decoder_rows: list[dict[str, Any]] = []
    decoder_flip = _group_values(ok_rows, "decoder", "avg_flip_count")
    decoder_warn = _group_values(ok_rows, "decoder", "warning_no_syndrome_rate")
    for decoder in decoders:
        per_decoder_rows.append(
            {
                "decoder": decoder,
                "mean_avg_flip_count": float(np.mean(decoder_flip.get(decoder, [float("nan")]))),
                "mean_warning_rate": float(np.mean(decoder_warn.get(decoder, [float("nan")]))),
                "n_rows": len(decoder_flip.get(decoder, [])),
            }
        )

    by_dataset: dict[str, list[float]] = {}
    for row in ok_rows:
        dataset = (row.get("dataset") or "").strip()
        if not dataset:
            continue
        by_dataset.setdefault(dataset, []).append(_f(row.get("avg_flip_count")))
    for vals in by_dataset.values():
        vals_arr = np.asarray([v for v in vals if not np.isnan(v)], dtype=float)
        if vals_arr.size <= 1:
            continue
        spreads.append(float(np.max(vals_arr) - np.min(vals_arr)))

    return (
        {
            "status": "ok",
            "n_rows": len(ok_rows),
            "n_datasets": len(datasets),
            "n_decoders": len(decoders),
            "mean_avg_flip_count": mean_avg_flip,
            "mean_warning_rate": mean_warning,
            "mean_response_ratio": mean_response_ratio,
            "mean_decoder_spread_per_dataset": float(np.mean(spreads)) if spreads else float("nan"),
        },
        per_decoder_rows,
    )


def _write_csv(rows: list[dict[str, Any]], fieldnames: list[str], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fieldnames:
                if key.startswith("mean_") or key.endswith("_s") or key == "shot":
                    if key in out:
                        out[key] = _fmt(out[key]) if key != "shot" else str(int(float(out[key])))
            writer.writerow(out)


def _write_md(rows: list[dict[str, Any]], out_md: Path) -> None:
    headers = [
        "shot",
        "status",
        "elapsed_total_s",
        "elapsed_generate_s",
        "elapsed_replay_s",
        "elapsed_analysis_s",
        "mean_avg_flip_count",
        "mean_warning_rate",
        "mean_decoder_spread_per_dataset",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals = []
            for h in headers:
                if h == "shot":
                    vals.append(str(int(float(row.get(h, 0) or 0))))
                elif h == "status":
                    vals.append(str(row.get(h, "")))
                else:
                    vals.append(_fmt(row.get(h)))
            f.write("| " + " | ".join(vals) + " |\n")


def _plot(shot_rows: list[dict[str, Any]], decoder_rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping scaling figure export ({exc}).")
        return

    valid_shots = [r for r in shot_rows if str(r.get("status", "")) == "ok"]
    if not valid_shots:
        return

    valid_shots = sorted(valid_shots, key=lambda r: int(float(r.get("shot", 0))))
    x = np.asarray([int(float(r["shot"])) for r in valid_shots], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), dpi=320, constrained_layout=True)

    total = np.asarray([_f(r.get("elapsed_total_s")) for r in valid_shots], dtype=float)
    gen = np.asarray([_f(r.get("elapsed_generate_s")) for r in valid_shots], dtype=float)
    rep = np.asarray([_f(r.get("elapsed_replay_s")) for r in valid_shots], dtype=float)
    ana = np.asarray([_f(r.get("elapsed_analysis_s")) for r in valid_shots], dtype=float)

    axes[0].plot(x, total, marker="o", linewidth=1.5, color="#1f77b4", label="total")
    axes[0].plot(x, gen, marker="o", linewidth=1.2, color="#2ca02c", label="generate")
    axes[0].plot(x, rep, marker="o", linewidth=1.2, color="#ff7f0e", label="replay")
    axes[0].plot(x, ana, marker="o", linewidth=1.2, color="#9467bd", label="analysis")
    if len(np.unique(x)) > 1:
        axes[0].set_xscale("log")
    axes[0].set_title("Pipeline Runtime vs Shot Count")
    axes[0].set_xlabel("Shots")
    axes[0].set_ylabel("Seconds")
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8)

    decoders = sorted({str(r.get("decoder", "")) for r in decoder_rows if str(r.get("decoder", ""))})
    palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf"]
    for i, decoder in enumerate(decoders):
        rows = [r for r in decoder_rows if str(r.get("decoder", "")) == decoder and str(r.get("status", "")) == "ok"]
        rows = sorted(rows, key=lambda r: int(float(r.get("shot", 0))))
        if not rows:
            continue
        x_dec = np.asarray([int(float(r["shot"])) for r in rows], dtype=float)
        y_dec = np.asarray([_f(r.get("mean_avg_flip_count")) for r in rows], dtype=float)
        axes[1].plot(x_dec, y_dec, marker="o", linewidth=1.3, color=palette[i % len(palette)], label=decoder)

    if len(np.unique(x)) > 1:
        axes[1].set_xscale("log")
    axes[1].set_title("Decoder Mean Flip Count Stability")
    axes[1].set_xlabel("Shots")
    axes[1].set_ylabel("Mean flips/request")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    manifest_rows = _read_csv(Path(args.manifest))
    shot_rows: list[dict[str, Any]] = []
    decoder_rows: list[dict[str, Any]] = []

    for row in manifest_rows:
        shot = int(float(row.get("shot", 0) or 0))
        results_base = str(row.get("results_base", "")).strip()
        matrix_csv = Path(results_base) / "03_analysis" / "table_replay_matrix.csv"
        summary, per_decoder = _summarize_run(matrix_csv)

        shot_row: dict[str, Any] = {
            "shot": shot,
            "results_base": results_base,
            "status": summary["status"],
            "elapsed_generate_s": _f(row.get("elapsed_generate_s")),
            "elapsed_replay_s": _f(row.get("elapsed_replay_s")),
            "elapsed_analysis_s": _f(row.get("elapsed_analysis_s")),
            "elapsed_total_s": _f(row.get("elapsed_total_s")),
            "n_rows": summary["n_rows"],
            "n_datasets": summary["n_datasets"],
            "n_decoders": summary["n_decoders"],
            "mean_avg_flip_count": summary["mean_avg_flip_count"],
            "mean_warning_rate": summary["mean_warning_rate"],
            "mean_response_ratio": summary["mean_response_ratio"],
            "mean_decoder_spread_per_dataset": summary["mean_decoder_spread_per_dataset"],
        }
        shot_rows.append(shot_row)

        for dec_row in per_decoder:
            decoder_rows.append(
                {
                    "shot": shot,
                    "status": summary["status"],
                    "decoder": dec_row["decoder"],
                    "mean_avg_flip_count": dec_row["mean_avg_flip_count"],
                    "mean_warning_rate": dec_row["mean_warning_rate"],
                    "n_rows": dec_row["n_rows"],
                }
            )

    shot_fields = [
        "shot",
        "status",
        "results_base",
        "elapsed_generate_s",
        "elapsed_replay_s",
        "elapsed_analysis_s",
        "elapsed_total_s",
        "n_rows",
        "n_datasets",
        "n_decoders",
        "mean_avg_flip_count",
        "mean_warning_rate",
        "mean_response_ratio",
        "mean_decoder_spread_per_dataset",
    ]
    decoder_fields = [
        "shot",
        "status",
        "decoder",
        "mean_avg_flip_count",
        "mean_warning_rate",
        "n_rows",
    ]

    _write_csv(shot_rows, shot_fields, Path(args.out_csv))
    _write_md(shot_rows, Path(args.out_md))
    _write_csv(decoder_rows, decoder_fields, Path(args.out_decoder_csv))
    _plot(shot_rows, decoder_rows, Path(args.out_prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
