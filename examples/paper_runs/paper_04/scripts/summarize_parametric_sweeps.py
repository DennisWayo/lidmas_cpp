#!/usr/bin/env python3
"""Summarize paper_04 parametric sweeps and export journal-ready figures."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Parametric sweep manifest CSV.")
    parser.add_argument("--out-run-csv", required=True, help="Run-level enriched summary CSV.")
    parser.add_argument("--out-noise-rounds-csv", required=True, help="Noise-rounds per-decoder CSV.")
    parser.add_argument("--out-distance-csv", required=True, help="Distance-sweep per-decoder CSV.")
    parser.add_argument("--out-prefix-noise-rounds", required=True, help="Noise-rounds figure prefix.")
    parser.add_argument("--out-prefix-distance", required=True, help="Distance figure prefix.")
    return parser.parse_args()


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _fmt(value: Any) -> str:
    v = _f(value)
    if np.isnan(v):
        return "nan"
    return f"{v:.6f}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list[dict[str, Any]], fieldnames: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fieldnames:
                if key.startswith("mean_") or key.endswith("_s") or key in {"noise_rate", "rounds", "distance", "shots"}:
                    if key in out and key not in {"sweep_type", "results_base", "status", "decoder"}:
                        if key in {"rounds", "distance", "shots"} and not np.isnan(_f(out[key])):
                            out[key] = str(int(round(_f(out[key]))))
                        else:
                            out[key] = _fmt(out[key])
            writer.writerow(out)


def _run_summary(matrix_csv: Path) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    if not matrix_csv.exists():
        return "missing_matrix", [], {
            "n_rows": 0,
            "n_datasets": 0,
            "n_decoders": 0,
            "mean_avg_flip_count": float("nan"),
            "mean_warning_rate": float("nan"),
        }

    rows = _read_csv(matrix_csv)
    ok_rows = [r for r in rows if (r.get("status") or "").strip() == "ok"]
    if not ok_rows:
        return "no_ok_rows", [], {
            "n_rows": 0,
            "n_datasets": 0,
            "n_decoders": 0,
            "mean_avg_flip_count": float("nan"),
            "mean_warning_rate": float("nan"),
        }

    decoders = sorted({(r.get("decoder") or "").strip() for r in ok_rows if (r.get("decoder") or "").strip()})
    datasets = sorted({(r.get("dataset") or "").strip() for r in ok_rows if (r.get("dataset") or "").strip()})

    decoder_rows: list[dict[str, Any]] = []
    for dec in decoders:
        sub = [r for r in ok_rows if (r.get("decoder") or "").strip() == dec]
        decoder_rows.append(
            {
                "decoder": dec,
                "mean_avg_flip_count": float(np.mean([_f(r.get("avg_flip_count")) for r in sub])) if sub else float("nan"),
                "mean_warning_rate": float(np.mean([_f(r.get("warning_no_syndrome_rate")) for r in sub])) if sub else float("nan"),
                "n_rows": len(sub),
            }
        )

    summary = {
        "n_rows": len(ok_rows),
        "n_datasets": len(datasets),
        "n_decoders": len(decoders),
        "mean_avg_flip_count": float(np.mean([_f(r.get("avg_flip_count")) for r in ok_rows])),
        "mean_warning_rate": float(np.mean([_f(r.get("warning_no_syndrome_rate")) for r in ok_rows])),
    }
    return "ok", decoder_rows, summary


def _plot_noise_rounds(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping noise-rounds figure export ({exc}).")
        return

    sel = [r for r in rows if str(r.get("sweep_type", "")) == "noise_rounds" and str(r.get("status", "")) == "ok"]
    if not sel:
        return

    decoders = sorted({str(r.get("decoder", "")) for r in sel if str(r.get("decoder", ""))})
    noises = sorted({float(r.get("noise_rate")) for r in sel if np.isfinite(_f(r.get("noise_rate")))})
    rounds = sorted({int(round(_f(r.get("rounds")))) for r in sel if np.isfinite(_f(r.get("rounds")))})
    if not decoders or not noises or not rounds:
        return

    cols = min(3, len(decoders))
    nrows = int(math.ceil(len(decoders) / float(cols)))
    fig, axes = plt.subplots(nrows, cols, figsize=(4.1 * cols, 3.7 * nrows), dpi=320, constrained_layout=True)
    axes_arr = np.atleast_1d(axes).reshape(nrows, cols)
    im = None

    for idx, dec in enumerate(decoders):
        ax = axes_arr[idx // cols, idx % cols]
        mat = np.full((len(rounds), len(noises)), np.nan, dtype=float)
        for r_i, r_val in enumerate(rounds):
            for n_i, n_val in enumerate(noises):
                cand = [
                    x
                    for x in sel
                    if str(x.get("decoder", "")) == dec
                    and int(round(_f(x.get("rounds")))) == r_val
                    and abs(_f(x.get("noise_rate")) - n_val) < 1e-12
                ]
                if cand:
                    mat[r_i, n_i] = _f(cand[0].get("mean_avg_flip_count"))
        im = ax.imshow(mat, origin="lower", aspect="auto", cmap="YlGnBu")
        ax.set_title(dec)
        ax.set_xticks(np.arange(len(noises)))
        ax.set_xticklabels([f"{n:.2f}" for n in noises], fontsize=8)
        ax.set_yticks(np.arange(len(rounds)))
        ax.set_yticklabels([str(r) for r in rounds], fontsize=8)
        ax.set_xlabel("Error rate")
        ax.set_ylabel("Rounds")
        for r_i in range(len(rounds)):
            for n_i in range(len(noises)):
                if np.isnan(mat[r_i, n_i]):
                    continue
                ax.text(n_i, r_i, f"{mat[r_i, n_i]:.2f}", ha="center", va="center", fontsize=7, color="black")

    for idx in range(len(decoders), nrows * cols):
        ax = axes_arr[idx // cols, idx % cols]
        ax.axis("off")

    fig.suptitle("Noise-Rounds Sensitivity (Mean Flip Count)", y=1.02)
    if im is not None:
        cbar = fig.colorbar(im, ax=axes_arr, fraction=0.022, pad=0.02)
        cbar.set_label("Mean flips/request")

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _plot_distance(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping distance sweep figure export ({exc}).")
        return

    sel = [r for r in rows if str(r.get("sweep_type", "")) == "distance" and str(r.get("status", "")) == "ok"]
    if not sel:
        return

    decoders = sorted({str(r.get("decoder", "")) for r in sel if str(r.get("decoder", ""))})
    distances = sorted({int(round(_f(r.get("distance")))) for r in sel if np.isfinite(_f(r.get("distance")))})
    if not decoders or not distances:
        return

    palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=320, constrained_layout=True)
    for i, dec in enumerate(decoders):
        ys = []
        for d in distances:
            cand = [x for x in sel if str(x.get("decoder", "")) == dec and int(round(_f(x.get("distance")))) == d]
            ys.append(_f(cand[0].get("mean_avg_flip_count")) if cand else float("nan"))
        ax.plot(distances, ys, marker="o", linewidth=1.4, color=palette[i % len(palette)], label=dec)

    ax.set_title("Distance Sweep (Mean Flip Count)")
    ax.set_xlabel("Code distance")
    ax.set_ylabel("Mean flips/request")
    ax.set_xticks(distances)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    manifest_rows = _read_csv(Path(args.manifest))

    run_rows: list[dict[str, Any]] = []
    decoder_rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        sweep_type = str(row.get("sweep_type", "")).strip()
        noise_rate = _f(row.get("noise_rate"))
        rounds = _f(row.get("rounds"))
        distance = _f(row.get("distance"))
        shots = _f(row.get("shots"))
        results_base = str(row.get("results_base", "")).strip()
        matrix_csv = Path(results_base) / "03_analysis" / "table_replay_matrix.csv"
        status, dec_rows, summary = _run_summary(matrix_csv)

        run_rows.append(
            {
                "sweep_type": sweep_type,
                "noise_rate": noise_rate,
                "rounds": rounds,
                "distance": distance,
                "shots": shots,
                "results_base": results_base,
                "elapsed_generate_s": _f(row.get("elapsed_generate_s")),
                "elapsed_replay_s": _f(row.get("elapsed_replay_s")),
                "elapsed_analysis_s": _f(row.get("elapsed_analysis_s")),
                "elapsed_total_s": _f(row.get("elapsed_total_s")),
                "status": status,
                "n_rows": summary["n_rows"],
                "n_datasets": summary["n_datasets"],
                "n_decoders": summary["n_decoders"],
                "mean_avg_flip_count": summary["mean_avg_flip_count"],
                "mean_warning_rate": summary["mean_warning_rate"],
            }
        )
        for drow in dec_rows:
            decoder_rows.append(
                {
                    "sweep_type": sweep_type,
                    "noise_rate": noise_rate,
                    "rounds": rounds,
                    "distance": distance,
                    "shots": shots,
                    "status": status,
                    "decoder": drow["decoder"],
                    "mean_avg_flip_count": drow["mean_avg_flip_count"],
                    "mean_warning_rate": drow["mean_warning_rate"],
                    "n_rows": drow["n_rows"],
                }
            )

    _write_csv(
        run_rows,
        [
            "sweep_type",
            "noise_rate",
            "rounds",
            "distance",
            "shots",
            "results_base",
            "elapsed_generate_s",
            "elapsed_replay_s",
            "elapsed_analysis_s",
            "elapsed_total_s",
            "status",
            "n_rows",
            "n_datasets",
            "n_decoders",
            "mean_avg_flip_count",
            "mean_warning_rate",
        ],
        Path(args.out_run_csv),
    )

    noise_round_rows = [r for r in decoder_rows if str(r.get("sweep_type", "")) == "noise_rounds"]
    distance_rows = [r for r in decoder_rows if str(r.get("sweep_type", "")) == "distance"]
    _write_csv(
        noise_round_rows,
        [
            "sweep_type",
            "noise_rate",
            "rounds",
            "distance",
            "shots",
            "status",
            "decoder",
            "mean_avg_flip_count",
            "mean_warning_rate",
            "n_rows",
        ],
        Path(args.out_noise_rounds_csv),
    )
    _write_csv(
        distance_rows,
        [
            "sweep_type",
            "noise_rate",
            "rounds",
            "distance",
            "shots",
            "status",
            "decoder",
            "mean_avg_flip_count",
            "mean_warning_rate",
            "n_rows",
        ],
        Path(args.out_distance_csv),
    )

    _plot_noise_rounds(noise_round_rows, Path(args.out_prefix_noise_rounds))
    _plot_distance(distance_rows, Path(args.out_prefix_distance))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
