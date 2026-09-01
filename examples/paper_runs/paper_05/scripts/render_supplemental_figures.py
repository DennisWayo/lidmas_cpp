#!/usr/bin/env python3
"""Render candidate supplemental figures for paper_05."""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from paper05_plot_style import (
    CONTAINS_COLOR,
    EXACT_COLOR,
    GKP_COLOR,
    HEATMAP_CMAP,
    IBM_COLOR,
    LOCAL_COLOR,
    apply_journal_style,
    save_journal_figure,
    style_bar_axis,
    style_heatmap_axis,
    style_rate_axis,
)


DECODER_ORDER = ["mwpm", "uf", "bp"]
DECODER_LABELS = {"mwpm": "MWPM", "uf": "UF", "bp": "BP"}


def add_panel_label(ax: Any, label: str, *, y: float = -0.23) -> None:
    ax.text(
        0.5,
        y,
        label,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.1,
        color="#111827",
        clip_on=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dir", default=".")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manuscript-dir")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fobj:
        return list(csv.DictReader(fobj))


def f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def parse_indices(value: str) -> list[int]:
    if not value.strip():
        return []
    return [int(part) for part in value.split() if part.strip()]


def target_sort(value: str) -> int:
    return int(value)


def select_injected(rows: list[dict[str, str]], *, dataset: str, decoder: str, target_field: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("dataset") == dataset and row.get("decoder") == decoder and row.get(target_field, "") != ""
    ]


def correction_inclusion_matrix(
    rows: list[dict[str, str]], *, dataset: str, decoder: str, target_field: str, n_data: int
) -> tuple[list[int], np.ndarray]:
    selected = select_injected(rows, dataset=dataset, decoder=decoder, target_field=target_field)
    targets = sorted({target_sort(row[target_field]) for row in selected})
    grouped: dict[int, list[dict[str, str]]] = collections.defaultdict(list)
    for row in selected:
        grouped[target_sort(row[target_field])].append(row)

    matrix = np.zeros((len(targets), n_data), dtype=float)
    for ridx, target in enumerate(targets):
        group = grouped[target]
        if not group:
            continue
        for row in group:
            for index in parse_indices(row.get("correction_indices", "")):
                if 0 <= index < n_data:
                    matrix[ridx, index] += 1.0
        matrix[ridx, :] /= float(len(group))
    return targets, matrix


def plot_correction_confusion(
    surface_rows: list[dict[str, str]], gkp_rows: list[dict[str, str]], out_dir: Path, manuscript_dir: Path | None
) -> None:
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.patches import Rectangle  # type: ignore

    surface_targets, surface_mat = correction_inclusion_matrix(
        surface_rows, dataset="ibm_ibm_fez", decoder="mwpm", target_field="injected_x", n_data=40
    )
    gkp_targets, gkp_mat = correction_inclusion_matrix(
        gkp_rows, dataset="digitized_gkp_pennylane", decoder="mwpm", target_field="injected_q", n_data=40
    )

    fig, axes = plt.subplots(2, 1, figsize=(6.45, 4.9), constrained_layout=True, sharex=True)
    panels = [
        (axes[0], surface_mat, surface_targets, "Surface IBM MWPM", "X"),
        (axes[1], gkp_mat, gkp_targets, "Digitized-GKP MWPM", "q"),
    ]
    im = None
    for ax, matrix, targets, title, prefix in panels:
        im = ax.imshow(matrix, aspect="auto", cmap=HEATMAP_CMAP, vmin=0.0, vmax=0.7, interpolation="nearest")
        ax.set_yticks(np.arange(len(targets)))
        ax.set_yticklabels([f"{prefix}{target}" for target in targets])
        ax.set_ylabel("intended target")
        for ridx, target in enumerate(targets):
            ax.add_patch(Rectangle((target - 0.5, ridx - 0.5), 1.0, 1.0, fill=False, edgecolor="white", linewidth=1.1))
        style_heatmap_axis(ax)
    add_panel_label(axes[0], "(a) Surface IBM MWPM", y=-0.14)
    add_panel_label(axes[1], "(b) Digitized-GKP MWPM", y=-0.18)
    axes[-1].set_xlabel("decoded correction data index")
    ticks = list(range(0, 40, 5)) + [39]
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels([str(tick) for tick in ticks])
    if im is not None:
        cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
        cbar.set_label("inclusion rate")
    save_journal_figure(fig, out_dir / "figure_correction_confusion_surface_gkp", manuscript_dir)
    plt.close(fig)


