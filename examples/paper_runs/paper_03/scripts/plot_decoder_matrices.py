#!/usr/bin/env python3
"""Generate paper_03 figures from decoder matrix CSV summaries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


DECODER_ORDER = {"mwpm": 0, "uf": 1, "bp": 2, "neural_mwpm": 3, "stub": 4}
DECODER_LABELS = {
    "mwpm": "MWPM",
    "uf": "UF",
    "bp": "BP",
    "neural_mwpm": "Neural-MWPM",
    "stub": "Stub",
}
DECODER_STYLES = {
    "mwpm": {"color": "#1f77b4", "marker": "o", "linestyle": "-"},
    "uf": {"color": "#ff7f0e", "marker": "s", "linestyle": "--"},
    "bp": {"color": "#2ca02c", "marker": "^", "linestyle": "-."},
    "neural_mwpm": {"color": "#d62728", "marker": "D", "linestyle": ":"},
}
DATASET_LABELS = {
    "job": "Job",
    "aurora": "Aurora",
    "gkp": "GKP",
    "qca": "QCA",
    "aurora_batch0_qpu5": "Aurora batch0\nQPU5",
    "qca_fig3b": "QCA fig3b",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture-csv", required=True, help="Fixture matrix CSV")
    p.add_argument("--real-csv", required=True, help="Real-data matrix CSV")
    p.add_argument("--out-dir", required=True, help="Figure output directory")
    return p.parse_args()


def _decoder_order(name: str) -> tuple[int, str]:
    return (DECODER_ORDER.get(name, 999), name)


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _configure_matplotlib() -> None:
    import matplotlib as mpl  # type: ignore

    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )


def _pretty_dataset(dataset: str) -> str:
    if dataset in DATASET_LABELS:
        return DATASET_LABELS[dataset]
    return dataset.replace("_", " ")


def _dataset_order(rows: list[dict[str, str]]) -> list[str]:
    return _unique_in_order([r.get("dataset", "") for r in rows if r.get("dataset", "")])


def _decoder_ordered(rows: list[dict[str, str]]) -> list[str]:
    decoders = _unique_in_order([r.get("decoder", "") for r in rows if r.get("decoder", "")])
    return sorted(decoders, key=_decoder_order)


def _save_figure(fig: Any, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), dpi=240)
    fig.savefig(out_path.with_suffix(".pdf"))


def _metric_matrix(
    rows: list[dict[str, str]], metric_key: str
) -> tuple[list[str], list[str], list[list[float]]]:
    datasets = _dataset_order(rows)
    decoders = _decoder_ordered(rows)
    lookup: dict[tuple[str, str], float] = {}
    for row in rows:
        dataset = row.get("dataset", "")
        decoder = row.get("decoder", "")
        lookup[(dataset, decoder)] = _safe_float(row.get(metric_key))
    mat: list[list[float]] = []
    for dataset in datasets:
        mat.append([lookup.get((dataset, decoder), 0.0) for decoder in decoders])
    return datasets, decoders, mat


def _render_avg_flip_heatmap(rows: list[dict[str, str]], title: str, out_path: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(5.9, 3.9))
    ax.set_title(title)

    if not rows:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    datasets, decoders, mat = _metric_matrix(rows, "avg_flip_count")
    if not datasets or not decoders:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    im = ax.imshow(mat, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(decoders)))
    ax.set_xticklabels([DECODER_LABELS.get(d, d) for d in decoders], rotation=20, ha="right")
    ax.set_yticks(range(len(datasets)))
    ax.set_yticklabels([_pretty_dataset(d).replace("\n", " ") for d in datasets])
    ax.set_xlabel("Decoder")
    ax.set_ylabel("Fixture dataset")

    vmin = min(min(row) for row in mat)
    vmax = max(max(row) for row in mat)
    mid = (vmin + vmax) / 2.0
    for i, dataset_row in enumerate(mat):
        for j, value in enumerate(dataset_row):
            txt_color = "white" if value >= mid else "black"
            ax.text(j, i, f"{value:.3f}", ha="center", va="center", color=txt_color, fontsize=8)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.set_ylabel("Average flip count per request", rotation=270, labelpad=14)

    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _render_avg_flip_profile(rows: list[dict[str, str]], title: str, out_path: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(6.8, 3.9))
    ax.set_title(title)

    if not rows:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    datasets = _dataset_order(rows)
    decoders = _decoder_ordered(rows)
    if not datasets or not decoders:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    x = list(range(len(datasets)))
    lookup: dict[tuple[str, str], float] = {}
    for row in rows:
        lookup[(row.get("dataset", ""), row.get("decoder", ""))] = _safe_float(row.get("avg_flip_count"))

    max_y = 0.0
    for decoder in decoders:
        ys = [lookup.get((dataset, decoder), 0.0) for dataset in datasets]
        max_y = max(max_y, max(ys) if ys else 0.0)
        style = DECODER_STYLES.get(decoder, {"color": "#555555", "marker": "o", "linestyle": "-"})
        ax.plot(
            x,
            ys,
            label=DECODER_LABELS.get(decoder, decoder),
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=2.0,
            markersize=6,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([_pretty_dataset(d) for d in datasets])
    ax.set_xlabel("Dataset")
    ax.set_ylabel("Average flip count per request")
    ax.set_ylim(0.0, max(1.0, max_y * 1.12))
    ax.grid(axis="y", alpha=0.28, linewidth=0.8)
    ax.legend(title="Decoder", frameon=False, ncol=2, loc="upper left")
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _render_warning_rate_bar(rows: list[dict[str, str]], title: str, out_path: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.set_title(title)

    if not rows:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    datasets = _dataset_order(rows)
    if not datasets:
        ax.axis("off")
        ax.text(0.5, 0.5, "not run", ha="center", va="center", fontsize=10)
        _save_figure(fig, out_path)
        plt.close(fig)
        return

    rates: list[float] = []
    for dataset in datasets:
        vals = [
            _safe_float(row.get("warning_no_syndrome_rate"))
            for row in rows
            if row.get("dataset", "") == dataset
        ]
        rate = sum(vals) / float(len(vals)) if vals else 0.0
        rates.append(rate)

    x = list(range(len(datasets)))
    bars = ax.bar(x, rates, width=0.58, color="#4C78A8", edgecolor="#2F4B7C", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([_pretty_dataset(d) for d in datasets])
    ax.set_xlabel("Dataset")
    ax.set_ylabel("No-syndrome warning rate")
    ax.set_ylim(0.0, max(1.0, max(rates) + 0.10))
    ax.grid(axis="y", alpha=0.26, linewidth=0.8)

    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.015,
            f"{rate:.3f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _configure_matplotlib()

    fixture_rows = _load_rows(Path(args.fixture_csv))
    real_rows = _load_rows(Path(args.real_csv))

    _render_avg_flip_profile(
        fixture_rows,
        title="Fixture replay: decoder correction profile",
        out_path=out_dir / "figure_fixture_avg_flip_profile",
    )
    _render_avg_flip_heatmap(
        fixture_rows,
        title="Fixture replay: average flip count heatmap",
        out_path=out_dir / "figure_fixture_avg_flip_heatmap",
    )
    _render_avg_flip_profile(
        real_rows,
        title="Real-data slice replay: decoder correction profile",
        out_path=out_dir / "figure_real_avg_flip_profile",
    )
    _render_warning_rate_bar(
        fixture_rows,
        title="Fixture replay: no-syndrome warning rates by dataset",
        out_path=out_dir / "figure_fixture_warning_rate_bar",
    )
    _render_warning_rate_bar(
        real_rows,
        title="Real-data slice replay: no-syndrome warning rates by dataset",
        out_path=out_dir / "figure_real_warning_rate_bar",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
