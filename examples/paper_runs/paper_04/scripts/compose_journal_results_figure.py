#!/usr/bin/env python3
"""Compose a journal-style multi-panel summary figure for paper_04 results."""

from __future__ import annotations

import argparse
import csv
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


DECODER_ORDER = ["bp", "mwpm", "uf"]
FAMILY_ORDER = ["surface", "gkp"]
SOURCE_ORDER = ["cirq", "pennylane", "qiskit"]
DECODER_COLORS = {
    "bp": "#2563EB",
    "mwpm": "#059669",
    "uf": "#DC2626",
}
SOURCE_COLORS = {
    "cirq": "#7C3AED",
    "pennylane": "#0284C7",
    "qiskit": "#16A34A",
}
FAMILY_MARKERS = {
    "surface": "o",
    "gkp": "s",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True, help="Directory containing paper_04 analysis CSV files.")
    parser.add_argument("--out-prefix", required=True, help="Output prefix without extension.")
    parser.add_argument("--manuscript-dir", help="Optional manuscript figure directory to receive copied outputs.")
    parser.add_argument("--write-standalone", action="store_true", help="Overwrite standalone manuscript result figures using the journal visual style.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def f(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, "nan"))
    except (TypeError, ValueError):
        return float("nan")


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return phat, max(0.0, center - half), min(1.0, center + half)


def panel_label(ax: Any, label: str, x: float = -0.13, y: float = 1.08) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=8.6, fontweight="bold", va="top", ha="left")


def tidy_axes(ax: Any, *, grid: str | None = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(axis=grid, color="#E5E7EB", linewidth=0.45, zorder=0)
    ax.tick_params(width=0.6, length=2.5, color="#374151")


def save_outputs(fig: Any, out_prefix: Path, manuscript_dir: Path | None = None) -> list[Path]:
    out_files: list[Path] = []
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".pdf", ".png", ".svg"):
        out = out_prefix.with_suffix(ext)
        fig.savefig(out, bbox_inches="tight")
        out_files.append(out)
    if manuscript_dir is not None:
        manuscript_dir.mkdir(parents=True, exist_ok=True)
        for out in out_files:
            shutil.copy2(out, manuscript_dir / out.name)
    return out_files


def source_mean_ler(ler_rows: list[dict[str, str]]) -> dict[tuple[str, str], tuple[float, float, float]]:
    out: dict[tuple[str, str], tuple[float, float, float]] = {}
    for fam in FAMILY_ORDER:
        for dec in DECODER_ORDER:
            rows = [
                r
                for r in ler_rows
                if r.get("family") == fam and r.get("decoder") == dec and r.get("dataset") != "lidmas_reference"
            ]
            k = sum(int(float(r.get("logical_error_count", "0"))) for r in rows)
            n = sum(int(float(r.get("valid_lines", "0"))) for r in rows)
            out[(fam, dec)] = wilson(k, n)
    return out


def add_panel_a_tradeoff(ax: Any, summary_rows: list[dict[str, str]], label: str | None = "a") -> None:
    for fam in FAMILY_ORDER:
        rows = [r for r in summary_rows if r.get("family") == fam]
        rows = sorted(rows, key=lambda r: DECODER_ORDER.index(r.get("decoder", "")))
        xs = [f(r, "mean_avg_flip_sources") for r in rows]
        ys = [f(r, "mean_logical_error_rate_sources") for r in rows]
        ax.plot(xs, ys, color="#9CA3AF", linewidth=0.8, zorder=1)
        for r, x, y in zip(rows, xs, ys):
            dec = r.get("decoder", "")
            ax.scatter(
                x,
                y,
                s=42,
                marker=FAMILY_MARKERS[fam],
                facecolor=DECODER_COLORS.get(dec, "#6B7280"),
                edgecolor="white",
                linewidth=0.65,
                zorder=3,
            )
            ax.text(x + 0.05, y + 0.002, dec.upper(), fontsize=5.5, color="#111827", va="bottom")

    ax.set_xlabel("mean flips")
    ax.set_ylabel("logical-parity error rate")
    ax.set_ylim(0.425, 0.515)
    ax.set_xlim(1.25, 6.15)
    if label:
        panel_label(ax, label)
    tidy_axes(ax, grid="both")

    from matplotlib.lines import Line2D  # type: ignore

    handles = [
        Line2D([0], [0], marker=FAMILY_MARKERS["surface"], color="none", markerfacecolor="#6B7280", markeredgecolor="white", markersize=5.0, label="surface"),
        Line2D([0], [0], marker=FAMILY_MARKERS["gkp"], color="none", markerfacecolor="#6B7280", markeredgecolor="white", markersize=5.0, label="GKP"),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=5.2, handlelength=0.8, borderpad=0.2)


