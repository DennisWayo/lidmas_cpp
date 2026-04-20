#!/usr/bin/env python3
"""Bootstrap confidence intervals for paper_04 decoder metrics and source deltas."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


METRICS: tuple[tuple[str, str], ...] = (
    ("avg_flip_count", "mean flips/request"),
    ("warning_no_syndrome_rate", "warning rate"),
    ("nonempty_flip_rate", "nonempty flip rate"),
)


@dataclass
class ResponseSeries:
    flip_counts: np.ndarray
    warning_flags: np.ndarray
    nonempty_flip_flags: np.ndarray
    parse_errors: int

    @property
    def n(self) -> int:
        return int(self.flip_counts.size)

    def metric_array(self, metric: str) -> np.ndarray:
        if metric == "avg_flip_count":
            return self.flip_counts
        if metric == "warning_no_syndrome_rate":
            return self.warning_flags
        if metric == "nonempty_flip_rate":
            return self.nonempty_flip_flags
        raise KeyError(f"unsupported metric: {metric}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-csv", required=True, help="Replay matrix CSV (from step 03).")
    parser.add_argument("--responses-dir", required=True, help="Directory containing decoder_responses_* files.")
    parser.add_argument("--reference-dataset", default="lidmas_reference", help="Reference dataset label.")
    parser.add_argument("--bootstrap", type=int, default=2000, help="Bootstrap samples.")
    parser.add_argument("--seed", type=int, default=20260409, help="RNG seed.")
    parser.add_argument("--out-metrics-csv", required=True, help="Per-dataset metric CI table CSV.")
    parser.add_argument("--out-metrics-md", required=True, help="Per-dataset metric CI table Markdown.")
    parser.add_argument("--out-delta-csv", required=True, help="Source-vs-reference delta CI table CSV.")
    parser.add_argument("--out-delta-md", required=True, help="Source-vs-reference delta CI table Markdown.")
    parser.add_argument("--out-prefix", required=True, help="Figure output prefix (without extension).")
    return parser.parse_args()


def _read_matrix_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_series(path: Path) -> ResponseSeries:
    if not path.exists():
        return ResponseSeries(
            flip_counts=np.zeros(0, dtype=float),
            warning_flags=np.zeros(0, dtype=float),
            nonempty_flip_flags=np.zeros(0, dtype=float),
            parse_errors=0,
        )

    flips: list[float] = []
    warnings: list[float] = []
    nonempty: list[float] = []
    parse_errors = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            correction = obj.get("correction", {})
            if not isinstance(correction, dict):
                correction = {}
            flip_list = correction.get("qubit_flips", [])
            if not isinstance(flip_list, list):
                flip_list = []

            diagnostics = obj.get("diagnostics", {})
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            warning = 1.0 if diagnostics.get("warning") == "no_syndrome_bits" else 0.0

            flip_count = float(len(flip_list))
            flips.append(flip_count)
            nonempty.append(1.0 if flip_count > 0.0 else 0.0)
            warnings.append(warning)

    return ResponseSeries(
        flip_counts=np.asarray(flips, dtype=float),
        warning_flags=np.asarray(warnings, dtype=float),
        nonempty_flip_flags=np.asarray(nonempty, dtype=float),
        parse_errors=parse_errors,
    )


def _bootstrap_mean(values: np.ndarray, bootstrap: int, rng: np.random.Generator) -> tuple[float, float, float, float]:
    n = int(values.size)
    if n <= 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    empirical = float(np.mean(values))
    if bootstrap <= 1:
        return (empirical, empirical, empirical, float("nan"))

    idx = rng.integers(0, n, size=(bootstrap, n), dtype=np.int64)
    sampled = values[idx]
    means = np.mean(sampled, axis=1)
    lo = float(np.percentile(means, 2.5))
    hi = float(np.percentile(means, 97.5))
    p_gt_zero = float(np.mean(means > 0.0))
    return (empirical, lo, hi, p_gt_zero)


def _bootstrap_delta(
    source_values: np.ndarray, reference_values: np.ndarray, bootstrap: int, rng: np.random.Generator
) -> tuple[float, float, float, float]:
    ns = int(source_values.size)
    nr = int(reference_values.size)
    if ns <= 0 or nr <= 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    empirical = float(np.mean(source_values) - np.mean(reference_values))
    if bootstrap <= 1:
        return (empirical, empirical, empirical, float("nan"))

    src_idx = rng.integers(0, ns, size=(bootstrap, ns), dtype=np.int64)
    ref_idx = rng.integers(0, nr, size=(bootstrap, nr), dtype=np.int64)
    src_mean = np.mean(source_values[src_idx], axis=1)
    ref_mean = np.mean(reference_values[ref_idx], axis=1)
    deltas = src_mean - ref_mean
    lo = float(np.percentile(deltas, 2.5))
    hi = float(np.percentile(deltas, 97.5))
    p_gt_zero = float(np.mean(deltas > 0.0))
    return (empirical, lo, hi, p_gt_zero)


def _fmt(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "nan"
    if np.isnan(v):
        return "nan"
    return f"{v:.6f}"


def _write_csv(rows: list[dict[str, Any]], fieldnames: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fieldnames:
                if key in {
                    "mean",
                    "ci95_low",
                    "ci95_high",
                    "p_gt_zero",
                    "delta_mean_source_minus_reference",
                    "delta_ci95_low",
                    "delta_ci95_high",
                    "delta_p_gt_zero",
                }:
                    out[key] = _fmt(out.get(key))
            writer.writerow(out)


def _write_md_metrics(rows: list[dict[str, Any]], path: Path) -> None:
    headers = [
        "dataset",
        "decoder",
        "metric",
        "status",
        "mean",
        "ci95_low",
        "ci95_high",
        "n",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals = [
                str(row.get("dataset", "")),
                str(row.get("decoder", "")),
                str(row.get("metric", "")),
                str(row.get("status", "")),
                _fmt(row.get("mean")),
                _fmt(row.get("ci95_low")),
                _fmt(row.get("ci95_high")),
                str(row.get("n", "")),
            ]
            f.write("| " + " | ".join(vals) + " |\n")


def _write_md_deltas(rows: list[dict[str, Any]], path: Path) -> None:
    headers = [
        "decoder",
        "source_dataset",
        "reference_dataset",
        "metric",
        "status",
        "delta_mean_source_minus_reference",
        "delta_ci95_low",
        "delta_ci95_high",
        "delta_p_gt_zero",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals = [
                str(row.get("decoder", "")),
                str(row.get("source_dataset", "")),
                str(row.get("reference_dataset", "")),
                str(row.get("metric", "")),
                str(row.get("status", "")),
                _fmt(row.get("delta_mean_source_minus_reference")),
                _fmt(row.get("delta_ci95_low")),
                _fmt(row.get("delta_ci95_high")),
                _fmt(row.get("delta_p_gt_zero")),
            ]
            f.write("| " + " | ".join(vals) + " |\n")


def _plot(
    metrics_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
    decoders: list[str],
    datasets: list[str],
    reference_dataset: str,
    out_prefix: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping bootstrap figure export ({exc}).")
        return

    if not decoders or not datasets:
        return

    metric_key = "avg_flip_count"
    palette = {
        "lidmas_reference": "#ff7f0e",
        "pennylane": "#1f77b4",
        "qiskit": "#2ca02c",
        "cirq": "#9467bd",
    }

    metric_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in metrics_rows:
        metric_index[(str(row["dataset"]), str(row["decoder"]), str(row["metric"]))] = row

    delta_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in delta_rows:
        delta_index[(str(row["source_dataset"]), str(row["decoder"]), str(row["metric"]))] = row

    sources = [d for d in datasets if d != reference_dataset]
    base_x = np.arange(len(decoders), dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), dpi=320, constrained_layout=True)

    width = min(0.76 / max(len(datasets), 1), 0.22)
    for idx, dataset in enumerate(datasets):
        offset = (idx - (len(datasets) - 1) / 2.0) * width
        means: list[float] = []
        err_lo: list[float] = []
        err_hi: list[float] = []
        for decoder in decoders:
            row = metric_index.get((dataset, decoder, metric_key))
            if row is None:
                means.append(np.nan)
                err_lo.append(np.nan)
                err_hi.append(np.nan)
                continue
            mean = float(row.get("mean", np.nan))
            lo = float(row.get("ci95_low", np.nan))
            hi = float(row.get("ci95_high", np.nan))
            means.append(mean)
            err_lo.append(max(0.0, mean - lo) if np.isfinite(mean) and np.isfinite(lo) else np.nan)
            err_hi.append(max(0.0, hi - mean) if np.isfinite(mean) and np.isfinite(hi) else np.nan)

        label = "LiDMaS+ reference" if dataset == reference_dataset else dataset
        axes[0].errorbar(
            base_x + offset,
            np.asarray(means, dtype=float),
            yerr=np.asarray([err_lo, err_hi], dtype=float),
            fmt="o",
            markersize=4.5,
            linewidth=1.0,
            capsize=2.2,
            color=palette.get(dataset, None),
            label=label,
        )

    axes[0].set_title("Decoder Means with 95% Bootstrap CI")
    axes[0].set_xlabel("Decoder")
    axes[0].set_ylabel("Average flip count")
    axes[0].set_xticks(base_x)
    axes[0].set_xticklabels(decoders)
    axes[0].grid(axis="y", alpha=0.25)

    if sources:
        width_delta = min(0.72 / max(len(sources), 1), 0.26)
        for idx, source in enumerate(sources):
            offset = (idx - (len(sources) - 1) / 2.0) * width_delta
            means: list[float] = []
            err_lo: list[float] = []
            err_hi: list[float] = []
            for decoder in decoders:
                row = delta_index.get((source, decoder, metric_key))
                if row is None:
                    means.append(np.nan)
                    err_lo.append(np.nan)
                    err_hi.append(np.nan)
                    continue
                mean = float(row.get("delta_mean_source_minus_reference", np.nan))
                lo = float(row.get("delta_ci95_low", np.nan))
                hi = float(row.get("delta_ci95_high", np.nan))
                means.append(mean)
                err_lo.append(max(0.0, mean - lo) if np.isfinite(mean) and np.isfinite(lo) else np.nan)
                err_hi.append(max(0.0, hi - mean) if np.isfinite(mean) and np.isfinite(hi) else np.nan)

            axes[1].errorbar(
                base_x + offset,
                np.asarray(means, dtype=float),
                yerr=np.asarray([err_lo, err_hi], dtype=float),
                fmt="s",
                markersize=4.2,
                linewidth=1.0,
                capsize=2.2,
                color=palette.get(source, None),
                label=source,
            )

    axes[1].axhline(0.0, color="black", linewidth=0.9, alpha=0.75)
    axes[1].set_title("Source - Reference Delta (95% CI)")
    axes[1].set_xlabel("Decoder")
    axes[1].set_ylabel("Δ average flip count")
    axes[1].set_xticks(base_x)
    axes[1].set_xticklabels(decoders)
    axes[1].grid(axis="y", alpha=0.25)

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(4, len(labels)), frameon=False, bbox_to_anchor=(0.5, 1.03))

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    matrix_rows = _read_matrix_rows(Path(args.matrix_csv))
    responses_dir = Path(args.responses_dir)

    decoders = sorted({(r.get("decoder") or "").strip() for r in matrix_rows if (r.get("decoder") or "").strip()})
    datasets = sorted({(r.get("dataset") or "").strip() for r in matrix_rows if (r.get("dataset") or "").strip()})
    if args.reference_dataset in datasets:
        datasets = [args.reference_dataset] + [d for d in datasets if d != args.reference_dataset]

    combo_rows = [r for r in matrix_rows if (r.get("dataset") or "").strip() and (r.get("decoder") or "").strip()]
    combo_index: dict[tuple[str, str], dict[str, str]] = {}
    for row in combo_rows:
        combo_index[((row.get("dataset") or "").strip(), (row.get("decoder") or "").strip())] = row

    series: dict[tuple[str, str], ResponseSeries] = {}
    for dataset in datasets:
        for decoder in decoders:
            row = combo_index.get((dataset, decoder), {})
            response_file = str(row.get("response_file", "")).strip()
            path = responses_dir / response_file if response_file else Path("")
            if not response_file:
                path = responses_dir / f"decoder_responses_{dataset}_{decoder}.ndjson"
            series[(dataset, decoder)] = _load_series(path)

    rng = np.random.default_rng(int(args.seed))

    metrics_rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for decoder in decoders:
            s = series[(dataset, decoder)]
            status = "ok" if s.n > 0 else "missing_or_empty"
            for metric, _metric_label in METRICS:
                mean, lo, hi, p_gt_zero = _bootstrap_mean(s.metric_array(metric), int(args.bootstrap), rng)
                metrics_rows.append(
                    {
                        "dataset": dataset,
                        "decoder": decoder,
                        "metric": metric,
                        "status": status,
                        "n": s.n,
                        "parse_errors": s.parse_errors,
                        "mean": mean,
                        "ci95_low": lo,
                        "ci95_high": hi,
                        "p_gt_zero": p_gt_zero,
                        "bootstrap_samples": int(args.bootstrap),
                    }
                )

    delta_rows: list[dict[str, Any]] = []
    sources = [d for d in datasets if d != args.reference_dataset]
    for decoder in decoders:
        ref = series.get((args.reference_dataset, decoder))
        for source in sources:
            src = series.get((source, decoder))
            status = "ok"
            if ref is None or ref.n <= 0:
                status = "missing_reference"
            elif src is None or src.n <= 0:
                status = "missing_source"

            for metric, _metric_label in METRICS:
                if status != "ok":
                    mean = lo = hi = p_gt_zero = float("nan")
                else:
                    mean, lo, hi, p_gt_zero = _bootstrap_delta(
                        src.metric_array(metric), ref.metric_array(metric), int(args.bootstrap), rng
                    )
                delta_rows.append(
                    {
                        "decoder": decoder,
                        "source_dataset": source,
                        "reference_dataset": args.reference_dataset,
                        "metric": metric,
                        "status": status,
                        "n_source": src.n if src is not None else 0,
                        "n_reference": ref.n if ref is not None else 0,
                        "delta_mean_source_minus_reference": mean,
                        "delta_ci95_low": lo,
                        "delta_ci95_high": hi,
                        "delta_p_gt_zero": p_gt_zero,
                        "bootstrap_samples": int(args.bootstrap),
                    }
                )

    metric_fields = [
        "dataset",
        "decoder",
        "metric",
        "status",
        "n",
        "parse_errors",
        "mean",
        "ci95_low",
        "ci95_high",
        "p_gt_zero",
        "bootstrap_samples",
    ]
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

    _write_csv(metrics_rows, metric_fields, Path(args.out_metrics_csv))
    _write_md_metrics(metrics_rows, Path(args.out_metrics_md))
    _write_csv(delta_rows, delta_fields, Path(args.out_delta_csv))
    _write_md_deltas(delta_rows, Path(args.out_delta_md))
    _plot(
        metrics_rows=metrics_rows,
        delta_rows=delta_rows,
        decoders=decoders,
        datasets=datasets,
        reference_dataset=args.reference_dataset,
        out_prefix=Path(args.out_prefix),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