def plot_surface_weight_distribution(rows: list[dict[str, str]], out_dir: Path, manuscript_dir: Path | None) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    selected = [
        row
        for row in rows
        if row.get("decoder") == "mwpm" and row.get("injected_x", "") != "" and row.get("dataset") in {"ibm_ibm_fez", "local_simulator"}
    ]
    weights_by_dataset: dict[str, list[int]] = collections.defaultdict(list)
    for row in selected:
        weights_by_dataset[row["dataset"]].append(int(f(row.get("correction_weight", "0"))))
    max_weight = max(max(values) for values in weights_by_dataset.values() if values)
    x = np.arange(max_weight + 1)
    width = 0.38

    fig, ax = plt.subplots(figsize=(3.75, 2.65), constrained_layout=True)
    for offset, (dataset, color, label) in zip(
        [-width / 2.0, width / 2.0],
        [("ibm_ibm_fez", EXACT_COLOR, "IBM fez"), ("local_simulator", GKP_COLOR, "local")],
    ):
        values = weights_by_dataset[dataset]
        counts = collections.Counter(values)
        rates = np.asarray([counts.get(int(weight), 0) / max(1, len(values)) for weight in x], dtype=float)
        ax.bar(x + offset, rates, width=width, color=color, label=label)
        mean_value = float(np.mean(values))
        ax.axvline(mean_value, color=color, linestyle=(0, (3, 2)), linewidth=1.0)
    ax.set_xlabel("MWPM correction weight")
    ax.set_ylabel("shot fraction")
    ax.set_xticks(x)
    style_bar_axis(ax)
    ax.legend(frameon=False, loc="upper right")
    save_journal_figure(fig, out_dir / "figure_surface_correction_weight_distribution", manuscript_dir)
    plt.close(fig)


def aggregate_policy_metrics(rows: list[dict[str, str]], *, dataset: str, target_field: str) -> dict[str, tuple[float, float, float]]:
    out: dict[str, tuple[float, float, float]] = {}
    for decoder in DECODER_ORDER:
        selected = select_injected(rows, dataset=dataset, decoder=decoder, target_field=target_field)
        if not selected:
            out[decoder] = (float("nan"), float("nan"), float("nan"))
            continue
        exact = float(np.mean([f(row.get("exact_intended_match", "0")) for row in selected]))
        contains = float(np.mean([f(row.get("contains_intended_target", "0")) for row in selected]))
        weight = float(np.mean([f(row.get("correction_weight", "0")) for row in selected]))
        out[decoder] = (exact, contains, weight)
    return out


def plot_decoder_policy_comparison(
    rep_rows: list[dict[str, str]],
    qldpc_rows: list[dict[str, str]],
    surface_rows: list[dict[str, str]],
    gkp_rows: list[dict[str, str]],
    out_dir: Path,
    manuscript_dir: Path | None,
) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    studies = [
        ("Rep.", aggregate_policy_metrics(rep_rows, dataset="ibm_ibm_fez", target_field="injected_x")),
        ("Steane", aggregate_policy_metrics(qldpc_rows, dataset="ibm_ibm_fez", target_field="injected_x")),
        ("Surface", aggregate_policy_metrics(surface_rows, dataset="ibm_ibm_fez", target_field="injected_x")),
        ("GKP", aggregate_policy_metrics(gkp_rows, dataset="digitized_gkp_pennylane", target_field="injected_q")),
    ]
    metric_specs = [
        ("exact", 0, "exact localization", (0.0, 1.02)),
        ("contains", 1, "target-containing", (0.0, 1.02)),
        ("weight", 2, "mean correction weight", None),
    ]
    colors = {"mwpm": EXACT_COLOR, "uf": CONTAINS_COLOR, "bp": LOCAL_COLOR}
    x = np.arange(len(studies))
    width = 0.23

    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.45), constrained_layout=False)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.82, bottom=0.28, wspace=0.55)
    for panel_index, (ax, (_name, metric_index, ylabel, ylim)) in enumerate(zip(axes, metric_specs)):
        for didx, decoder in enumerate(DECODER_ORDER):
            values = [metrics[decoder][metric_index] for _, metrics in studies]
            ax.bar(x + (didx - 1) * width, values, width=width, color=colors[decoder], label=DECODER_LABELS[decoder])
        ax.set_xticks(x)
        ax.set_xticklabels([name for name, _metrics in studies], rotation=25, ha="right")
        ax.set_ylabel(ylabel)
        style_bar_axis(ax)
        if ylim is not None:
            ax.set_ylim(*ylim)
        add_panel_label(ax, f"({chr(ord('a') + panel_index)}) {ylabel}", y=-0.34)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=3)
    save_journal_figure(fig, out_dir / "figure_decoder_policy_comparison", manuscript_dir)
    plt.close(fig)


