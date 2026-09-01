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
    parser.add_argument("--rank-bootstrap", type=int, default=4000, help="Bootstrap samples for rank-stability analysis.")
    parser.add_argument("--rank-seed", type=int, default=20260410, help="RNG seed for rank-stability bootstrap.")
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
                    or key.endswith("_share")
                    or key.endswith("_squares")
                    or key.endswith("_square")
                    or key.endswith("_prob")
                ):
                    if key in out:
                        out[key] = _fmt(out[key])
            writer.writerow(out)


def _plot_family_tradeoff(summary_rows: list[dict[str, Any]], families: list[str], out_prefix: Path) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.lines import Line2D  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping family tradeoff plot ({exc}).")
        return

    if not summary_rows:
        return

    cols = len(families)
    fig, axes = plt.subplots(1, cols, figsize=(5.6 * max(1, cols), 4.3), dpi=320, constrained_layout=False)
    axes_arr = np.atleast_1d(axes)
    palette = {"bp": "#1f77b4", "mwpm": "#2ca02c", "uf": "#d62728"}

    for i, fam in enumerate(families):
        ax = axes_arr[i]
        fam_rows = [r for r in summary_rows if str(r.get("family", "")) == fam]
        fam_rows = sorted(fam_rows, key=lambda r: _f(r.get("mean_avg_flip_sources")))
        decoders = [str(r.get("decoder", "")) for r in fam_rows]
        x = np.asarray([_f(r.get("mean_avg_flip_sources")) for r in fam_rows], dtype=float)
        y = np.asarray([_f(r.get("mean_nonempty_flip_rate_sources")) for r in fam_rows], dtype=float)
        delta = np.asarray([_f(r.get("mean_abs_source_delta_flip")) for r in fam_rows], dtype=float)
        finite_delta = delta[np.isfinite(delta)]
        if finite_delta.size:
            d_min = float(np.min(finite_delta))
            d_span = float(np.max(finite_delta) - d_min)
            sizes = 150.0 + 420.0 * ((delta - d_min) / d_span if d_span > 1e-12 else np.ones_like(delta) * 0.45)
        else:
            sizes = np.ones_like(x) * 260.0

        for j, dec in enumerate(decoders):
            color = palette.get(dec, "#6B7280")
            ax.scatter(x[j], y[j], s=sizes[j], color=color, edgecolors="white", linewidths=0.9, zorder=3)
            ax.annotate(
                dec.upper(),
                xy=(x[j], y[j]),
                xytext=(5, 8),
                textcoords="offset points",
                fontsize=8.2,
                fontweight="bold",
                ha="left",
                va="bottom",
                color="#111827",
            )

        if np.isfinite(x).any():
            x_lo = float(np.nanmin(x))
            x_hi = float(np.nanmax(x))
            pad = max(0.08 * (x_hi - x_lo), 0.08)
            ax.set_xlim(x_lo - pad, x_hi + pad)
        if np.isfinite(y).any():
            y_lo = float(np.nanmin(y))
            y_hi = float(np.nanmax(y))
            pad = max(0.16 * (y_hi - y_lo), 0.015)
            ax.set_ylim(max(0.0, y_lo - pad), min(1.04, y_hi + pad))

        panel = chr(ord("a") + i)
        ax.text(-0.12, 1.06, panel, transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")
        ax.set_title(f"{fam.upper()} decoder operating point", fontsize=11.5, pad=10)
        ax.set_xlabel("Mean flip count (sources)")
        ax.set_ylabel("Nonempty flip rate (sources)")
        ax.grid(alpha=0.25, linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    size_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#9CA3AF", markeredgecolor="white", markersize=7, label="lower source sensitivity"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#9CA3AF", markeredgecolor="white", markersize=12, label="higher source sensitivity"),
    ]
    fig.legend(
        handles=size_handles,
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
        fontsize=8.0,
    )
    fig.subplots_adjust(left=0.08, right=0.99, top=0.84, bottom=0.22, wspace=0.28)

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _plot_family_delta_forest(delta_rows: list[dict[str, Any]], families: list[str], out_prefix: Path) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
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


def _plot_source_vs_lidmas(
    source_rows: list[dict[str, Any]],
    families: list[str],
    out_prefix: Path,
) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.lines import Line2D  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping source-vs-lidmas plot ({exc}).")
        return

    if not source_rows:
        return

    clean_rows = []
    for row in source_rows:
        if str(row.get("status", "")).strip() != "ok":
            continue
        s = _f(row.get("avg_flip_count_source"))
        r = _f(row.get("avg_flip_count_reference"))
        if not (np.isfinite(s) and np.isfinite(r)):
            continue
        clean_rows.append(row)
    if not clean_rows:
        return

    decoders = sorted({str(r.get("decoder", "")) for r in clean_rows if str(r.get("decoder", ""))})
    sources = sorted({str(r.get("source_dataset", "")) for r in clean_rows if str(r.get("source_dataset", ""))})
    if not decoders or not sources:
        return

    src_colors = {
        "pennylane": "#1f77b4",
        "qiskit": "#2ca02c",
        "cirq": "#9467bd",
    }
    source_offsets = np.linspace(-0.22, 0.22, num=len(sources)) if len(sources) > 1 else np.asarray([0.0])

    cols = max(1, len(families))
    fig, axes = plt.subplots(1, cols, figsize=(6.2 * cols, 4.8), dpi=320, constrained_layout=True, sharey=True)
    axes_arr = np.atleast_1d(axes)

    for i, fam in enumerate(families):
        ax = axes_arr[i]
        fam_rows = [r for r in clean_rows if str(r.get("family", "")) == fam]
        if not fam_rows:
            ax.set_axis_off()
            continue

        x_centers = np.arange(len(decoders), dtype=float)
        for d_idx, dec in enumerate(decoders):
            d_rows = [r for r in fam_rows if str(r.get("decoder", "")) == dec]
            if not d_rows:
                continue

            ref_vals = [_f(r.get("avg_flip_count_reference")) for r in d_rows if np.isfinite(_f(r.get("avg_flip_count_reference")))]
            if ref_vals:
                ref = float(np.mean(ref_vals))
                ax.scatter(
                    x_centers[d_idx],
                    ref,
                    marker="D",
                    s=44,
                    color="#111827",
                    edgecolors="white",
                    linewidths=0.6,
                    zorder=4,
                )

            for s_idx, src in enumerate(sources):
                row = next((r for r in d_rows if str(r.get("source_dataset", "")) == src), None)
                if row is None:
                    continue
                y_src = _f(row.get("avg_flip_count_source"))
                y_ref = _f(row.get("avg_flip_count_reference"))
                if not (np.isfinite(y_src) and np.isfinite(y_ref)):
                    continue
                x_src = x_centers[d_idx] + float(source_offsets[s_idx])
                ax.plot([x_centers[d_idx], x_src], [y_ref, y_src], color="#9CA3AF", linewidth=0.9, alpha=0.7, zorder=1)
                ax.scatter(
                    x_src,
                    y_src,
                    marker="o",
                    s=42,
                    color=src_colors.get(src, "#6B7280"),
                    edgecolors="white",
                    linewidths=0.6,
                    zorder=3,
                )

        ax.set_xticks(x_centers)
        ax.set_xticklabels(decoders)
        ax.set_xlabel("Decoder")
        if i == 0:
            ax.set_ylabel("Average flip count")
        ax.set_title(f"{fam}: Source vs LiDMaS+ reference")
        ax.grid(axis="y", alpha=0.25)

    legend_items: list[Line2D] = [
        Line2D(
            [0],
            [0],
            marker="D",
            color="none",
            markerfacecolor="#111827",
            markeredgecolor="white",
            markeredgewidth=0.6,
            markersize=7,
            label="LiDMaS+ reference",
        )
    ]
    for src in sources:
        legend_items.append(
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=src_colors.get(src, "#6B7280"),
                markeredgecolor="white",
                markeredgewidth=0.6,
                markersize=7,
                label=src,
            )
        )
    fig.legend(handles=legend_items, loc="upper center", ncol=min(5, len(legend_items)), frameon=False, bbox_to_anchor=(0.5, 1.06))

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
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
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