def add_delta_axis(ax: Any, rows: list[dict[str, str]], fam: str, show_ylabel: bool) -> None:
    fam_rows = [r for r in rows if r.get("family") == fam]
    fam_rows = sorted(
        fam_rows,
        key=lambda r: (DECODER_ORDER.index(r.get("decoder", "")), SOURCE_ORDER.index(r.get("source_dataset", ""))),
    )
    y = np.arange(len(fam_rows), dtype=float)
    for yi, r in zip(y, fam_rows):
        src = r.get("source_dataset", "")
        dec = r.get("decoder", "")
        mean = f(r, "delta_mean_source_minus_reference")
        lo = f(r, "delta_ci95_low")
        hi = f(r, "delta_ci95_high")
        ax.plot([lo, hi], [yi, yi], color=SOURCE_COLORS.get(src, "#6B7280"), linewidth=0.85, alpha=0.95)
        ax.scatter(mean, yi, s=13, color=SOURCE_COLORS.get(src, "#6B7280"), edgecolor="white", linewidth=0.35, zorder=3)
    ax.axvline(0.0, color="#111827", linewidth=0.6, alpha=0.7)
    ax.set_title(fam.upper(), fontsize=6.2, pad=2)
    ax.set_yticks(y)
    if show_ylabel:
        labels = [f"{r.get('decoder','').upper()}-{r.get('source_dataset','')[:1].upper()}" for r in fam_rows]
        ax.set_yticklabels(labels, fontsize=4.8)
    else:
        ax.set_yticklabels([])
    ax.invert_yaxis()
    ax.set_xlabel(r"$\Delta$ flips")
    tidy_axes(ax, grid="x")
    if fam == "surface":
        ax.set_xlim(-0.26, 0.31)
    else:
        ax.set_xlim(-2.45, 0.72)


def add_panel_c_ler(ax: Any, ler_rows: list[dict[str, str]], label: str | None = "c") -> None:
    agg = source_mean_ler(ler_rows)
    family_x = {"surface": 0.0, "gkp": 1.0}
    offsets = {"bp": -0.17, "mwpm": 0.0, "uf": 0.17}
    for fam in FAMILY_ORDER:
        for dec in DECODER_ORDER:
            rate, lo, hi = agg[(fam, dec)]
            x = family_x[fam] + offsets[dec]
            ax.errorbar(
                [x],
                [rate],
                yerr=[[rate - lo], [hi - rate]],
                fmt=FAMILY_MARKERS[fam],
                markersize=4.8,
                color=DECODER_COLORS[dec],
                markeredgecolor="white",
                markeredgewidth=0.55,
                elinewidth=0.8,
                capsize=2.2,
                zorder=3,
            )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["surface", "GKP"])
    ax.set_ylabel(r"$\lambda$ (source aggregate)")
    ax.set_ylim(0.39, 0.53)
    if label:
        panel_label(ax, label)
    tidy_axes(ax, grid="y")

    from matplotlib.lines import Line2D  # type: ignore

    handles = [
        Line2D([0], [0], marker="o", color=DECODER_COLORS[d], label=d.upper(), markersize=4.2, linewidth=0.9)
        for d in DECODER_ORDER
    ]
    ax.legend(handles=handles, frameon=False, loc="upper left", fontsize=5.2, ncol=3, handlelength=1.0, columnspacing=0.6)


def add_panel_d_rank(ax: Any, rank_rows: list[dict[str, str]], label: str | None = "d") -> Any:
    rows: list[tuple[str, str]] = [(fam, dec) for fam in FAMILY_ORDER for dec in DECODER_ORDER]
    mat = np.zeros((len(rows), 3), dtype=float)
    for i, (fam, dec) in enumerate(rows):
        for r in rank_rows:
            if r.get("family") == fam and r.get("decoder") == dec:
                rank = int(float(r.get("rank", "0")))
                if 1 <= rank <= 3:
                    mat[i, rank - 1] = f(r, "rank_prob")
    im = ax.imshow(mat, cmap="Blues", vmin=0.0, vmax=1.0, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat[i, j]
            color = "white" if val > 0.55 else "#111827"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=4.9, color=color, fontweight="bold" if val > 0.55 else "normal")
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["1", "2", "3"])
    ax.set_yticks(np.arange(len(rows)))
    ax.set_yticklabels([f"{fam[0].upper()} {dec.upper()}" for fam, dec in rows], fontsize=5.1)
    ax.set_xlabel("rank")
    ax.set_ylabel("family decoder")
    if label:
        panel_label(ax, label)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    return im