def wrap_gkp_value(value: float, period: float) -> float:
    return (value + 0.5 * period) % period - 0.5 * period


def plot_gkp_binning(paper_dir: Path, out_dir: Path, manuscript_dir: Path | None) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    data = json.loads((paper_dir / "results/32_gkp_digitized_sampler/local_gkp_digitized_results.json").read_text(encoding="utf-8"))
    period = math.sqrt(math.pi)
    decision_width = float(data["decision_width"])
    clean_values: list[float] = []
    injected_support_values: list[float] = []
    injected_background_values: list[float] = []
    for experiment in data["experiments"]:
        expected = experiment["expected_syndrome"]
        for record in experiment["shot_records"]:
            wrapped = [wrap_gkp_value(float(value), period) for value in record["analog_z_values"]]
            if experiment["injected_q"] is None:
                clean_values.extend(wrapped)
            else:
                for idx, value in enumerate(wrapped):
                    if int(expected[idx]):
                        injected_support_values.append(value)
                    else:
                        injected_background_values.append(value)

    bins = np.linspace(-0.5 * period, 0.5 * period, 81)
    fig, ax = plt.subplots(figsize=(4.15, 2.75), constrained_layout=True)
    ax.hist(clean_values, bins=bins, density=True, histtype="stepfilled", alpha=0.32, color=IBM_COLOR, label="clean checks")
    ax.hist(
        injected_background_values,
        bins=bins,
        density=True,
        histtype="step",
        linewidth=1.35,
        color=LOCAL_COLOR,
        label="injected background checks",
    )
    ax.hist(
        injected_support_values,
        bins=bins,
        density=True,
        histtype="step",
        linewidth=1.55,
        color=GKP_COLOR,
        label="injected target-support checks",
    )
    for sign in (-1.0, 1.0):
        ax.axvline(sign * decision_width, color="#111827", linestyle=(0, (3, 2)), linewidth=1.0)
    ax.axvspan(-decision_width, decision_width, color="#F3F4F6", alpha=0.45, zorder=-1)
    ax.set_xlabel(r"wrapped check coordinate")
    ax.set_ylabel("density")
    style_bar_axis(ax)
    ax.legend(frameon=False, loc="upper left")
    save_journal_figure(fig, out_dir / "figure_gkp_wrapped_quadrature_binning", manuscript_dir)
    plt.close(fig)


def activation_rates(rows: list[dict[str, str]], *, dataset: str, circuit_id: str) -> np.ndarray:
    selected = [row for row in rows if row.get("decoder") == "mwpm" and row.get("dataset") == dataset and row.get("circuit_id") == circuit_id]
    if not selected:
        return np.asarray([], dtype=float)
    n_checks = len(selected[0]["measured_syndrome"])
    matrix = np.zeros((len(selected), n_checks), dtype=float)
    for ridx, row in enumerate(selected):
        matrix[ridx, :] = [int(bit) for bit in row["measured_syndrome"]]
    return np.mean(matrix, axis=0)


def stream_summaries(rows: list[dict[str, str]], *, dataset: str) -> tuple[list[str], np.ndarray, np.ndarray]:
    selected = [row for row in rows if row.get("decoder") == "mwpm" and row.get("dataset") == dataset]
    grouped: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in selected:
        grouped[row["circuit_id"]].append(row)

    def key(circuit_id: str) -> tuple[int, int]:
        if circuit_id == "clean":
            return (0, 0)
        return (1, int(circuit_id.removeprefix("x_data_")))

    labels: list[str] = []
    syndrome_weight: list[float] = []
    correction_weight: list[float] = []
    for circuit_id in sorted(grouped, key=key):
        group = grouped[circuit_id]
        labels.append("clean" if circuit_id == "clean" else "X" + circuit_id.removeprefix("x_data_"))
        syndrome_weight.append(float(np.mean([f(row["syndrome_weight"]) for row in group])))
        correction_weight.append(float(np.mean([f(row["correction_weight"]) for row in group])))
    return labels, np.asarray(syndrome_weight), np.asarray(correction_weight)