def _rank_stability_by_family(
    matrix_rows: list[dict[str, Any]],
    families: list[str],
    decoders: list[str],
    *,
    bootstrap: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray], list[int]]:
    ok_rows = [r for r in matrix_rows if str(r.get("status", "")).strip() == "ok"]
    ranks = list(range(1, len(decoders) + 1))
    rng = np.random.default_rng(seed)
    out_rows: list[dict[str, Any]] = []
    heatmaps: dict[str, np.ndarray] = {}

    for fam in families:
        fam_rows = [r for r in ok_rows if str(r.get("family", "")) == fam]
        sources = sorted(
            {
                str(r.get("dataset", "")).strip()
                for r in fam_rows
                if str(r.get("dataset", "")).strip() and str(r.get("dataset", "")).strip() != "lidmas_reference"
            }
        )
        probs = np.zeros((len(decoders), len(decoders)), dtype=float)
        if not sources or not decoders:
            heatmaps[fam] = probs
            continue

        metric_map: dict[tuple[str, str], float] = {}
        for row in fam_rows:
            source = str(row.get("dataset", "")).strip()
            decoder = str(row.get("decoder", "")).strip()
            if source and decoder:
                metric_map[(source, decoder)] = _f(row.get("avg_flip_count"))

        counts = np.zeros_like(probs)
        source_idx = np.arange(len(sources), dtype=int)
        n_boot = max(1, int(bootstrap))
        for _ in range(n_boot):
            sample = rng.choice(source_idx, size=len(source_idx), replace=True)
            means: list[float] = []
            for decoder in decoders:
                vals = [
                    metric_map.get((sources[int(idx)], decoder), float("nan"))
                    for idx in sample
                ]
                finite = [v for v in vals if np.isfinite(v)]
                means.append(float(np.mean(finite)) if finite else float("inf"))
            order = sorted(range(len(decoders)), key=lambda idx: (means[idx], decoders[idx]))
            for rank_zero, decoder_idx in enumerate(order):
                counts[decoder_idx, rank_zero] += 1.0

        probs = counts / float(n_boot)
        heatmaps[fam] = probs
        for decoder_idx, decoder in enumerate(decoders):
            for rank_zero, rank in enumerate(ranks):
                out_rows.append(
                    {
                        "family": fam,
                        "decoder": decoder,
                        "rank": rank,
                        "rank_prob": float(probs[decoder_idx, rank_zero]),
                        "bootstrap_samples": n_boot,
                        "source_count": len(sources),
                    }
                )

    return out_rows, heatmaps, ranks