def add_panel_e_variance(ax: Any, variance_rows: list[dict[str, str]], label: str | None = "e") -> None:
    metrics = ["avg_flip_count", "nonempty_flip_rate"]
    metric_labels = {"avg_flip_count": "mean flips", "nonempty_flip_rate": "nonempty rate"}
    components = [
        "family",
        "decoder",
        "source_stack",
        "family_x_decoder",
        "family_x_source",
        "decoder_x_source",
        "residual_interaction",
    ]
    comp_labels = {
        "family": "family",
        "decoder": "decoder",
        "source_stack": "source",
        "family_x_decoder": "fam x dec",
        "family_x_source": "fam x src",
        "decoder_x_source": "dec x src",
        "residual_interaction": "resid.",
    }
    comp_colors = {
        "family": "#2563EB",
        "decoder": "#DC2626",
        "source_stack": "#059669",
        "family_x_decoder": "#8B5CF6",
        "family_x_source": "#F97316",
        "decoder_x_source": "#0891B2",
        "residual_interaction": "#64748B",
    }
    y = np.arange(len(metrics), dtype=float)
    for yi, metric in zip(y, metrics):
        left = 0.0
        for comp in components:
            row = next((r for r in variance_rows if r.get("metric") == metric and r.get("component") == comp), None)
            share = f(row or {}, "variance_share")
            if not np.isfinite(share):
                share = 0.0
            ax.barh(yi, share, left=left, height=0.48, color=comp_colors[comp], edgecolor="white", linewidth=0.35)
            if share >= 0.10:
                ax.text(left + share / 2, yi, f"{100*share:.0f}%", ha="center", va="center", fontsize=4.9, color="white", fontweight="bold")
            left += share
    ax.set_xlim(0.0, 1.0)
    ax.set_yticks(y)
    ax.set_yticklabels([metric_labels[m] for m in metrics])
    ax.set_xlabel("variance share")
    ax.invert_yaxis()
    if label:
        panel_label(ax, label)
    tidy_axes(ax, grid="x")

    from matplotlib.patches import Patch  # type: ignore

    handles = [Patch(facecolor=comp_colors[c], label=comp_labels[c]) for c in components]
    ax.legend(handles=handles, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.54), ncol=4, fontsize=4.8, handlelength=1.0, columnspacing=0.8)


def add_panel_f_normalized(ax: Any, norm_rows: list[dict[str, str]], label: str | None = "f") -> None:
    metrics = [("norm_flip", "flip"), ("norm_stack_delta", "source delta")]
    rows: list[tuple[str, str, str]] = []
    for metric, label in metrics:
        for dec in DECODER_ORDER:
            rows.append((metric, label, dec))
    y = np.arange(len(rows), dtype=float)
    for yi, (metric, _label, dec) in zip(y, rows):
        values = {}
        for fam in FAMILY_ORDER:
            row = next((r for r in norm_rows if r.get("family") == fam and r.get("decoder") == dec), None)
            values[fam] = f(row or {}, metric)
        ax.plot([values["surface"], values["gkp"]], [yi, yi], color=DECODER_COLORS[dec], linewidth=0.85, alpha=0.55)
        ax.scatter(values["surface"], yi, s=17, marker="o", color=DECODER_COLORS[dec], edgecolor="white", linewidth=0.4, zorder=3)
        ax.scatter(values["gkp"], yi, s=20, marker="s", color=DECODER_COLORS[dec], edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_xlim(-0.05, 1.05)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{label} {dec.upper()}" for _, label, dec in rows], fontsize=5.1)
    ax.set_xlabel("within-family normalized value")
    ax.invert_yaxis()
    if label:
        panel_label(ax, label)
    tidy_axes(ax, grid="x")

    from matplotlib.lines import Line2D  # type: ignore

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#6B7280", markeredgecolor="white", markersize=4.2, label="surface"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#6B7280", markeredgecolor="white", markersize=4.2, label="GKP"),
    ]
    ax.legend(handles=handles, frameon=False, loc="upper right", fontsize=5.2, handlelength=0.9)


