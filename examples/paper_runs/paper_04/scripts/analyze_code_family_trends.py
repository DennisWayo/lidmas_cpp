#!/usr/bin/env python3
"""Analyze paper_04 code-family runs with within-family and normalized cross-family trends."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Family run manifest CSV.")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
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


def _write_csv(rows: list[dict[str, Any]], fields: list[str], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fields:
                if (
                    key.startswith("mean_")
                    or key.startswith("delta_")
                    or key.startswith("norm_")
                    or key.startswith("avg_")
                    or key.endswith("_rate")
                    or key.endswith("_low")
                    or key.endswith("_high")
                    or key.endswith("_ratio")
                ):
                    if key in out:
                        out[key] = _fmt(out[key])
            writer.writerow(out)


def _plot_family_tradeoff(summary_rows: list[dict[str, Any]], families: list[str], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping family tradeoff plot ({exc}).")
        return

    if not summary_rows:
        return

    cols = len(families)
    fig, axes = plt.subplots(1, cols, figsize=(5.0 * max(1, cols), 4.4), dpi=320, constrained_layout=True)
    axes_arr = np.atleast_1d(axes)
    palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf"]

    for i, fam in enumerate(families):
        ax = axes_arr[i]
        fam_rows = [r for r in summary_rows if str(r.get("family", "")) == fam]
        fam_rows = sorted(fam_rows, key=lambda r: str(r.get("decoder", "")))
        decoders = [str(r.get("decoder", "")) for r in fam_rows]
        x = np.asarray([_f(r.get("mean_avg_flip_sources")) for r in fam_rows], dtype=float)
        y = np.asarray([_f(r.get("mean_warning_rate_sources")) for r in fam_rows], dtype=float)

        for j, dec in enumerate(decoders):
            ax.scatter(x[j], y[j], s=56, color=palette[j % len(palette)], label=dec)
            ax.text(x[j], y[j], dec, fontsize=8, ha="left", va="bottom")

        ax.set_title(f"{fam}: Decoder Tradeoff")
        ax.set_xlabel("Mean flip count (sources)")
        ax.set_ylabel("Warning rate (sources)")
        ax.grid(alpha=0.25)

    handles, labels = axes_arr[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(6, len(labels)), frameon=False, bbox_to_anchor=(0.5, 1.05))

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _plot_family_delta_forest(delta_rows: list[dict[str, Any]], families: list[str], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping family delta forest ({exc}).")
        return

    if not delta_rows:
        return

    cols = len(families)
    fig, axes = plt.subplots(1, cols, figsize=(5.6 * max(1, cols), 4.8), dpi=320, constrained_layout=True)
    axes_arr = np.atleast_1d(axes)
    src_palette = {"pennylane": "#1f77b4", "qiskit": "#2ca02c", "cirq": "#9467bd"}

    for i, fam in enumerate(families):
        ax = axes_arr[i]
        rows = [r for r in delta_rows if str(r.get("family", "")) == fam]
        rows = sorted(rows, key=lambda r: (str(r.get("decoder", "")), str(r.get("source_dataset", ""))))
        if not rows:
            ax.set_axis_off()
            continue

        y = np.arange(len(rows), dtype=float)
        mean = np.asarray([_f(r.get("delta_mean_source_minus_reference")) for r in rows], dtype=float)
        lo = np.asarray([_f(r.get("delta_ci95_low")) for r in rows], dtype=float)
        hi = np.asarray([_f(r.get("delta_ci95_high")) for r in rows], dtype=float)
        err = np.vstack((np.maximum(0.0, mean - lo), np.maximum(0.0, hi - mean)))
        colors = [src_palette.get(str(r.get("source_dataset", "")), "#555555") for r in rows]
        labels = [f"{r['decoder']}|{r['source_dataset']}" for r in rows]

        ax.errorbar(mean, y, xerr=err, fmt="none", ecolor="#333333", elinewidth=1.0, capsize=2.2)
        ax.scatter(mean, y, c=colors, s=30, zorder=3)
        ax.axvline(0.0, color="black", linewidth=1.0, alpha=0.8)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xlabel("Δ flip count (source - ref)")
        ax.set_title(f"{fam}: Source Effect Sizes")
        ax.grid(axis="x", alpha=0.25)
        ax.invert_yaxis()

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _plot_normalized_trends(
    norm_rows: list[dict[str, Any]],
    families: list[str],
    decoders: list[str],
    out_prefix: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping normalized trends plot ({exc}).")
        return

    if not norm_rows or not families:
        return

    metrics = [
        ("norm_flip", "Normalized flip count"),
        ("norm_warning", "Normalized warning rate"),
        ("norm_stack_delta", "Normalized source-delta magnitude"),
    ]
    palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf"]
    fam_to_x = {fam: idx for idx, fam in enumerate(families)}

    fig, axes = plt.subplots(1, len(metrics), figsize=(5.0 * len(metrics), 4.3), dpi=320, constrained_layout=True)
    axes_arr = np.atleast_1d(axes)

    for m_idx, (metric_key, metric_title) in enumerate(metrics):
        ax = axes_arr[m_idx]
        for d_idx, decoder in enumerate(decoders):
            rows = [r for r in norm_rows if str(r.get("decoder", "")) == decoder and np.isfinite(_f(r.get(metric_key)))]
            if not rows:
                continue
            xs = np.asarray([fam_to_x[str(r.get("family", ""))] for r in rows], dtype=float)
            ys = np.asarray([_f(r.get(metric_key)) for r in rows], dtype=float)
            order = np.argsort(xs)
            xs = xs[order]
            ys = ys[order]
            ax.plot(xs, ys, marker="o", linewidth=1.3, color=palette[d_idx % len(palette)], label=decoder)
        ax.set_title(metric_title)
        ax.set_xticks(np.arange(len(families)))
        ax.set_xticklabels(families)
        ax.set_ylim(-0.03, 1.03)
        ax.grid(alpha=0.25)

    handles, labels = axes_arr[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(6, len(labels)), frameon=False, bbox_to_anchor=(0.5, 1.08))

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = _read_csv(Path(args.manifest))
    family_order_raw = [str(r.get("family", "")).strip() for r in manifest if str(r.get("family", "")).strip()]
    family_order: list[str] = []
    for fam in family_order_raw:
        if fam not in family_order:
            family_order.append(fam)

    summary_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    combined_matrix_rows: list[dict[str, Any]] = []
    combined_source_rows: list[dict[str, Any]] = []

    for row in manifest:
        family = str(row.get("family", "")).strip()
        if not family:
            continue
        matrix_csv = Path(str(row.get("matrix_csv", "")).strip())
        delta_csv = Path(str(row.get("delta_csv", "")).strip())
        if not matrix_csv.exists():
            continue
        matrix_rows = _read_csv(matrix_csv)
        for mrow in matrix_rows:
            combined_matrix_rows.append({"family": family, **mrow})
        ok_rows = [r for r in matrix_rows if (r.get("status") or "").strip() == "ok"]
        decoders = sorted({(r.get("decoder") or "").strip() for r in ok_rows if (r.get("decoder") or "").strip()})
        datasets = sorted({(r.get("dataset") or "").strip() for r in ok_rows if (r.get("dataset") or "").strip()})
        sources = [d for d in datasets if d and d != "lidmas_reference"]
        idx: dict[tuple[str, str], dict[str, str]] = {}
        for r in ok_rows:
            ds = (r.get("dataset") or "").strip()
            dec = (r.get("decoder") or "").strip()
            if ds and dec:
                idx[(dec, ds)] = r

        for dec in decoders:
            dec_rows = [r for r in ok_rows if (r.get("decoder") or "").strip() == dec]
            src_rows = [r for r in dec_rows if (r.get("dataset") or "").strip() != "lidmas_reference"]
            ref_rows = [r for r in dec_rows if (r.get("dataset") or "").strip() == "lidmas_reference"]
            mean_flip_sources = float(np.mean([_f(r.get("avg_flip_count")) for r in src_rows])) if src_rows else float("nan")
            mean_warning_sources = (
                float(np.mean([_f(r.get("warning_no_syndrome_rate")) for r in src_rows])) if src_rows else float("nan")
            )
            mean_nonempty_sources = (
                float(np.mean([_f(r.get("nonempty_flip_rate")) for r in src_rows])) if src_rows else float("nan")
            )
            mean_flip_reference = float(np.mean([_f(r.get("avg_flip_count")) for r in ref_rows])) if ref_rows else float("nan")
            summary_rows.append(
                {
                    "family": family,
                    "decoder": dec,
                    "n_rows_sources": len(src_rows),
                    "n_rows_reference": len(ref_rows),
                    "mean_avg_flip_sources": mean_flip_sources,
                    "mean_avg_flip_reference": mean_flip_reference,
                    "mean_warning_rate_sources": mean_warning_sources,
                    "mean_nonempty_flip_rate_sources": mean_nonempty_sources,
                    "mean_abs_source_delta_flip": float("nan"),
                    "flip_rank_within_family": 0,
                }
            )

            ref_row = idx.get((dec, "lidmas_reference"))
            for source in sources:
                src_row = idx.get((dec, source))
                status = "ok"
                if src_row is None and ref_row is None:
                    status = "missing_source_and_reference"
                elif src_row is None:
                    status = f"missing_{source}"
                elif ref_row is None:
                    status = "missing_lidmas_reference"

                s_flip = _f((src_row or {}).get("avg_flip_count"))
                r_flip = _f((ref_row or {}).get("avg_flip_count"))
                s_warn = _f((src_row or {}).get("warning_no_syndrome_rate"))
                r_warn = _f((ref_row or {}).get("warning_no_syndrome_rate"))
                s_event = _f((src_row or {}).get("nonempty_request_event_rate"))
                r_event = _f((ref_row or {}).get("nonempty_request_event_rate"))
                combined_source_rows.append(
                    {
                        "family": family,
                        "decoder": dec,
                        "source_dataset": source,
                        "reference_dataset": "lidmas_reference",
                        "status": status,
                        "avg_flip_count_source": s_flip,
                        "avg_flip_count_reference": r_flip,
                        "delta_avg_flip_count_source_minus_reference": s_flip - r_flip,
                        "warning_rate_source": s_warn,
                        "warning_rate_reference": r_warn,
                        "delta_warning_rate_source_minus_reference": s_warn - r_warn,
                        "nonempty_event_rate_source": s_event,
                        "nonempty_event_rate_reference": r_event,
                        "delta_nonempty_event_rate_source_minus_reference": s_event - r_event,
                    }
                )

        if delta_csv.exists():
            del_rows = _read_csv(delta_csv)
            del_rows = [
                r
                for r in del_rows
                if (r.get("metric") or "").strip() == "avg_flip_count" and (r.get("status") or "").strip() == "ok"
            ]
            for drow in del_rows:
                delta_rows.append(
                    {
                        "family": family,
                        "decoder": str(drow.get("decoder", "")).strip(),
                        "source_dataset": str(drow.get("source_dataset", "")).strip(),
                        "delta_mean_source_minus_reference": _f(drow.get("delta_mean_source_minus_reference")),
                        "delta_ci95_low": _f(drow.get("delta_ci95_low")),
                        "delta_ci95_high": _f(drow.get("delta_ci95_high")),
                        "delta_p_gt_zero": _f(drow.get("delta_p_gt_zero")),
                    }
                )

    # Fold delta magnitudes into summary and assign within-family ranks.
    delta_abs_map: dict[tuple[str, str], list[float]] = {}
    for drow in delta_rows:
        key = (str(drow["family"]), str(drow["decoder"]))
        delta_abs_map.setdefault(key, []).append(abs(_f(drow["delta_mean_source_minus_reference"])))

    for row in summary_rows:
        key = (str(row["family"]), str(row["decoder"]))
        vals = delta_abs_map.get(key, [])
        row["mean_abs_source_delta_flip"] = float(np.mean(vals)) if vals else float("nan")

    families = sorted({str(r["family"]) for r in summary_rows})
    for fam in families:
        fam_rows = [r for r in summary_rows if str(r["family"]) == fam]
        fam_rows = sorted(fam_rows, key=lambda r: (_f(r["mean_avg_flip_sources"]), str(r["decoder"])))
        for rank, r in enumerate(fam_rows, start=1):
            r["flip_rank_within_family"] = rank

    # Cross-family normalized trends (normalized within each family across decoders).
    norm_rows: list[dict[str, Any]] = []
    decoders_all = sorted({str(r["decoder"]) for r in summary_rows})
    metric_keys = [
        ("mean_avg_flip_sources", "norm_flip"),
        ("mean_warning_rate_sources", "norm_warning"),
        ("mean_abs_source_delta_flip", "norm_stack_delta"),
    ]

    for fam in families:
        fam_rows = [r for r in summary_rows if str(r["family"]) == fam]
        for metric_key, norm_key in metric_keys:
            vals = np.asarray([_f(r.get(metric_key)) for r in fam_rows], dtype=float)
            valid = vals[np.isfinite(vals)]
            if valid.size == 0:
                for r in fam_rows:
                    r[norm_key] = float("nan")
                continue
            lo = float(np.min(valid))
            hi = float(np.max(valid))
            denom = hi - lo
            for r in fam_rows:
                v = _f(r.get(metric_key))
                if not np.isfinite(v):
                    r[norm_key] = float("nan")
                elif denom <= 1e-12:
                    r[norm_key] = 0.5
                else:
                    r[norm_key] = (v - lo) / denom

    for r in summary_rows:
        norm_rows.append(
            {
                "family": r["family"],
                "decoder": r["decoder"],
                "norm_flip": r.get("norm_flip", float("nan")),
                "norm_warning": r.get("norm_warning", float("nan")),
                "norm_stack_delta": r.get("norm_stack_delta", float("nan")),
            }
        )

    _write_csv(
        combined_matrix_rows,
        [
            "family",
            "dataset",
            "decoder",
            "status",
            "request_lines",
            "request_parse_errors",
            "response_lines",
            "response_parse_errors",
            "response_ratio",
            "avg_request_events",
            "nonempty_request_event_rate",
            "warning_no_syndrome_count",
            "warning_no_syndrome_rate",
            "error_count",
            "avg_sx_count",
            "avg_sz_count",
            "avg_flip_count",
            "nonempty_flip_rate",
            "unique_flip_qubits",
            "decoder_name_mismatch_count",
            "request_file",
            "response_file",
        ],
        out_dir / "table_replay_matrix.csv",
    )
    _write_csv(
        combined_source_rows,
        [
            "family",
            "decoder",
            "source_dataset",
            "reference_dataset",
            "status",
            "avg_flip_count_source",
            "avg_flip_count_reference",
            "delta_avg_flip_count_source_minus_reference",
            "warning_rate_source",
            "warning_rate_reference",
            "delta_warning_rate_source_minus_reference",
            "nonempty_event_rate_source",
            "nonempty_event_rate_reference",
            "delta_nonempty_event_rate_source_minus_reference",
        ],
        out_dir / "table_source_vs_lidmas.csv",
    )
    _write_csv(
        summary_rows,
        [
            "family",
            "decoder",
            "n_rows_sources",
            "n_rows_reference",
            "mean_avg_flip_sources",
            "mean_avg_flip_reference",
            "mean_warning_rate_sources",
            "mean_nonempty_flip_rate_sources",
            "mean_abs_source_delta_flip",
            "flip_rank_within_family",
            "norm_flip",
            "norm_warning",
            "norm_stack_delta",
        ],
        out_dir / "table_family_decoder_summary.csv",
    )
    _write_csv(
        delta_rows,
        [
            "family",
            "decoder",
            "source_dataset",
            "delta_mean_source_minus_reference",
            "delta_ci95_low",
            "delta_ci95_high",
            "delta_p_gt_zero",
        ],
        out_dir / "table_family_delta_effects.csv",
    )
    _write_csv(
        norm_rows,
        ["family", "decoder", "norm_flip", "norm_warning", "norm_stack_delta"],
        out_dir / "table_cross_family_normalized.csv",
    )

    _plot_family_tradeoff(summary_rows, families, out_dir / "figure_family_tradeoff")
    _plot_family_tradeoff(summary_rows, families, out_dir / "figure_source_vs_lidmas")
    _plot_family_delta_forest(delta_rows, families, out_dir / "figure_family_delta_forest")
    _plot_normalized_trends(norm_rows, family_order if family_order else families, decoders_all, out_dir / "figure_cross_family_normalized_trends")

    summary_md = out_dir / "summary_code_family_comparison.md"
    with summary_md.open("w", encoding="utf-8") as f:
        f.write("# paper_04 Surface-vs-GKP Decoder Comparison\n\n")
        f.write("This analysis reports:\n\n")
        f.write("1. within-family decoder tradeoffs (surface and gkp separately),\n")
        f.write("2. source-vs-reference effect sizes within each family,\n")
        f.write("3. cross-family normalized trends (no raw threshold equivalence claims).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