def _plot_rank_stability_by_family(
    heatmaps: dict[str, np.ndarray],
    families: list[str],
    decoders: list[str],
    ranks: list[int],
    out_prefix: Path,
) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping rank-stability plot ({exc}).")
        return

    if not heatmaps or not decoders or not ranks:
        return

    cols = max(1, len(families))
    fig, axes = plt.subplots(1, cols, figsize=(5.4 * cols, 3.6), dpi=320, constrained_layout=False)
    axes_arr = np.atleast_1d(axes)

    last_im = None
    for i, fam in enumerate(families):
        ax = axes_arr[i]
        probs = heatmaps.get(fam, np.zeros((len(decoders), len(ranks)), dtype=float))
        last_im = ax.imshow(probs, cmap="YlGnBu", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_title(f"{fam.upper()} rank stability", fontsize=11.5, pad=9)
        ax.set_xticks(np.arange(len(ranks)))
        ax.set_xticklabels([str(rank) for rank in ranks])
        ax.set_xlabel("Rank (1 = lowest flip count)")
        ax.set_yticks(np.arange(len(decoders)))
        ax.set_yticklabels([decoder.upper() for decoder in decoders])
        ax.text(-0.14, 1.08, chr(ord("a") + i), transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")

        for row in range(probs.shape[0]):
            for col in range(probs.shape[1]):
                value = float(probs[row, col])
                color = "white" if value > 0.62 else "#111827"
                ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=8.5, fontweight="bold", color=color)

    fig.subplots_adjust(left=0.08, right=0.86, top=0.82, bottom=0.20, wspace=0.40)
    if last_im is not None:
        cax = fig.add_axes([0.90, 0.23, 0.018, 0.58])
        cbar = fig.colorbar(last_im, cax=cax)
        cbar.set_label("Bootstrap probability")

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _balanced_tensor(
    matrix_rows: list[dict[str, Any]],
    metric: str,
) -> tuple[np.ndarray, list[str], list[str], list[str]] | None:
    ok_rows = [r for r in matrix_rows if str(r.get("status", "")).strip() == "ok"]
    families = sorted({str(r.get("family", "")).strip() for r in ok_rows if str(r.get("family", "")).strip()})
    decoders = sorted({str(r.get("decoder", "")).strip() for r in ok_rows if str(r.get("decoder", "")).strip()})
    sources = sorted({str(r.get("dataset", "")).strip() for r in ok_rows if str(r.get("dataset", "")).strip()})
    if not families or not decoders or not sources:
        return None

    idx = {
        (str(r.get("family", "")).strip(), str(r.get("decoder", "")).strip(), str(r.get("dataset", "")).strip()): _f(r.get(metric))
        for r in ok_rows
    }
    tensor = np.full((len(families), len(decoders), len(sources)), np.nan, dtype=float)
    for f_idx, family in enumerate(families):
        for d_idx, decoder in enumerate(decoders):
            for s_idx, source in enumerate(sources):
                tensor[f_idx, d_idx, s_idx] = idx.get((family, decoder, source), float("nan"))
    if not np.isfinite(tensor).all():
        return None
    return tensor, families, decoders, sources


def _variance_decomposition_rows(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_labels = [
        ("avg_flip_count", "Average flip count"),
        ("nonempty_flip_rate", "Nonempty flip rate"),
    ]
    component_order = [
        ("family", "Family"),
        ("decoder", "Decoder"),
        ("source_stack", "Source stack"),
        ("family_x_decoder", "Family x decoder"),
        ("family_x_source", "Family x source"),
        ("decoder_x_source", "Decoder x source"),
        ("residual_interaction", "Residual interaction"),
    ]

    rows: list[dict[str, Any]] = []
    for metric, metric_label in metric_labels:
        packed = _balanced_tensor(matrix_rows, metric)
        if packed is None:
            continue
        tensor, families, decoders, sources = packed
        n_family, n_decoder, n_source = tensor.shape
        grand = float(np.mean(tensor))
        family_mean = np.mean(tensor, axis=(1, 2))
        decoder_mean = np.mean(tensor, axis=(0, 2))
        source_mean = np.mean(tensor, axis=(0, 1))
        family_decoder_mean = np.mean(tensor, axis=2)
        family_source_mean = np.mean(tensor, axis=1)
        decoder_source_mean = np.mean(tensor, axis=0)

        sums = {
            "family": float(n_decoder * n_source * np.sum((family_mean - grand) ** 2)),
            "decoder": float(n_family * n_source * np.sum((decoder_mean - grand) ** 2)),
            "source_stack": float(n_family * n_decoder * np.sum((source_mean - grand) ** 2)),
            "family_x_decoder": float(
                n_source * np.sum((family_decoder_mean - family_mean[:, None] - decoder_mean[None, :] + grand) ** 2)
            ),
            "family_x_source": float(
                n_decoder * np.sum((family_source_mean - family_mean[:, None] - source_mean[None, :] + grand) ** 2)
            ),
            "decoder_x_source": float(
                n_family * np.sum((decoder_source_mean - decoder_mean[:, None] - source_mean[None, :] + grand) ** 2)
            ),
        }
        total = float(np.sum((tensor - grand) ** 2))
        sums["residual_interaction"] = max(0.0, total - sum(sums.values()))
        dfs = {
            "family": max(0, n_family - 1),
            "decoder": max(0, n_decoder - 1),
            "source_stack": max(0, n_source - 1),
            "family_x_decoder": max(0, (n_family - 1) * (n_decoder - 1)),
            "family_x_source": max(0, (n_family - 1) * (n_source - 1)),
            "decoder_x_source": max(0, (n_decoder - 1) * (n_source - 1)),
            "residual_interaction": max(0, (n_family - 1) * (n_decoder - 1) * (n_source - 1)),
        }

        for component_key, component_label in component_order:
            ss = sums[component_key]
            df = dfs[component_key]
            rows.append(
                {
                    "metric": metric,
                    "metric_label": metric_label,
                    "component": component_key,
                    "component_label": component_label,
                    "degrees_of_freedom": df,
                    "sum_squares": ss,
                    "mean_square": ss / df if df else float("nan"),
                    "variance_share": ss / total if total > 0.0 else float("nan"),
                }
            )

    return rows


def _plot_variance_decomposition(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.patches import Patch  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping variance decomposition plot ({exc}).")
        return

    if not rows:
        return

    metrics: list[str] = []
    for row in rows:
        metric_label = str(row.get("metric_label", ""))
        if metric_label and metric_label not in metrics:
            metrics.append(metric_label)
    component_labels: list[str] = []
    for row in rows:
        label = str(row.get("component_label", ""))
        if label and label not in component_labels:
            component_labels.append(label)

    colors = {
        "Family": "#2563EB",
        "Decoder": "#DC2626",
        "Source stack": "#059669",
        "Family x decoder": "#7C3AED",
        "Family x source": "#EA580C",
        "Decoder x source": "#0891B2",
        "Residual interaction": "#64748B",
    }
    fig, ax = plt.subplots(figsize=(9.4, 3.7), dpi=320, constrained_layout=False)
    y_positions = np.arange(len(metrics), dtype=float)

    for y_idx, metric_label in enumerate(metrics):
        left = 0.0
        metric_rows = [r for r in rows if str(r.get("metric_label", "")) == metric_label]
        for component_label in component_labels:
            row = next((r for r in metric_rows if str(r.get("component_label", "")) == component_label), None)
            share = _f((row or {}).get("variance_share"))
            if not np.isfinite(share):
                share = 0.0
            ax.barh(
                y_positions[y_idx],
                share,
                left=left,
                height=0.48,
                color=colors.get(component_label, "#94A3B8"),
                edgecolor="white",
                linewidth=0.8,
            )
            if share >= 0.075:
                ax.text(
                    left + share / 2.0,
                    y_positions[y_idx],
                    f"{share * 100:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="white",
                )
            left += share

    ax.set_yticks(y_positions)
    ax.set_yticklabels(metrics)
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("Share of balanced matrix sum of squares")
    ax.set_title("Variance Attribution Across Family, Decoder, and Source Stack", fontsize=11.5, pad=10)
    ax.grid(axis="x", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.invert_yaxis()

    handles = [Patch(facecolor=colors.get(label, "#94A3B8"), label=label) for label in component_labels]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.04), fontsize=8)
    fig.subplots_adjust(left=0.18, right=0.99, top=0.82, bottom=0.30)

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def _plot_logical_error_rate(
    ler_rows: list[dict[str, Any]],
    families: list[str],
    decoders: list[str],
    out_prefix: Path,
) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping LER plot ({exc}).")
        return

    ok_rows = [r for r in ler_rows if str(r.get("status", "")).strip() == "ok"]
    if not ok_rows:
        return

    cols = max(1, len(families))
    fig, axes = plt.subplots(1, cols, figsize=(5.7 * cols, 4.2), dpi=320, constrained_layout=False, sharey=True)
    axes_arr = np.atleast_1d(axes)
    palette = {"bp": "#1f77b4", "mwpm": "#2ca02c", "uf": "#d62728"}

    for i, fam in enumerate(families):
        ax = axes_arr[i]
        fam_rows = [r for r in ok_rows if str(r.get("family", "")) == fam]
        datasets = sorted({str(r.get("dataset", "")) for r in fam_rows if str(r.get("dataset", ""))})
        x = np.arange(len(datasets), dtype=float)
        width = 0.22 if len(decoders) > 1 else 0.45
        offsets = np.linspace(-width * (len(decoders) - 1), width * (len(decoders) - 1), len(decoders)) if decoders else []

        for d_idx, decoder in enumerate(decoders):
            vals: list[float] = []
            lows: list[float] = []
            highs: list[float] = []
            for dataset in datasets:
                row = next(
                    (
                        r
                        for r in fam_rows
                        if str(r.get("dataset", "")) == dataset and str(r.get("decoder", "")) == decoder
                    ),
                    None,
                )
                v = _f((row or {}).get("logical_error_rate"))
                lo = _f((row or {}).get("logical_error_ci95_low"))
                hi = _f((row or {}).get("logical_error_ci95_high"))
                vals.append(v)
                lows.append(max(0.0, v - lo) if np.isfinite(v) and np.isfinite(lo) else 0.0)
                highs.append(max(0.0, hi - v) if np.isfinite(v) and np.isfinite(hi) else 0.0)
            pos = x + float(offsets[d_idx] if len(decoders) > 1 else 0.0)
            ax.bar(pos, vals, width=width, color=palette.get(decoder, "#6B7280"), alpha=0.86, label=decoder.upper())
            ax.errorbar(pos, vals, yerr=[lows, highs], fmt="none", ecolor="#111827", elinewidth=0.8, capsize=2.2)

        ax.set_xticks(x)
        ax.set_xticklabels(datasets, rotation=22, ha="right", fontsize=8)
        ax.set_ylim(0.0, 1.0)
        ax.set_title(f"{fam.upper()} logical-parity errors", fontsize=11.5, pad=10)
        ax.set_xlabel("Source stack")
        if i == 0:
            ax.set_ylabel("Logical error rate")
        ax.grid(axis="y", alpha=0.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.text(-0.12, 1.07, chr(ord("a") + i), transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")

    handles, labels = axes_arr[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=min(3, len(labels)), frameon=False, bbox_to_anchor=(0.5, -0.02), fontsize=8)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.84, bottom=0.30, wspace=0.22)

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
    combined_ler_rows: list[dict[str, Any]] = []

    for row in manifest:
        family = str(row.get("family", "")).strip()
        if not family:
            continue
        matrix_csv = Path(str(row.get("matrix_csv", "")).strip())
        delta_csv = Path(str(row.get("delta_csv", "")).strip())
        results_base_raw = str(row.get("results_base", "")).strip()
        ler_csv = Path(results_base_raw) / "03_analysis" / "table_logical_error_rate.csv" if results_base_raw else None
        if not matrix_csv.exists():
            continue
        matrix_rows = _read_csv(matrix_csv)
        for mrow in matrix_rows:
            combined_matrix_rows.append({"family": family, **mrow})
        if ler_csv is not None and ler_csv.exists():
            for ler_row in _read_csv(ler_csv):
                combined_ler_rows.append({"family": family, **ler_row})
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
        ler_src = [
            _f(r.get("logical_error_rate"))
            for r in combined_ler_rows
            if str(r.get("family", "")) == str(row["family"])
            and str(r.get("decoder", "")) == str(row["decoder"])
            and str(r.get("dataset", "")) != "lidmas_reference"
            and str(r.get("status", "")) == "ok"
        ]
        ler_ref = [
            _f(r.get("logical_error_rate"))
            for r in combined_ler_rows
            if str(r.get("family", "")) == str(row["family"])
            and str(r.get("decoder", "")) == str(row["decoder"])
            and str(r.get("dataset", "")) == "lidmas_reference"
            and str(r.get("status", "")) == "ok"
        ]
        row["mean_logical_error_rate_sources"] = float(np.mean(ler_src)) if ler_src else float("nan")
        row["mean_logical_error_rate_reference"] = float(np.mean(ler_ref)) if ler_ref else float("nan")

    observed_families = {str(r["family"]) for r in summary_rows}
    families = [fam for fam in family_order if fam in observed_families]
    families.extend(sorted(observed_families - set(families)))
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

    rank_rows, rank_heatmaps, rank_columns = _rank_stability_by_family(
        combined_matrix_rows,
        families,
        decoders_all,
        bootstrap=int(args.rank_bootstrap),
        seed=int(args.rank_seed),
    )
    variance_rows = _variance_decomposition_rows(combined_matrix_rows)

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
            "mean_logical_error_rate_sources",
            "mean_logical_error_rate_reference",
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
        combined_ler_rows,
        [
            "family",
            "dataset",
            "decoder",
            "status",
            "truth_lines",
            "response_lines",
            "valid_lines",
            "logical_error_count",
            "logical_error_rate",
            "logical_error_ci95_low",
            "logical_error_ci95_high",
            "logical_observable",
            "truth_model",
            "truth_file",
            "response_file",
        ],
        out_dir / "table_logical_error_rate.csv",
    )
    _write_csv(
        norm_rows,
        ["family", "decoder", "norm_flip", "norm_warning", "norm_stack_delta"],
        out_dir / "table_cross_family_normalized.csv",
    )
    _write_csv(
        rank_rows,
        ["family", "decoder", "rank", "rank_prob", "bootstrap_samples", "source_count"],
        out_dir / "table_rank_stability_family.csv",
    )
    _write_csv(
        variance_rows,
        [
            "metric",
            "metric_label",
            "component",
            "component_label",
            "degrees_of_freedom",
            "sum_squares",
            "mean_square",
            "variance_share",
        ],
        out_dir / "table_variance_decomposition.csv",
    )

    _plot_family_tradeoff(summary_rows, families, out_dir / "figure_family_tradeoff")
    _plot_source_vs_lidmas(combined_source_rows, families, out_dir / "figure_source_vs_lidmas")
    _plot_family_delta_forest(delta_rows, families, out_dir / "figure_family_delta_forest")
    _plot_normalized_trends(norm_rows, family_order if family_order else families, decoders_all, out_dir / "figure_cross_family_normalized_trends")
    _plot_rank_stability_by_family(rank_heatmaps, families, decoders_all, rank_columns, out_dir / "figure_rank_stability_family")
    _plot_variance_decomposition(variance_rows, out_dir / "figure_variance_decomposition")
    _plot_logical_error_rate(combined_ler_rows, families, decoders_all, out_dir / "figure_logical_error_rate_family")

    summary_md = out_dir / "summary_code_family_comparison.md"
    with summary_md.open("w", encoding="utf-8") as f:
        f.write("# paper_04 Surface-vs-GKP Decoder Comparison\n\n")
        f.write("This analysis reports:\n\n")
        f.write("1. within-family decoder tradeoffs (surface and gkp separately),\n")
        f.write("2. source-vs-reference effect sizes within each family,\n")
        f.write("3. cross-family normalized trends (no raw threshold equivalence claims),\n")
        f.write("4. source-bootstrap rank stability within each family,\n")
        f.write("5. balanced variance attribution across family, decoder, and source stack,\n")
        f.write("6. outer-code logical-parity error rates from hidden truth sidecars.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