def add_source_vs_reference_axis(ax: Any, rows: list[dict[str, str]], fam: str, show_ylabel: bool) -> None:
    fam_rows = [r for r in rows if r.get("family") == fam]
    x_base = {dec: i for i, dec in enumerate(DECODER_ORDER)}
    offsets = {"cirq": -0.16, "pennylane": 0.0, "qiskit": 0.16}
    ref_seen: set[str] = set()
    for dec in DECODER_ORDER:
        dec_rows = [r for r in fam_rows if r.get("decoder") == dec]
        if not dec_rows:
            continue
        x = x_base[dec]
        ref = f(dec_rows[0], "avg_flip_count_reference")
        ax.scatter(
            x,
            ref,
            marker="D",
            s=24,
            color="#111827",
            edgecolor="white",
            linewidth=0.45,
            zorder=4,
            label="LiDMaS+ reference" if not ref_seen else None,
        )
        ref_seen.add("reference")
        for r in dec_rows:
            src = r.get("source_dataset", "")
            x_src = x + offsets.get(src, 0.0)
            y_src = f(r, "avg_flip_count_source")
            ax.plot([x, x_src], [ref, y_src], color=SOURCE_COLORS.get(src, "#6B7280"), linewidth=0.75, alpha=0.55, zorder=1)
            ax.scatter(
                x_src,
                y_src,
                marker="o",
                s=25,
                color=SOURCE_COLORS.get(src, "#6B7280"),
                edgecolor="white",
                linewidth=0.45,
                zorder=3,
                label=src if dec == DECODER_ORDER[0] else None,
            )
    ax.set_title(fam.upper(), fontsize=8.0, pad=5)
    ax.set_xticks([x_base[d] for d in DECODER_ORDER])
    ax.set_xticklabels([d.upper() for d in DECODER_ORDER])
    ax.set_xlabel("decoder")
    if show_ylabel:
        ax.set_ylabel("mean flips")
    else:
        ax.set_ylabel("")
    if fam == "gkp":
        ax.set_ylim(0.55, 4.65)
    else:
        ax.set_ylim(2.2, 6.25)
    tidy_axes(ax, grid="y")


def render_standalone_figures(
    analysis_dir: Path,
    manuscript_dir: Path | None,
    summary_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    ler_rows: list[dict[str, str]],
    rank_rows: list[dict[str, str]],
    variance_rows: list[dict[str, str]],
    norm_rows: list[dict[str, str]],
) -> list[Path]:
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.lines import Line2D  # type: ignore

    written: list[Path] = []

    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.75), constrained_layout=False)
    add_source_vs_reference_axis(axes[0], source_rows, "gkp", True)
    add_source_vs_reference_axis(axes[1], source_rows, "surface", False)
    handles = [
        Line2D([0], [0], marker="D", color="none", markerfacecolor="#111827", markeredgecolor="white", markersize=4.3, label="LiDMaS+ reference"),
        *[
            Line2D([0], [0], marker="o", color=SOURCE_COLORS[src], markerfacecolor=SOURCE_COLORS[src], markeredgecolor="white", markersize=4.3, linewidth=0.9, label=src)
            for src in SOURCE_ORDER
        ],
    ]
    fig.legend(handles=handles, frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.03), fontsize=6.0, handlelength=1.0, columnspacing=0.9)
    fig.subplots_adjust(bottom=0.22)
    written.extend(save_outputs(fig, analysis_dir / "figure_source_vs_lidmas", manuscript_dir))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.65, 3.25), constrained_layout=True)
    add_panel_a_tradeoff(ax, summary_rows, label=None)
    written.extend(save_outputs(fig, analysis_dir / "figure_family_tradeoff", manuscript_dir))
    plt.close(fig)

    fig = plt.figure(figsize=(7.05, 3.0), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, wspace=0.18)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    add_delta_axis(ax1, delta_rows, "gkp", True)
    add_delta_axis(ax2, delta_rows, "surface", False)
    handles = [
        Line2D([0], [0], marker="o", color=SOURCE_COLORS[src], markerfacecolor=SOURCE_COLORS[src], markeredgecolor="white", markersize=4.3, linewidth=0.9, label=src)
        for src in SOURCE_ORDER
    ]
    ax2.legend(handles=handles, frameon=False, loc="upper right", fontsize=5.8, handlelength=0.9)
    written.extend(save_outputs(fig, analysis_dir / "figure_family_delta_forest", manuscript_dir))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.4, 3.0), constrained_layout=True)
    add_panel_f_normalized(ax, norm_rows, label=None)
    written.extend(save_outputs(fig, analysis_dir / "figure_cross_family_normalized_trends", manuscript_dir))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.2, 3.1), constrained_layout=True)
    add_panel_d_rank(ax, rank_rows, label=None)
    written.extend(save_outputs(fig, analysis_dir / "figure_rank_stability_family", manuscript_dir))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.4, 2.75), constrained_layout=True)
    add_panel_e_variance(ax, variance_rows, label=None)
    written.extend(save_outputs(fig, analysis_dir / "figure_variance_decomposition", manuscript_dir))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.25, 3.0), constrained_layout=True)
    add_panel_c_ler(ax, ler_rows, label=None)
    written.extend(save_outputs(fig, analysis_dir / "figure_logical_error_rate_family", manuscript_dir))
    plt.close(fig)

    return written