def plot_surface_empirical_noise_overlay(rows: list[dict[str, str]], out_dir: Path, manuscript_dir: Path | None) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    ibm_clean = activation_rates(rows, dataset="ibm_ibm_fez", circuit_id="clean")
    local_clean = activation_rates(rows, dataset="local_simulator", circuit_id="clean")
    labels, ibm_syndrome_weight, ibm_correction_weight = stream_summaries(rows, dataset="ibm_ibm_fez")
    local_labels, local_syndrome_weight, local_correction_weight = stream_summaries(rows, dataset="local_simulator")

    fig, axes = plt.subplots(2, 1, figsize=(5.2, 4.55), constrained_layout=False)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.97, bottom=0.18, hspace=0.58)
    x_checks = np.arange(len(ibm_clean))
    axes[0].bar(x_checks - 0.18, ibm_clean, width=0.36, color=EXACT_COLOR, label="IBM clean")
    axes[0].bar(x_checks + 0.18, local_clean, width=0.36, color=GKP_COLOR, label="local clean")
    axes[0].set_xticks(x_checks)
    axes[0].set_xticklabels([f"Z{i}" for i in x_checks])
    axes[0].set_ylabel("activation rate")
    style_bar_axis(axes[0])
    axes[0].legend(frameon=False, loc="upper right")

    axes[1].scatter(local_syndrome_weight, local_correction_weight, color=GKP_COLOR, marker="D", label="local")
    axes[1].scatter(ibm_syndrome_weight, ibm_correction_weight, color=EXACT_COLOR, marker="o", label="IBM")
    labels_to_mark = {"clean", "X5", "X10", "X17", "X37"}
    for label, sx, cy in zip(labels, ibm_syndrome_weight, ibm_correction_weight):
        if label in labels_to_mark:
            axes[1].annotate(label, (sx, cy), xytext=(4, 3), textcoords="offset points", fontsize=6.8, color="#374151")
    for label, sx, cy in zip(local_labels, local_syndrome_weight, local_correction_weight):
        if label == "clean":
            axes[1].annotate("local clean", (sx, cy), xytext=(3, 2), textcoords="offset points", fontsize=6.8, color="#374151")
    axes[1].set_xlabel("mean syndrome weight")
    axes[1].set_ylabel("mean correction weight")
    add_panel_label(axes[0], "(a) Clean background activation", y=-0.18)
    axes[1].xaxis.set_label_coords(0.5, -0.12)
    add_panel_label(axes[1], "(b) Syndrome vs correction burden", y=-0.34)
    axes[1].set_ylim(0.0, max(float(np.max(ibm_correction_weight)) + 0.4, 4.0))
    style_bar_axis(axes[1])
    axes[1].legend(frameon=False, loc="upper left")
    save_journal_figure(fig, out_dir / "figure_surface_empirical_noise_overlay", manuscript_dir)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    paper_dir = Path(args.paper_dir).resolve()
    out_dir = Path(args.out_dir)
    manuscript_dir = Path(args.manuscript_dir) if args.manuscript_dir else None
    out_dir.mkdir(parents=True, exist_ok=True)
    if manuscript_dir is not None:
        manuscript_dir.mkdir(parents=True, exist_ok=True)

    import matplotlib  # type: ignore

    matplotlib.use("Agg", force=True)
    apply_journal_style()

    rep_rows = read_csv_rows(paper_dir / "results/05_decode_live_syndromes/decoded_shots.csv")
    qldpc_rows = read_csv_rows(paper_dir / "results/15_decode_qldpc_syndromes/decoded_shots.csv")
    surface_rows = read_csv_rows(paper_dir / "results/25_decode_surface_syndromes/decoded_shots.csv")
    gkp_rows = read_csv_rows(paper_dir / "results/34_decode_gkp_syndromes/decoded_shots.csv")

    plot_correction_confusion(surface_rows, gkp_rows, out_dir, manuscript_dir)
    plot_surface_weight_distribution(surface_rows, out_dir, manuscript_dir)
    plot_decoder_policy_comparison(rep_rows, qldpc_rows, surface_rows, gkp_rows, out_dir, manuscript_dir)
    plot_gkp_binning(paper_dir, out_dir, manuscript_dir)
    plot_surface_empirical_noise_overlay(surface_rows, out_dir, manuscript_dir)
    print(f"Wrote paper_05 supplemental figures to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
