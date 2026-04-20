#!/usr/bin/env python3
"""Build journal-facing diagnostic figures from paper_04 replay outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-csv", required=True, help="Replay matrix CSV from step 03.")
    parser.add_argument(
        "--delta-csv",
        required=True,
        help="Bootstrap delta CSV from step 04 (table_bootstrap_source_vs_reference.csv).",
    )
    parser.add_argument("--replay-dir", required=True, help="Replay directory with decoder_responses_*.ndjson.")
    parser.add_argument("--out-dir", required=True, help="Output directory for tables/figures.")
    parser.add_argument(
        "--scaling-csv",
        default="",
        help="Optional scaling summary CSV (table_scaling_sweep.csv) for runtime log-log fit.",
    )
    parser.add_argument("--rank-bootstrap", type=int, default=4000, help="Bootstrap samples for rank stability.")
    parser.add_argument("--seed", type=int, default=20260410, help="RNG seed.")
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
                if key.startswith("mean_") or key.endswith("_rate") or key.endswith("_low") or key.endswith("_high") or key.endswith("_prob") or key in {
                    "delta_mean_source_minus_reference",
                    "delta_ci95_low",
                    "delta_ci95_high",
                    "delta_p_gt_zero",
                    "slope",
                    "intercept",
                    "r2",
                }:
                    if key in out:
                        out[key] = _fmt(out.get(key))
            writer.writerow(out)


def _write_md(rows: list[dict[str, Any]], headers: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals: list[str] = []
            for h in headers:
                v = row.get(h, "")
                if h in {"decoder", "source_dataset", "dataset_a", "dataset_b", "metric", "series", "status"}:
                    vals.append(str(v))
                else:
                    vals.append(_fmt(v) if isinstance(v, (float, int)) or (isinstance(v, str) and v and v != "nan") else str(v))
            f.write("| " + " | ".join(vals) + " |\n")


def _plot_delta_forest(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping delta forest plot ({exc}).")
        return

    if not rows:
        return

    labels = [f"{r['decoder']} | {r['source_dataset']}" for r in rows]
    y = np.arange(len(rows), dtype=float)
    mean = np.asarray([_f(r["delta_mean_source_minus_reference"]) for r in rows], dtype=float)
    lo = np.asarray([_f(r["delta_ci95_low"]) for r in rows], dtype=float)
    hi = np.asarray([_f(r["delta_ci95_high"]) for r in rows], dtype=float)
    err = np.vstack((np.maximum(0.0, mean - lo), np.maximum(0.0, hi - mean)))

    sources = sorted({str(r["source_dataset"]) for r in rows})
    palette = {
        "pennylane": "#1f77b4",
        "qiskit": "#2ca02c",
        "cirq": "#9467bd",
    }
    colors = [palette.get(str(r["source_dataset"]), "#555555") for r in rows]

    fig, ax = plt.subplots(figsize=(10.8, max(3.8, 0.45 * len(rows))), dpi=320, constrained_layout=True)
    ax.errorbar(mean, y, xerr=err, fmt="none", ecolor="#333333", elinewidth=1.0, capsize=2.4)
    ax.scatter(mean, y, s=34, c=colors, zorder=3)
    ax.axvline(0.0, color="black", linewidth=1.0, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Δ average flip count (source - reference)")
    ax.set_title("Source-vs-Reference Effect Sizes (95% Bootstrap CI)")
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()

    handles = []
    for s in sources:
        handles.append(plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=palette.get(s, "#555555"), label=s, markersize=6))
    if handles:
        ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=8)

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _rank_stability(
    matrix_rows: list[dict[str, str]], bootstrap: int, seed: int
) -> tuple[list[dict[str, Any]], list[str], list[int], np.ndarray]:
    ok_rows = [r for r in matrix_rows if (r.get("status") or "").strip() == "ok"]
    decoders = sorted({(r.get("decoder") or "").strip() for r in ok_rows if (r.get("decoder") or "").strip()})
    datasets = sorted({(r.get("dataset") or "").strip() for r in ok_rows if (r.get("dataset") or "").strip()})
    n_dec = len(decoders)
    if n_dec == 0 or len(datasets) == 0:
        return [], [], [], np.zeros((0, 0), dtype=float)

    metric_map: dict[tuple[str, str], float] = {}
    for row in ok_rows:
        dset = (row.get("dataset") or "").strip()
        dec = (row.get("decoder") or "").strip()
        if not dset or not dec:
            continue
        metric_map[(dset, dec)] = _f(row.get("avg_flip_count"))

    rng = np.random.default_rng(seed)
    counts = np.zeros((n_dec, n_dec), dtype=float)
    ds_idx = np.arange(len(datasets), dtype=int)

    for _ in range(max(1, bootstrap)):
        sample = rng.choice(ds_idx, size=len(ds_idx), replace=True)
        means = []
        for dec in decoders:
            vals = []
            for s_idx in sample:
                ds = datasets[int(s_idx)]
                v = metric_map.get((ds, dec), float("nan"))
                if not np.isnan(v):
                    vals.append(v)
            means.append(float(np.mean(vals)) if vals else float("inf"))

        order = sorted(range(n_dec), key=lambda i: (means[i], decoders[i]))
        for rank_zero, dec_idx in enumerate(order):
            counts[dec_idx, rank_zero] += 1.0

    probs = counts / float(max(1, bootstrap))
    rows: list[dict[str, Any]] = []
    for i, dec in enumerate(decoders):
        for r in range(n_dec):
            rows.append(
                {
                    "decoder": dec,
                    "rank": r + 1,
                    "rank_prob": float(probs[i, r]),
                    "bootstrap_samples": int(max(1, bootstrap)),
                }
            )
    return rows, decoders, list(range(1, n_dec + 1)), probs


def _plot_rank_stability(decoders: list[str], ranks: list[int], probs: np.ndarray, out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping rank stability plot ({exc}).")
        return

    if probs.size == 0:
        return

    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=320, constrained_layout=True)
    im = ax.imshow(probs, aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=max(0.45, float(np.max(probs))))
    ax.set_yticks(np.arange(len(decoders)))
    ax.set_yticklabels(decoders)
    ax.set_xticks(np.arange(len(ranks)))
    ax.set_xticklabels([str(r) for r in ranks])
    ax.set_xlabel("Rank (1 = lowest avg flip count)")
    ax.set_title("Decoder Rank Stability (Bootstrap)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Probability")

    for i in range(probs.shape[0]):
        for j in range(probs.shape[1]):
            ax.text(j, i, f"{probs[i, j]:.2f}", ha="center", va="center", fontsize=8, color="black")

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _load_flip_sets(path: Path) -> list[frozenset[int]]:
    if not path.exists():
        return []
    out: list[frozenset[int]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            correction = obj.get("correction", {})
            if not isinstance(correction, dict):
                correction = {}
            flips = correction.get("qubit_flips", [])
            if not isinstance(flips, list):
                flips = []
            vals: list[int] = []
            for q in flips:
                try:
                    vals.append(int(q))
                except (TypeError, ValueError):
                    continue
            out.append(frozenset(vals))
    return out


def _pair_agreement(a: list[frozenset[int]], b: list[frozenset[int]]) -> tuple[int, float, float]:
    n = min(len(a), len(b))
    if n <= 0:
        return 0, float("nan"), float("nan")
    jaccard_sum = 0.0
    exact_sum = 0.0
    for i in range(n):
        sa = a[i]
        sb = b[i]
        inter = len(sa & sb)
        union = len(sa | sb)
        j = 1.0 if union == 0 else (float(inter) / float(union))
        exact = 1.0 if sa == sb else 0.0
        jaccard_sum += j
        exact_sum += exact
    return n, jaccard_sum / float(n), exact_sum / float(n)


def _correction_agreement(
    matrix_rows: list[dict[str, str]], replay_dir: Path
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[str, np.ndarray]]:
    ok_rows = [r for r in matrix_rows if (r.get("status") or "").strip() == "ok"]
    decoders = sorted({(r.get("decoder") or "").strip() for r in ok_rows if (r.get("decoder") or "").strip()})
    datasets = sorted({(r.get("dataset") or "").strip() for r in ok_rows if (r.get("dataset") or "").strip()})
    if "lidmas_reference" in datasets:
        datasets = ["lidmas_reference"] + [d for d in datasets if d != "lidmas_reference"]

    response_lookup: dict[tuple[str, str], Path] = {}
    for row in ok_rows:
        ds = (row.get("dataset") or "").strip()
        dec = (row.get("decoder") or "").strip()
        response_file = (row.get("response_file") or "").strip()
        if not ds or not dec:
            continue
        if response_file:
            response_lookup[(ds, dec)] = replay_dir / response_file
        else:
            response_lookup[(ds, dec)] = replay_dir / f"decoder_responses_{ds}_{dec}.ndjson"

    series_cache: dict[tuple[str, str], list[frozenset[int]]] = {}
    rows: list[dict[str, Any]] = []
    heatmaps: dict[str, np.ndarray] = {}

    for dec in decoders:
        matrix = np.full((len(datasets), len(datasets)), np.nan, dtype=float)
        for i, da in enumerate(datasets):
            for j, db in enumerate(datasets):
                if (da, dec) not in series_cache:
                    series_cache[(da, dec)] = _load_flip_sets(response_lookup.get((da, dec), Path("")))
                if (db, dec) not in series_cache:
                    series_cache[(db, dec)] = _load_flip_sets(response_lookup.get((db, dec), Path("")))
                n, mean_j, exact = _pair_agreement(series_cache[(da, dec)], series_cache[(db, dec)])
                if not np.isnan(mean_j):
                    matrix[i, j] = mean_j
                rows.append(
                    {
                        "decoder": dec,
                        "dataset_a": da,
                        "dataset_b": db,
                        "n_compared": n,
                        "mean_jaccard": mean_j,
                        "exact_match_rate": exact,
                    }
                )
        heatmaps[dec] = matrix

    return rows, decoders, datasets, heatmaps


def _plot_correction_agreement(
    decoders: list[str], datasets: list[str], heatmaps: dict[str, np.ndarray], out_prefix: Path
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping correction-agreement plot ({exc}).")
        return

    if not decoders or not datasets:
        return

    cols = min(3, len(decoders))
    rows = int(math.ceil(len(decoders) / float(cols)))
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.8 * rows), dpi=320, constrained_layout=True)
    axes_arr = np.atleast_1d(axes).reshape(rows, cols)
    vmax = 1.0

    for idx, dec in enumerate(decoders):
        r = idx // cols
        c = idx % cols
        ax = axes_arr[r, c]
        mat = heatmaps.get(dec)
        if mat is None or mat.size == 0:
            ax.axis("off")
            continue
        im = ax.imshow(mat, cmap="YlGnBu", vmin=0.0, vmax=vmax)
        ax.set_title(dec)
        ax.set_xticks(np.arange(len(datasets)))
        ax.set_xticklabels(datasets, rotation=25, ha="right", fontsize=8)
        ax.set_yticks(np.arange(len(datasets)))
        ax.set_yticklabels(datasets, fontsize=8)
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                if np.isnan(mat[i, j]):
                    continue
                ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7, color="black")

    for idx in range(len(decoders), rows * cols):
        r = idx // cols
        c = idx % cols
        axes_arr[r, c].axis("off")

    fig.suptitle("Correction-Set Agreement (Mean Jaccard)", y=1.02)
    cbar = fig.colorbar(im, ax=axes_arr, fraction=0.022, pad=0.02)
    cbar.set_label("Mean Jaccard")

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _runtime_fit_rows(
    scaling_csv: Path,
) -> tuple[list[dict[str, Any]], dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]]:
    if not scaling_csv.exists():
        return [], {}
    rows = _read_csv(scaling_csv)
    ok = [r for r in rows if (r.get("status") or "").strip() == "ok"]
    if len(ok) < 2:
        return [], {}

    x = np.asarray([_f(r.get("shot")) for r in ok], dtype=float)
    mask_x = np.isfinite(x) & (x > 0.0)
    if np.sum(mask_x) < 2:
        return [], {}
    x = x[mask_x]

    series_map = {
        "elapsed_total_s": "total runtime",
        "elapsed_generate_s": "generate runtime",
        "elapsed_replay_s": "replay runtime",
        "elapsed_analysis_s": "analysis runtime",
    }
    out_rows: list[dict[str, Any]] = []
    fit_points: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    logx = np.log10(x)
    x_grid = np.linspace(np.min(logx), np.max(logx), 128)

    for key, label in series_map.items():
        y_all = np.asarray([_f(r.get(key)) for r in ok], dtype=float)[mask_x]
        mask = np.isfinite(y_all) & (y_all > 0.0)
        if np.sum(mask) < 2:
            continue
        lx = logx[mask]
        ly = np.log10(y_all[mask])
        slope, intercept = np.polyfit(lx, ly, 1)
        pred = slope * lx + intercept
        ss_res = float(np.sum((ly - pred) ** 2))
        ss_tot = float(np.sum((ly - np.mean(ly)) ** 2))
        r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0.0 else float("nan")
        fit_y = slope * x_grid + intercept
        fit_points[label] = (10.0 ** lx, 10.0 ** ly, 10.0 ** x_grid, 10.0 ** fit_y)
        out_rows.append(
            {
                "series": label,
                "slope": float(slope),
                "intercept": float(intercept),
                "r2": r2,
                "n_points": int(np.sum(mask)),
            }
        )
    return out_rows, fit_points


def _plot_runtime_fit(
    fit_rows: list[dict[str, Any]],
    fit_points: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    out_prefix: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping runtime fit plot ({exc}).")
        return

    if not fit_rows:
        return

    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd"]
    fig, ax = plt.subplots(figsize=(7.4, 4.6), dpi=320, constrained_layout=True)

    for idx, row in enumerate(fit_rows):
        label = str(row["series"])
        if label not in fit_points:
            continue
        x_obs, y_obs, x_fit, y_fit = fit_points[label]
        c = colors[idx % len(colors)]
        ax.scatter(x_obs, y_obs, s=26, color=c, alpha=0.9)
        ax.plot(x_fit, y_fit, color=c, linewidth=1.4, label=f"{label} (slope={row['slope']:.2f})")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Shots")
    ax.set_ylabel("Seconds")
    ax.set_title("Runtime Scaling: Log-Log Fit")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix_rows = _read_csv(Path(args.matrix_csv))
    delta_rows_all = _read_csv(Path(args.delta_csv))
    delta_rows = [
        r
        for r in delta_rows_all
        if (r.get("metric") or "").strip() == "avg_flip_count" and (r.get("status") or "").strip() == "ok"
    ]
    delta_rows = sorted(delta_rows, key=lambda r: ((r.get("decoder") or "").strip(), (r.get("source_dataset") or "").strip()))

    delta_fields = [
        "decoder",
        "source_dataset",
        "reference_dataset",
        "metric",
        "status",
        "n_source",
        "n_reference",
        "delta_mean_source_minus_reference",
        "delta_ci95_low",
        "delta_ci95_high",
        "delta_p_gt_zero",
        "bootstrap_samples",
    ]
    _write_csv(delta_rows, delta_fields, out_dir / "table_delta_forest.csv")
    _write_md(
        delta_rows,
        [
            "decoder",
            "source_dataset",
            "delta_mean_source_minus_reference",
            "delta_ci95_low",
            "delta_ci95_high",
            "delta_p_gt_zero",
        ],
        out_dir / "table_delta_forest.md",
    )
    _plot_delta_forest(delta_rows, out_dir / "figure_delta_forest")

    rank_rows, decoders, ranks, probs = _rank_stability(matrix_rows, int(args.rank_bootstrap), int(args.seed))
    _write_csv(
        rank_rows,
        ["decoder", "rank", "rank_prob", "bootstrap_samples"],
        out_dir / "table_rank_stability.csv",
    )
    _write_md(rank_rows, ["decoder", "rank", "rank_prob", "bootstrap_samples"], out_dir / "table_rank_stability.md")
    _plot_rank_stability(decoders, ranks, probs, out_dir / "figure_rank_stability")

    agreement_rows, ag_decoders, datasets, heatmaps = _correction_agreement(matrix_rows, Path(args.replay_dir))
    _write_csv(
        agreement_rows,
        ["decoder", "dataset_a", "dataset_b", "n_compared", "mean_jaccard", "exact_match_rate"],
        out_dir / "table_correction_agreement.csv",
    )
    _write_md(
        agreement_rows,
        ["decoder", "dataset_a", "dataset_b", "n_compared", "mean_jaccard", "exact_match_rate"],
        out_dir / "table_correction_agreement.md",
    )
    _plot_correction_agreement(ag_decoders, datasets, heatmaps, out_dir / "figure_correction_agreement")

    runtime_rows: list[dict[str, Any]] = []
    runtime_fit_points: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    if args.scaling_csv:
        runtime_rows, runtime_fit_points = _runtime_fit_rows(Path(args.scaling_csv))
    if runtime_rows:
        _write_csv(runtime_rows, ["series", "slope", "intercept", "r2", "n_points"], out_dir / "table_runtime_scaling_fit.csv")
        _write_md(runtime_rows, ["series", "slope", "r2", "n_points"], out_dir / "table_runtime_scaling_fit.md")
        _plot_runtime_fit(runtime_rows, runtime_fit_points, out_dir / "figure_runtime_scaling_fit")

    summary = out_dir / "summary_journal_plots.md"
    with summary.open("w", encoding="utf-8") as f:
        f.write("# paper_04 Journal Plot Pack\n\n")
        f.write("- Delta forest: `figure_delta_forest.(png|pdf|svg)`\n")
        f.write("- Rank stability heatmap: `figure_rank_stability.(png|pdf|svg)`\n")
        f.write("- Correction agreement heatmap: `figure_correction_agreement.(png|pdf|svg)`\n")
        if runtime_rows:
            f.write("- Runtime log-log fit: `figure_runtime_scaling_fit.(png|pdf|svg)`\n")
        else:
            f.write("- Runtime log-log fit: skipped (missing/insufficient scaling data)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