def main() -> int:
    args = parse_args()
    analysis_dir = Path(args.analysis_dir)
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", Path(tempfile.gettempdir()) / "lidmas_matplotlib"))
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))

    summary_rows = read_csv(analysis_dir / "table_family_decoder_summary.csv")
    delta_rows = read_csv(analysis_dir / "table_family_delta_effects.csv")
    source_rows = read_csv(analysis_dir / "table_source_vs_lidmas.csv")
    ler_rows = read_csv(analysis_dir / "table_logical_error_rate.csv")
    rank_rows = read_csv(analysis_dir / "table_rank_stability_family.csv")
    variance_rows = read_csv(analysis_dir / "table_variance_decomposition.csv")
    norm_rows = read_csv(analysis_dir / "table_cross_family_normalized.csv")

    import matplotlib  # type: ignore

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt  # type: ignore

    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.family": "Arial",
            "font.size": 6.2,
            "axes.labelsize": 6.2,
            "axes.titlesize": 6.2,
            "xtick.labelsize": 5.4,
            "ytick.labelsize": 5.4,
            "legend.fontsize": 5.2,
            "axes.linewidth": 0.65,
            "savefig.dpi": 420,
        }
    )

    fig = plt.figure(figsize=(7.05, 6.35), constrained_layout=False)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.05, 1.0, 0.92], hspace=0.62, wspace=0.42)

    ax_a = fig.add_subplot(gs[0, 0])
    add_panel_a_tradeoff(ax_a, summary_rows)

    sub_b = gs[0, 1].subgridspec(1, 2, wspace=0.22)
    ax_b1 = fig.add_subplot(sub_b[0, 0])
    ax_b2 = fig.add_subplot(sub_b[0, 1])
    add_delta_axis(ax_b1, delta_rows, "gkp", True)
    add_delta_axis(ax_b2, delta_rows, "surface", False)
    panel_label(ax_b1, "b", x=-0.22)
    from matplotlib.lines import Line2D  # type: ignore

    ax_b2.legend(
        handles=[
            Line2D([0], [0], marker="o", color=SOURCE_COLORS[s], label=s, markersize=3.2, linewidth=0.8)
            for s in SOURCE_ORDER
        ],
        frameon=False,
        loc="upper right",
        fontsize=4.8,
        handlelength=0.9,
    )

    ax_c = fig.add_subplot(gs[1, 0])
    add_panel_c_ler(ax_c, ler_rows)

    ax_d = fig.add_subplot(gs[1, 1])
    add_panel_d_rank(ax_d, rank_rows)

    ax_e = fig.add_subplot(gs[2, 0])
    add_panel_e_variance(ax_e, variance_rows)

    ax_f = fig.add_subplot(gs[2, 1])
    add_panel_f_normalized(ax_f, norm_rows)

    fig.subplots_adjust(left=0.075, right=0.985, top=0.972, bottom=0.095)

    manuscript_dir = Path(args.manuscript_dir) if args.manuscript_dir else None
    out_files = save_outputs(fig, out_prefix, manuscript_dir)
    plt.close(fig)

    if args.write_standalone:
        out_files.extend(
            render_standalone_figures(
                analysis_dir,
                manuscript_dir,
                summary_rows,
                delta_rows,
                source_rows,
                ler_rows,
                rank_rows,
                variance_rows,
                norm_rows,
            )
        )

    for out in out_files:
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
