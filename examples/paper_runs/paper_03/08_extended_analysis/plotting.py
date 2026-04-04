#!/usr/bin/env python3
"""Figure generation for paper_03 extended analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from metrics import DECODER_ORDER, decoder_label, pretty_dataset, scope_label

DECODER_COLORS = {
    "mwpm": "#1f77b4",
    "uf": "#ff7f0e",
    "bp": "#2ca02c",
    "neural_mwpm": "#d62728",
    "stub": "#9467bd",
}
PROVIDER_MARKERS = {
    "Aurora": "o",
    "QCA": "s",
    "GKP": "^",
    "FixtureJob": "D",
    "Quandela": "P",
    "Google": "X",
}
PROVIDER_LINESTYLES = {
    "Aurora": "-",
    "QCA": "--",
    "GKP": "-.",
    "FixtureJob": ":",
    "Quandela": (0, (4, 1, 1, 1)),
    "Google": (0, (2, 2)),
}
DATASET_CODES = {
    "job": "J",
    "aurora": "AUR",
    "gkp": "GKP",
    "qca": "QCA",
    "aurora_batch0_qpu5": "AB0",
    "qca_fig3b": "QF3",
    "synth_aurora_batch0_qpu5_heldout": "SAH",
    "synth_qca_fig3b_heldout": "SQH",
}


@dataclass
class FigureResult:
    figure_id: str
    title: str
    filename_base: str
    table_filename: str
    status: str
    main_result: str
    caption: str


def configure_matplotlib() -> None:
    import matplotlib as mpl  # type: ignore

    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "-",
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8.5,
            "savefig.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _decoder_sort_key(name: str) -> tuple[int, str]:
    try:
        idx = DECODER_ORDER.index(name)
    except ValueError:
        idx = 999
    return (idx, name)


def _table_write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.8f")


def _save_figure(fig: Any, out_base: Path, export_svg: bool) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_base.with_suffix(".png"), dpi=320, bbox_inches="tight")
    fig.savefig(
        out_base.with_name(out_base.name + "_transparent").with_suffix(".png"),
        dpi=320,
        bbox_inches="tight",
        transparent=True,
    )
    fig.savefig(out_base.with_suffix(".pdf"), dpi=320, bbox_inches="tight")
    if export_svg:
        fig.savefig(out_base.with_suffix(".svg"), dpi=320, bbox_inches="tight")


def _scope_panels(df: pd.DataFrame) -> list[str]:
    order = ["fixture", "real_slice", "synthetic_holdout", "real_full_hpc"]
    return [s for s in order if s in set(df["scope"].astype(str))]


def _marker_for_provider(provider: str) -> str:
    return PROVIDER_MARKERS.get(provider, "o")


def _color_for_decoder(decoder: str) -> str:
    return DECODER_COLORS.get(decoder, "#444444")


def _line_for_provider(provider: str) -> Any:
    return PROVIDER_LINESTYLES.get(provider, "-")


def _dataset_code(dataset: str) -> str:
    key = str(dataset).strip()
    if key in DATASET_CODES:
        return DATASET_CODES[key]
    letters = "".join(ch for ch in key.upper() if ch.isalnum())
    if not letters:
        return "UNK"
    return letters[:4]


def _dataset_code_map_text(datasets: list[str]) -> str:
    pairs = [f"{_dataset_code(ds)}={pretty_dataset(ds)}" for ds in datasets]
    return "; ".join(pairs)


def generate_figure_a(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Decoder Tradeoff Scatter"
    figure_base = "figure_A_decoder_tradeoff_scatter"
    table_name = "figure_A_decoder_tradeoff_scatter.csv"
    need_cols = [
        "scope",
        "dataset",
        "provider",
        "decoder",
        "request_lines",
        "nonempty_flip_rate",
        "avg_flip_count",
        "syndrome_satisfied_rate",
    ]
    if not set(need_cols).issubset(set(merged_df.columns)):
        return FigureResult("A", title, figure_base, table_name, "skipped", "missing required columns", "")

    df = merged_df[need_cols].copy()
    df = df[np.isfinite(df["avg_flip_count"]) & np.isfinite(df["syndrome_satisfied_rate"])].copy()
    if df.empty:
        return FigureResult("A", title, figure_base, table_name, "skipped", "no valid rows", "")

    req_max = max(float(df["request_lines"].max()), 1.0)
    df["point_size"] = 80.0 + 220.0 * (
        0.6 * (df["request_lines"].astype(float) / req_max) + 0.4 * df["nonempty_flip_rate"].fillna(0.0).astype(float)
    )
    df["dataset_code"] = df["dataset"].astype(str).map(_dataset_code)
    _table_write(df, tables_dir / table_name)

    scopes = _scope_panels(df)
    if save_figures:
        import matplotlib.lines as mlines  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        fig, axes = plt.subplots(1, len(scopes), figsize=(6.2 * len(scopes), 4.9), sharey=True)
        if len(scopes) == 1:
            axes = [axes]

        for ax, scope in zip(axes, scopes):
            scope_df = df[df["scope"] == scope].copy()
            ax.set_title(scope_label(scope))
            ax.set_xlabel("Average flip count")
            ax.set_ylabel("Syndrome satisfaction rate")
            ax.set_ylim(0.0, 1.03)
            xmin = float(scope_df["avg_flip_count"].min()) if not scope_df.empty else 0.0
            xmax = float(scope_df["avg_flip_count"].max()) if not scope_df.empty else 1.0
            xpad = max((xmax - xmin) * 0.16, 0.03)
            ax.set_xlim(xmin - xpad, xmax + xpad)
            ax.margins(y=0.08)
            for i, row in scope_df.iterrows():
                marker = _marker_for_provider(str(row["provider"]))
                color = _color_for_decoder(str(row["decoder"]))
                ax.scatter(
                    float(row["avg_flip_count"]),
                    float(row["syndrome_satisfied_rate"]),
                    s=float(row["point_size"]),
                    marker=marker,
                    c=color,
                    alpha=0.86,
                    linewidths=0.7,
                    edgecolors="black",
                )
            # One short code label per dataset cluster for readability.
            clusters = (
                scope_df.groupby(["dataset", "dataset_code"], as_index=False)[["avg_flip_count", "syndrome_satisfied_rate"]]
                .mean()
                .sort_values("dataset")
            )
            offsets = [(-0.018, 0.020), (0.014, 0.021), (0.012, -0.018), (-0.022, -0.015), (0.0, 0.026)]
            xspan = max((xmax - xmin), 1e-6)
            for j, row in clusters.iterrows():
                ox_frac, oy = offsets[j % len(offsets)]
                ox = ox_frac * xspan
                ax.text(
                    float(row["avg_flip_count"]) + ox,
                    float(row["syndrome_satisfied_rate"]) + oy,
                    str(row["dataset_code"]),
                    fontsize=7.3,
                    ha="left",
                    va="center",
                    bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
                    zorder=5,
                )

        decoder_handles = [
            mlines.Line2D(
                [], [], color=_color_for_decoder(dec), marker="o", linestyle="None", markersize=7, label=decoder_label(dec)
            )
            for dec in sorted(df["decoder"].astype(str).unique(), key=_decoder_sort_key)
        ]
        provider_handles = [
            mlines.Line2D([], [], color="black", marker=_marker_for_provider(prov), linestyle="None", markersize=7, label=prov)
            for prov in sorted(df["provider"].astype(str).unique())
        ]
        leg_dec = fig.legend(
            handles=decoder_handles,
            title="Decoder",
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.34, 0.93),
            ncol=min(4, len(decoder_handles)),
        )
        fig.add_artist(leg_dec)
        fig.legend(
            handles=provider_handles,
            title="Provider",
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.76, 0.93),
            ncol=min(4, len(provider_handles)),
        )
        fig.suptitle(title, y=0.99)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    decoder_means = df.groupby("decoder", as_index=False)[["avg_flip_count", "syndrome_satisfied_rate"]].mean()
    low_flip_decoder = str(decoder_means.sort_values("avg_flip_count").iloc[0]["decoder"])
    high_sat_decoder = str(decoder_means.sort_values("syndrome_satisfied_rate", ascending=False).iloc[0]["decoder"])
    main_result = (
        f"Lower intervention volume and correction quality diverge: lowest mean flips={decoder_label(low_flip_decoder)}, "
        f"highest mean satisfaction={decoder_label(high_sat_decoder)}."
    )
    code_map = _dataset_code_map_text(sorted(df["dataset"].astype(str).unique()))
    caption = (
        "Decoder tradeoff scatter across fixture/real/synthetic scopes. Point color encodes decoder, marker encodes provider/dataset, "
        "and size scales with request volume/nonempty-flip activity. Short point labels use dataset codes to reduce overlap. "
        f"Code map: {code_map}. The plot shows that low correction volume does not always imply higher syndrome-satisfaction quality."
    )
    return FigureResult("A", title, figure_base, table_name, "ok", main_result, caption)


def generate_figure_b(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Residual Burden vs Intervention Volume"
    figure_base = "figure_B_residual_vs_intervention"
    table_name = "figure_B_residual_vs_intervention.csv"
    need_cols = ["scope", "dataset", "provider", "decoder", "avg_flip_count", "residual_nonzero_rate"]
    if not set(need_cols).issubset(set(merged_df.columns)):
        return FigureResult("B", title, figure_base, table_name, "skipped", "missing required columns", "")

    df = merged_df[need_cols].copy()
    df = df[np.isfinite(df["avg_flip_count"]) & np.isfinite(df["residual_nonzero_rate"])].copy()
    if df.empty:
        return FigureResult("B", title, figure_base, table_name, "skipped", "no valid rows", "")

    _table_write(df, tables_dir / table_name)
    scopes = _scope_panels(df)
    if save_figures:
        import matplotlib.lines as mlines  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        fig, axes = plt.subplots(1, len(scopes), figsize=(6.1 * len(scopes), 4.8), sharey=True)
        if len(scopes) == 1:
            axes = [axes]
        for ax, scope in zip(axes, scopes):
            scope_df = df[df["scope"] == scope].sort_values("avg_flip_count")
            ax.set_title(scope_label(scope))
            ax.set_xlabel("Average flip count")
            ax.set_ylabel("Residual nonzero rate")
            ax.set_ylim(-0.02, min(1.05, float(scope_df["residual_nonzero_rate"].max() * 1.15 + 0.02)))
            for _, row in scope_df.iterrows():
                ax.scatter(
                    float(row["avg_flip_count"]),
                    float(row["residual_nonzero_rate"]),
                    s=110,
                    marker=_marker_for_provider(str(row["provider"])),
                    c=_color_for_decoder(str(row["decoder"])),
                    edgecolors="black",
                    linewidths=0.7,
                    alpha=0.88,
                )
            xs = scope_df["avg_flip_count"].to_numpy(dtype=float)
            ys = scope_df["residual_nonzero_rate"].to_numpy(dtype=float)
            if xs.size > 0:
                order = np.argsort(xs)
                xs = xs[order]
                ys = ys[order]
                running = np.minimum.accumulate(ys)
                ax.plot(xs, running, color="#111111", linewidth=1.1, linestyle="--", alpha=0.75, label="Pareto envelope")
            median_x = float(scope_df["avg_flip_count"].median())
            median_y = float(scope_df["residual_nonzero_rate"].median())
            ax.axvline(median_x, color="#b0b0b0", linewidth=0.8, linestyle=":")
            ax.axhline(median_y, color="#b0b0b0", linewidth=0.8, linestyle=":")
            ax.text(
                0.02,
                0.96,
                "conservative + residual-heavy",
                transform=ax.transAxes,
                fontsize=7.4,
                va="top",
                ha="left",
                color="#444444",
            )

        dec_handles = [
            mlines.Line2D(
                [], [], color=_color_for_decoder(dec), marker="o", linestyle="None", markersize=7, label=decoder_label(dec)
            )
            for dec in sorted(df["decoder"].astype(str).unique(), key=_decoder_sort_key)
        ]
        fig.legend(
            handles=dec_handles,
            title="Decoder",
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.92),
            ncol=min(4, len(dec_handles)),
        )
        fig.suptitle(title, y=0.99)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.88))
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    means = df.groupby("decoder", as_index=False)[["avg_flip_count", "residual_nonzero_rate"]].mean()
    low_flip = str(means.sort_values("avg_flip_count").iloc[0]["decoder"])
    high_residual = str(means.sort_values("residual_nonzero_rate", ascending=False).iloc[0]["decoder"])
    main_result = (
        f"Conservative intervention and residual burden separate across decoders: lowest mean flips={decoder_label(low_flip)}, "
        f"highest residual burden={decoder_label(high_residual)}."
    )
    caption = (
        "Residual burden versus intervention volume by scope. Dashed envelopes indicate Pareto-style trends. The plot isolates decoders "
        "that apply conservative corrections but leave more unresolved syndrome."
    )
    return FigureResult("B", title, figure_base, table_name, "ok", main_result, caption)


def _sparsity_bucket(event_count: int) -> str:
    if event_count <= 0:
        return "0"
    if event_count == 1:
        return "1"
    if event_count == 2:
        return "2"
    if event_count == 3:
        return "3"
    if event_count <= 5:
        return "4-5"
    return "6+"


def generate_figure_c(
    request_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> list[FigureResult]:
    out: list[FigureResult] = []
    base_cols = [
        "scope",
        "dataset",
        "decoder",
        "request_parse_ok",
        "response_parse_ok",
        "request_event_count",
        "flip_count",
        "nonempty_flip",
    ]
    title_base = "Sparsity Sensitivity Curve"
    table_name = "figure_C_sparsity_buckets.csv"
    if not set(base_cols).issubset(set(request_df.columns)):
        out.append(FigureResult("C", title_base, "figure_C_sparsity_sensitivity", table_name, "skipped", "missing columns", ""))
        return out

    df = request_df[base_cols].copy()
    df = df[(df["request_parse_ok"] == 1) & (df["response_parse_ok"] == 1)].copy()
    if df.empty:
        out.append(FigureResult("C", title_base, "figure_C_sparsity_sensitivity", table_name, "skipped", "no valid rows", ""))
        return out

    df["event_bucket"] = df["request_event_count"].astype(int).map(_sparsity_bucket)
    bucket_order = ["0", "1", "2", "3", "4-5", "6+"]
    grouped = (
        df.groupby(["scope", "decoder", "event_bucket"], as_index=False)
        .agg(
            sample_count=("request_event_count", "size"),
            avg_request_events=("request_event_count", "mean"),
            avg_flip_count=("flip_count", "mean"),
            nonempty_flip_rate=("nonempty_flip", "mean"),
        )
        .sort_values(["scope", "decoder", "event_bucket"])
    )
    grouped["event_bucket"] = pd.Categorical(grouped["event_bucket"], categories=bucket_order, ordered=True)
    grouped = grouped.sort_values(["scope", "decoder", "event_bucket"]).reset_index(drop=True)
    _table_write(grouped, tables_dir / table_name)

    metric_specs = [
        ("avg_flip_count", "Avg flip count", "figure_C1_sparsity_sensitivity_avg_flip"),
        ("nonempty_flip_rate", "Nonempty flip rate", "figure_C2_sparsity_sensitivity_nonempty_flip"),
    ]

    for metric_key, y_label, fig_base in metric_specs:
        if save_figures:
            import matplotlib.pyplot as plt  # type: ignore

            scopes = _scope_panels(grouped)
            fig, axes = plt.subplots(1, len(scopes), figsize=(5.9 * len(scopes), 4.6), sharey=False)
            if len(scopes) == 1:
                axes = [axes]
            for ax, scope in zip(axes, scopes):
                scope_df = grouped[grouped["scope"] == scope].copy()
                ax.set_title(scope_label(scope))
                ax.set_xlabel("Request-event sparsity bucket")
                ax.set_ylabel(y_label)
                ax.set_xticks(range(len(bucket_order)))
                ax.set_xticklabels(bucket_order)
                for decoder in sorted(scope_df["decoder"].astype(str).unique(), key=_decoder_sort_key):
                    dec_df = scope_df[scope_df["decoder"] == decoder].copy()
                    if dec_df.empty:
                        continue
                    x = [bucket_order.index(str(b)) for b in dec_df["event_bucket"].astype(str)]
                    y = dec_df[metric_key].astype(float).to_list()
                    ax.plot(
                        x,
                        y,
                        label=decoder_label(decoder),
                        color=_color_for_decoder(decoder),
                        marker="o",
                        linewidth=2.0,
                        markersize=5.0,
                    )
                ax.grid(axis="y", alpha=0.28)
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(
                handles=handles,
                labels=labels,
                title="Decoder",
                frameon=False,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.93),
                ncol=min(4, len(labels)),
            )
            fig.suptitle(f"{title_base}: {y_label}", y=0.99)
            fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.88))
            _save_figure(fig, figures_dir / fig_base, export_svg=export_svg)
            plt.close(fig)

        summary = grouped.groupby("decoder", as_index=False)[metric_key].mean()
        top_decoder = str(summary.sort_values(metric_key, ascending=(metric_key != "avg_flip_count")).iloc[0]["decoder"])
        result = (
            f"{y_label} changes with sparsity bucket; {decoder_label(top_decoder)} sets the leading average trend in this metric."
        )
        caption = (
            f"Sparsity-sensitivity curve ({y_label}). Requests are bucketed by event-count sparsity and decoder response behavior is "
            "tracked per bucket to expose regime-dependent separability."
        )
        out.append(FigureResult("C", f"{title_base}: {y_label}", fig_base, table_name, "ok", result, caption))
    return out


def generate_figure_d(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Engine-Swap Consistency Panel"
    figure_base = "figure_D_engine_swap_consistency"
    table_name = "figure_D_engine_swap_consistency.csv"
    cols = ["scope", "dataset", "decoder", "request_lines", "warning_no_syndrome_rate", "avg_flip_count", "residual_nonzero_rate"]
    if not set(cols).issubset(set(merged_df.columns)):
        return FigureResult("D", title, figure_base, table_name, "skipped", "missing columns", "")

    df = merged_df[cols].copy()
    df = df[np.isfinite(df["request_lines"]) & np.isfinite(df["avg_flip_count"])].copy()
    if df.empty:
        return FigureResult("D", title, figure_base, table_name, "skipped", "no valid rows", "")

    # Select representative datasets: prioritize real slice, then fixture, then synthetic.
    group = df.groupby(["scope", "dataset"], as_index=False)["request_lines"].mean()
    priority = {"real_slice": 0, "fixture": 1, "synthetic_holdout": 2, "real_full_hpc": 3}
    group["priority"] = group["scope"].map(lambda s: priority.get(str(s), 99))
    group = group.sort_values(["priority", "request_lines"], ascending=[True, False])
    selected = group.head(2)[["scope", "dataset"]]
    sel = df.merge(selected, on=["scope", "dataset"], how="inner").copy()
    if sel.empty:
        return FigureResult("D", title, figure_base, table_name, "skipped", "no representative datasets", "")

    metrics = ["request_lines", "warning_no_syndrome_rate", "avg_flip_count", "residual_nonzero_rate"]
    table_rows: list[dict[str, Any]] = []
    for (scope, dataset), dfg in sel.groupby(["scope", "dataset"]):
        for metric in metrics:
            vals = pd.to_numeric(dfg[metric], errors="coerce")
            max_val = float(vals.max()) if vals.notna().any() else 1.0
            denom = max(max_val, 1e-12)
            for _, row in dfg.iterrows():
                table_rows.append(
                    {
                        "scope": scope,
                        "dataset": dataset,
                        "decoder": row["decoder"],
                        "metric": metric,
                        "value": float(row[metric]),
                        "value_normalized": float(row[metric]) / denom,
                    }
                )
    panel_df = pd.DataFrame(table_rows)
    _table_write(panel_df, tables_dir / table_name)

    dataset_pairs = list(panel_df[["scope", "dataset"]].drop_duplicates().itertuples(index=False, name=None))

    if save_figures:
        import matplotlib.pyplot as plt  # type: ignore

        decoders = sorted(panel_df["decoder"].astype(str).unique(), key=_decoder_sort_key)
        metric_labels = {
            "request_lines": "request lines",
            "warning_no_syndrome_rate": "warning rate",
            "avg_flip_count": "avg flip count",
            "residual_nonzero_rate": "residual rate",
        }
        fig, axes = plt.subplots(1, len(dataset_pairs), figsize=(6.1 * len(dataset_pairs), 5.0), sharey=True)
        if len(dataset_pairs) == 1:
            axes = [axes]
        x = np.arange(len(metrics), dtype=float)
        width = 0.18
        for ax, (scope, dataset) in zip(axes, dataset_pairs):
            subset = panel_df[(panel_df["scope"] == scope) & (panel_df["dataset"] == dataset)]
            for idx, decoder in enumerate(decoders):
                ds = subset[subset["decoder"] == decoder]
                ys = [
                    float(ds[ds["metric"] == metric]["value_normalized"].iloc[0]) if not ds[ds["metric"] == metric].empty else 0.0
                    for metric in metrics
                ]
                ax.bar(
                    x + (idx - (len(decoders) - 1) / 2.0) * width,
                    ys,
                    width=width,
                    color=_color_for_decoder(decoder),
                    alpha=0.88,
                    label=decoder_label(decoder),
                )
            ax.set_title(f"{scope_label(scope)}: {_dataset_code(dataset)}")
            ax.set_xticks(x)
            ax.set_xticklabels([metric_labels[m] for m in metrics], rotation=20, ha="right")
            ax.set_ylim(0.0, 1.05)
            ax.set_ylabel("Within-metric normalized value")
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(
            handles=handles,
            labels=labels,
            frameon=False,
            ncol=min(4, len(labels)),
            loc="upper center",
            bbox_to_anchor=(0.5, 0.93),
        )
        fig.suptitle(title, y=0.99)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.88))
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    spread_req = panel_df[panel_df["metric"] == "request_lines"].groupby(["scope", "dataset"])["value"].agg(lambda s: s.max() - s.min())
    spread_warn = panel_df[panel_df["metric"] == "warning_no_syndrome_rate"].groupby(["scope", "dataset"])["value"].agg(
        lambda s: s.max() - s.min()
    )
    main_result = (
        f"Request and warning metrics stay decoder-invariant (max spread request_lines={float(spread_req.max()):.3g}, "
        f"warning_rate={float(spread_warn.max()):.6f}) while correction-volume/residual metrics diverge."
    )
    code_map = _dataset_code_map_text(sorted({str(d) for _, d in dataset_pairs}))
    caption = (
        "Engine-swap consistency panel on matched request streams. Invariant contract metrics (request count and warning rate) remain fixed "
        "across decoders, while correction intervention and residual outcomes change with decoder policy. "
        f"Panel dataset codes: {code_map}."
    )
    return FigureResult("D", title, figure_base, table_name, "ok", main_result, caption)


def generate_figure_f(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Provider Comparison Heatmap"
    figure_base = "figure_F_provider_comparison_heatmap"
    table_name = "figure_F_provider_comparison_heatmap.csv"
    needed = [
        "scope",
        "dataset",
        "provider",
        "decoder",
        "warning_no_syndrome_rate",
        "avg_request_events",
        "nonempty_request_event_rate",
        "avg_flip_count",
        "residual_nonzero_rate",
    ]
    if not set(needed).issubset(set(merged_df.columns)):
        return FigureResult("F", title, figure_base, table_name, "skipped", "missing columns", "")
    df = merged_df[needed].copy()
    if df.empty:
        return FigureResult("F", title, figure_base, table_name, "skipped", "no rows", "")

    base = (
        df.groupby(["scope", "dataset", "provider"], as_index=False)[
            ["warning_no_syndrome_rate", "avg_request_events", "nonempty_request_event_rate", "residual_nonzero_rate"]
        ]
        .mean()
        .rename(columns={"residual_nonzero_rate": "residual_nonzero_rate_mean"})
    )
    piv = (
        df.pivot_table(
            index=["scope", "dataset", "provider"],
            columns="decoder",
            values="avg_flip_count",
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for decoder in sorted(df["decoder"].astype(str).unique(), key=_decoder_sort_key):
        col = f"avg_flip_{decoder}"
        if decoder in piv.columns:
            piv = piv.rename(columns={decoder: col})
        else:
            piv[col] = np.nan
    heat = base.merge(piv, on=["scope", "dataset", "provider"], how="left")
    heat["row_label"] = heat.apply(lambda r: f"{scope_label(str(r['scope']))} | {pretty_dataset(str(r['dataset']))}", axis=1)
    heat = heat.sort_values(["scope", "provider", "dataset"]).reset_index(drop=True)
    _table_write(heat, tables_dir / table_name)

    metric_cols = ["warning_no_syndrome_rate", "avg_request_events", "nonempty_request_event_rate", "residual_nonzero_rate_mean"] + [
        c for c in heat.columns if c.startswith("avg_flip_")
    ]
    raw = heat[metric_cols].astype(float)
    norm = raw.copy()
    for col in metric_cols:
        col_min = float(np.nanmin(norm[col].to_numpy(dtype=float))) if norm[col].notna().any() else 0.0
        col_max = float(np.nanmax(norm[col].to_numpy(dtype=float))) if norm[col].notna().any() else 1.0
        if abs(col_max - col_min) < 1e-12:
            norm[col] = 0.5
        else:
            norm[col] = (norm[col] - col_min) / (col_max - col_min)

    if save_figures:
        import matplotlib.pyplot as plt  # type: ignore

        fig, ax = plt.subplots(figsize=(1.55 * len(metric_cols) + 3.0, max(3.8, 0.56 * len(heat) + 2.0)))
        mat = norm.to_numpy(dtype=float)
        im = ax.imshow(mat, aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=1.0)
        ax.set_title(title)
        ax.set_xticks(np.arange(len(metric_cols)))
        ax.set_xticklabels(metric_cols, rotation=28, ha="right")
        ax.set_yticks(np.arange(len(heat)))
        ax.set_yticklabels(heat["row_label"].tolist())
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                val = raw.iloc[i, j]
                text = f"{val:.3f}" if np.isfinite(val) else "NA"
                color = "white" if mat[i, j] > 0.60 else "black"
                ax.text(j, i, text, ha="center", va="center", fontsize=7.4, color=color)
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.ax.set_ylabel("Column-normalized intensity", rotation=270, labelpad=12)
        fig.tight_layout()
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    main_result = (
        "A single normalized grammar captures provider-level sparsity/warning structure and decoder-specific flip behavior, "
        "supporting extensible multi-provider benchmarking."
    )
    caption = (
        "Provider comparison heatmap with normalized columns and raw-value annotations. Rows are dataset/provider slices, "
        "columns combine input-structure metrics with decoder-specific intervention burden."
    )
    return FigureResult("F", title, figure_base, table_name, "ok", main_result, caption)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    vals = pd.to_numeric(values, errors="coerce")
    wts = pd.to_numeric(weights, errors="coerce")
    mask = vals.notna() & wts.notna()
    if not mask.any():
        return float("nan")
    v = vals[mask].to_numpy(dtype=float)
    w = wts[mask].to_numpy(dtype=float)
    if np.sum(w) <= 0.0:
        return float(np.mean(v))
    return float(np.average(v, weights=w))


def generate_figure_g(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Decoder Signature Parallel Coordinates"
    figure_base = "figure_G_decoder_signature_parallel"
    table_name = "figure_G_decoder_signature_parallel.csv"
    metrics_cols = [
        "avg_flip_count",
        "nonempty_flip_rate",
        "residual_nonzero_rate",
        "syndrome_satisfied_rate",
        "unique_flip_qubits",
        "warning_invariance_score",
        "decoder_stability_score",
    ]
    need = ["decoder", "request_lines"] + metrics_cols
    if not set(need).issubset(set(merged_df.columns)):
        return FigureResult("G", title, figure_base, table_name, "skipped", "missing columns", "")

    rows: list[dict[str, Any]] = []
    for decoder, group in merged_df.groupby("decoder"):
        row: dict[str, Any] = {"decoder": decoder, "decoder_label": decoder_label(str(decoder))}
        for metric in metrics_cols:
            row[metric] = _weighted_mean(group[metric], group["request_lines"])
        rows.append(row)
    sig = pd.DataFrame(rows).sort_values("decoder", key=lambda s: s.map(lambda v: _decoder_sort_key(str(v))))
    if sig.empty:
        return FigureResult("G", title, figure_base, table_name, "skipped", "no decoder rows", "")

    # Normalize per metric for parallel coordinates.
    norm = sig.copy()
    for metric in metrics_cols:
        col = pd.to_numeric(norm[metric], errors="coerce")
        cmin = float(np.nanmin(col.to_numpy(dtype=float))) if col.notna().any() else 0.0
        cmax = float(np.nanmax(col.to_numpy(dtype=float))) if col.notna().any() else 1.0
        if abs(cmax - cmin) < 1e-12:
            norm[metric] = 0.5
        else:
            norm[metric] = (col - cmin) / (cmax - cmin)
    out_table = sig.copy()
    for metric in metrics_cols:
        out_table[f"{metric}_norm"] = norm[metric]
    _table_write(out_table, tables_dir / table_name)

    if save_figures:
        import matplotlib.pyplot as plt  # type: ignore

        x = np.arange(len(metrics_cols), dtype=float)
        fig, ax = plt.subplots(figsize=(12.5, 5.0))
        for _, row in norm.iterrows():
            decoder = str(row["decoder"])
            ys = [float(row[m]) for m in metrics_cols]
            ax.plot(
                x,
                ys,
                color=_color_for_decoder(decoder),
                linewidth=2.2,
                marker="o",
                markersize=5.3,
                label=decoder_label(decoder),
                alpha=0.9,
            )
            ax.text(x[-1] + 0.06, ys[-1], decoder_label(decoder), color=_color_for_decoder(decoder), fontsize=8.3, va="center")
        ax.set_xlim(x[0] - 0.2, x[-1] + 1.0)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics_cols, rotation=28, ha="right")
        ax.set_ylabel("Normalized metric value")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    low_flip = str(sig.sort_values("avg_flip_count").iloc[0]["decoder"])
    high_sat = str(sig.sort_values("syndrome_satisfied_rate", ascending=False).iloc[0]["decoder"])
    main_result = (
        f"Decoder signatures separate consistently across metrics: lowest intervention={decoder_label(low_flip)}, "
        f"highest satisfaction={decoder_label(high_sat)}."
    )
    caption = (
        "Decoder signature parallel-coordinates plot over intervention, residual, satisfaction, support, warning-invariance, "
        "and stability metrics. Values are normalized for compact cross-metric comparison."
    )
    return FigureResult("G", title, figure_base, table_name, "ok", main_result, caption)


def generate_figure_h(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Control-Ablation Comparison (Real vs Synthetic)"
    figure_base = "figure_H_control_ablation_comparison"
    table_name = "figure_H_control_ablation_comparison.csv"
    need = ["scope", "dataset", "provider", "decoder", "avg_flip_count", "correction_efficiency_index"]
    if not set(need).issubset(set(merged_df.columns)):
        return FigureResult("H", title, figure_base, table_name, "skipped", "missing columns", "")

    real_df = merged_df[merged_df["scope"] == "real_slice"].copy()
    synth_df = merged_df[merged_df["scope"] == "synthetic_holdout"].copy()
    if real_df.empty or synth_df.empty:
        return FigureResult("H", title, figure_base, table_name, "skipped", "real or synthetic scope missing", "")

    real_core = real_df[["provider", "decoder", "avg_flip_count", "correction_efficiency_index"]].rename(
        columns={
            "avg_flip_count": "real_avg_flip_count",
            "correction_efficiency_index": "real_correction_efficiency_index",
        }
    )
    synth_core = synth_df[["provider", "decoder", "avg_flip_count", "correction_efficiency_index"]].rename(
        columns={
            "avg_flip_count": "synthetic_avg_flip_count",
            "correction_efficiency_index": "synthetic_correction_efficiency_index",
        }
    )
    paired = real_core.merge(synth_core, on=["provider", "decoder"], how="inner")
    if paired.empty:
        return FigureResult("H", title, figure_base, table_name, "skipped", "no provider-matched real/synthetic pairs", "")

    _table_write(paired, tables_dir / table_name)

    if save_figures:
        import matplotlib.pyplot as plt  # type: ignore

        fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), sharex=True)
        metric_specs = [
            ("avg_flip_count", "Average flip count"),
            ("correction_efficiency_index", "Correction efficiency index"),
        ]
        x = np.array([0.0, 1.0], dtype=float)
        for ax, (metric, label) in zip(axes, metric_specs):
            for _, row in paired.iterrows():
                provider = str(row["provider"])
                decoder = str(row["decoder"])
                y0 = float(row[f"real_{metric}"])
                y1 = float(row[f"synthetic_{metric}"])
                ax.plot(
                    x,
                    [y0, y1],
                    color=_color_for_decoder(decoder),
                    linestyle=_line_for_provider(provider),
                    linewidth=2.0,
                    marker=_marker_for_provider(provider),
                    markersize=5.6,
                    alpha=0.9,
                )
            ax.set_xticks(x)
            ax.set_xticklabels(["real slice", "synthetic heldout"])
            ax.set_ylabel(label)
            ax.set_title(label)
            ax.grid(axis="y", alpha=0.28)

        # Decoder legend only (style legend omitted to reduce clutter).
        import matplotlib.lines as mlines  # type: ignore

        handles = [
            mlines.Line2D([], [], color=_color_for_decoder(dec), marker="o", linewidth=2.0, label=decoder_label(dec))
            for dec in sorted(paired["decoder"].astype(str).unique(), key=_decoder_sort_key)
        ]
        axes[0].legend(handles=handles, title="Decoder", frameon=False, loc="upper left")
        fig.suptitle(title, y=1.02)
        fig.tight_layout()
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    rank_changes = 0
    for provider, group in paired.groupby("provider"):
        real_rank = group.sort_values("real_avg_flip_count")["decoder"].tolist()
        synth_rank = group.sort_values("synthetic_avg_flip_count")["decoder"].tolist()
        if real_rank != synth_rank:
            rank_changes += 1
    main_result = (
        f"Control-ablation pairing reveals how decoder rankings transfer from real slices to sparsity-matched synthetic controls "
        f"(provider groups with rank shifts: {rank_changes})."
    )
    caption = (
        "Side-by-side control-ablation slopes comparing real photonic slices with sparsity-matched synthetic heldout controls under "
        "identical decoder definitions. Persistence or shifts in ranking support causal interpretability claims."
    )
    return FigureResult("H", title, figure_base, table_name, "ok", main_result, caption)


def generate_figure_i(
    merged_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> FigureResult:
    title = "Hardware-to-Decoder Workflow Flowchart"
    figure_base = "figure_I_workflow_flowchart"
    table_name = "figure_I_workflow_flowchart.csv"

    provider_count = int(merged_df["provider"].nunique()) if "provider" in merged_df.columns else 0
    dataset_count = int(merged_df["dataset"].nunique()) if "dataset" in merged_df.columns else 0
    decoder_count = int(merged_df["decoder"].nunique()) if "decoder" in merged_df.columns else 0

    nodes = [
        {
            "record_type": "node",
            "id": "providers",
            "label": f"Provider-native records\n{provider_count} providers, {dataset_count} datasets",
            "group": "input",
            "x": 0.05,
            "y": 0.63,
            "w": 0.20,
            "h": 0.22,
        },
        {
            "record_type": "node",
            "id": "normalize",
            "label": "Contract normalization\nschema checks + parse checks",
            "group": "transform",
            "x": 0.30,
            "y": 0.63,
            "w": 0.22,
            "h": 0.22,
        },
        {
            "record_type": "node",
            "id": "replay",
            "label": "Replay engine\nmatched request stream",
            "group": "engine",
            "x": 0.57,
            "y": 0.63,
            "w": 0.18,
            "h": 0.22,
        },
        {
            "record_type": "node",
            "id": "decoders",
            "label": "Decoder engines",
            "group": "decoder",
            "x": 0.79,
            "y": 0.57,
            "w": 0.17,
            "h": 0.31,
        },
        {
            "record_type": "node",
            "id": "metrics",
            "label": "Metrics layer\nintegrity, sparsity, residual, intervention",
            "group": "metrics",
            "x": 0.30,
            "y": 0.24,
            "w": 0.25,
            "h": 0.22,
        },
        {
            "record_type": "node",
            "id": "figures",
            "label": "Journal figure pack\nA/B/C/D/F (+G/H/I)",
            "group": "figures",
            "x": 0.60,
            "y": 0.24,
            "w": 0.20,
            "h": 0.22,
        },
        {
            "record_type": "node",
            "id": "future",
            "label": "Extensible benchmarking\nnew providers, same contract",
            "group": "future",
            "x": 0.83,
            "y": 0.24,
            "w": 0.15,
            "h": 0.22,
        },
    ]
    edges = [
        {"record_type": "edge", "source": "providers", "target": "normalize", "label": "provider adapters"},
        {"record_type": "edge", "source": "normalize", "target": "replay", "label": "normalized IO"},
        {"record_type": "edge", "source": "replay", "target": "decoders", "label": "same request stream"},
        {"record_type": "edge", "source": "decoders", "target": "metrics", "label": "decoded responses"},
        {"record_type": "edge", "source": "metrics", "target": "figures", "label": "derived tables"},
        {"record_type": "edge", "source": "figures", "target": "future", "label": "reusable pipeline"},
    ]
    table_df = pd.concat([pd.DataFrame(nodes), pd.DataFrame(edges)], ignore_index=True, sort=False)
    _table_write(table_df, tables_dir / table_name)

    if save_figures:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.patches import FancyBboxPatch  # type: ignore

        fig, ax = plt.subplots(figsize=(13.2, 6.8))
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.axis("off")

        palette = {
            "input": {"face": "#E3F0FF", "edge": "#3B78B4"},
            "transform": {"face": "#DFF6F0", "edge": "#2A8F78"},
            "engine": {"face": "#E8F3E0", "edge": "#4F8C36"},
            "decoder": {"face": "#FFF0D9", "edge": "#C17B1D"},
            "metrics": {"face": "#FCEAEA", "edge": "#BD4D4D"},
            "figures": {"face": "#EFE9FF", "edge": "#6F56B8"},
            "future": {"face": "#FFF8D8", "edge": "#B18A16"},
        }

        node_map = {str(n["id"]): n for n in nodes}

        def draw_node(node: dict[str, Any]) -> None:
            style = palette.get(str(node["group"]), {"face": "#F4F4F4", "edge": "#4A4A4A"})
            rect = FancyBboxPatch(
                (float(node["x"]), float(node["y"])),
                float(node["w"]),
                float(node["h"]),
                boxstyle="round,pad=0.012,rounding_size=0.02",
                linewidth=1.8,
                edgecolor=style["edge"],
                facecolor=style["face"],
                alpha=0.98,
            )
            ax.add_patch(rect)
            if str(node["id"]) == "decoders":
                cx = float(node["x"]) + float(node["w"]) / 2.0
                top = float(node["y"]) + float(node["h"])
                ax.text(
                    cx,
                    top - 0.045,
                    "Decoder engines",
                    ha="center",
                    va="center",
                    fontsize=10.0,
                    color="#1C1C1C",
                    fontweight="semibold",
                )
                ax.text(
                    cx,
                    top - 0.075,
                    f"{decoder_count} swappable policies",
                    ha="center",
                    va="center",
                    fontsize=9.1,
                    color="#2D2D2D",
                )
            else:
                ax.text(
                    float(node["x"]) + float(node["w"]) / 2.0,
                    float(node["y"]) + float(node["h"]) / 2.0,
                    str(node["label"]),
                    ha="center",
                    va="center",
                    fontsize=10.0,
                    color="#1C1C1C",
                    linespacing=1.25,
                    fontweight="semibold",
                )

        for node in nodes:
            draw_node(node)

        decoder_box = node_map["decoders"]
        mini_h = 0.037
        mini_y0 = float(decoder_box["y"]) + 0.02
        mini_x = float(decoder_box["x"]) + 0.02
        mini_w = float(decoder_box["w"]) - 0.04
        mini_labels = ["MWPM", "UF", "BP", "Neural-MWPM"]
        mini_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        for i, (txt, clr) in enumerate(zip(mini_labels, mini_colors)):
            y = mini_y0 + i * (mini_h + 0.010)
            r = FancyBboxPatch(
                (mini_x, y),
                mini_w,
                mini_h,
                boxstyle="round,pad=0.01,rounding_size=0.012",
                linewidth=1.2,
                edgecolor=clr,
                facecolor="white",
                alpha=0.97,
            )
            ax.add_patch(r)
            ax.text(mini_x + mini_w / 2.0, y + mini_h / 2.0, txt, ha="center", va="center", fontsize=8.9, color="#202020")

        def right_center(node: dict[str, Any]) -> tuple[float, float]:
            return float(node["x"]) + float(node["w"]), float(node["y"]) + float(node["h"]) / 2.0

        def left_center(node: dict[str, Any]) -> tuple[float, float]:
            return float(node["x"]), float(node["y"]) + float(node["h"]) / 2.0

        def bottom_center(node: dict[str, Any]) -> tuple[float, float]:
            return float(node["x"]) + float(node["w"]) / 2.0, float(node["y"])

        def top_center(node: dict[str, Any]) -> tuple[float, float]:
            return float(node["x"]) + float(node["w"]) / 2.0, float(node["y"]) + float(node["h"])

        edge_points = {
            ("providers", "normalize"): (right_center(node_map["providers"]), left_center(node_map["normalize"])),
            ("normalize", "replay"): (right_center(node_map["normalize"]), left_center(node_map["replay"])),
            ("replay", "decoders"): (right_center(node_map["replay"]), left_center(node_map["decoders"])),
            ("decoders", "metrics"): (bottom_center(node_map["decoders"]), top_center(node_map["metrics"])),
            ("metrics", "figures"): (right_center(node_map["metrics"]), left_center(node_map["figures"])),
            ("figures", "future"): (right_center(node_map["figures"]), left_center(node_map["future"])),
        }

        for e in edges:
            src = str(e["source"])
            dst = str(e["target"])
            start, end = edge_points[(src, dst)]
            ax.annotate(
                "",
                xy=end,
                xytext=start,
                arrowprops={
                    "arrowstyle": "-|>",
                    "lw": 1.9,
                    "color": "#4A4A4A",
                    "shrinkA": 8,
                    "shrinkB": 8,
                    "mutation_scale": 14,
                },
            )
            lx = (start[0] + end[0]) / 2.0
            ly = (start[1] + end[1]) / 2.0
            if (src, dst) == ("decoders", "metrics"):
                lx -= 0.11
                ly -= 0.02
            ax.text(
                lx,
                ly + 0.028,
                str(e["label"]),
                fontsize=8.2,
                color="#333333",
                ha="center",
                va="center",
                bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.92},
            )

        ax.text(0.03, 0.95, "LiDMaS+ Hardware-to-Decoder Workflow", fontsize=15.2, fontweight="bold", color="#1A1A1A")
        ax.text(
            0.03,
            0.905,
            "Stable interface contract, engine-style decoder swapping, and extensible provider benchmarking",
            fontsize=10.2,
            color="#3A3A3A",
        )
        ax.text(
            0.03,
            0.07,
            "Invariant checks: request count, parse consistency, warning-rate invariance under matched inputs",
            fontsize=8.6,
            color="#4B4B4B",
        )
        ax.text(
            0.03,
            0.04,
            "Decoder-sensitive checks: intervention volume, syndrome satisfaction, residual burden, sparsity response",
            fontsize=8.6,
            color="#4B4B4B",
        )

        fig.tight_layout()
        _save_figure(fig, figures_dir / figure_base, export_svg=export_svg)
        plt.close(fig)

    main_result = (
        "Flowchart maps the full hardware-to-decoder pathway from provider-native records to reusable figure generation "
        "with fixed-contract replay and swappable decoder policies."
    )
    caption = (
        "Workflow flowchart for LiDMaS+ hardware-to-decoder evaluation: provider-native records are normalized to a fixed decoder IO contract, "
        "replayed through swappable decoder engines, aggregated into diagnostic metrics, and rendered into a reproducible figure pack."
    )
    return FigureResult("I", title, figure_base, table_name, "ok", main_result, caption)
