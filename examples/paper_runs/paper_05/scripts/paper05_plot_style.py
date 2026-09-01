#!/usr/bin/env python3
"""Shared journal-style plotting helpers for paper_05."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


HEATMAP_CMAP = "viridis"
GRID_COLOR = "#D1D5DB"
AXIS_COLOR = "#374151"
TEXT_COLOR = "#111827"
MUTED_TEXT = "#4B5563"
EXACT_COLOR = "#2563EB"
CONTAINS_COLOR = "#059669"
LOCAL_COLOR = "#D97706"
IBM_COLOR = "#334155"
GKP_COLOR = "#7C3AED"


def apply_journal_style() -> None:
    import matplotlib as mpl  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore

    plt.style.use("ggplot")
    mpl.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 600,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": AXIS_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "axes.titlecolor": TEXT_COLOR,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID_COLOR,
            "grid.linewidth": 0.45,
            "grid.alpha": 0.75,
            "xtick.color": MUTED_TEXT,
            "ytick.color": MUTED_TEXT,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "font.family": "DejaVu Sans",
            "font.size": 8.2,
            "axes.labelsize": 8.4,
            "axes.titlesize": 9.0,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 7.0,
            "legend.title_fontsize": 7.2,
            "lines.linewidth": 1.45,
            "lines.markersize": 4.2,
            "patch.linewidth": 0.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def half_panel_size(kind: str, n_rows: int = 0) -> tuple[float, float]:
    if kind == "heatmap":
        return (3.55, max(2.25, min(4.25, 0.205 * max(1, n_rows) + 0.95)))
    if kind == "rate":
        return (3.55, 2.55)
    if kind == "bar":
        return (3.55, 2.35)
    return (3.55, 2.55)


def horizontal_heatmap_size(n_columns: int, n_rows: int) -> tuple[float, float]:
    width = max(4.25, min(6.2, 0.23 * max(1, n_columns) + 1.55))
    height = max(1.85, min(3.05, 0.10 * max(1, n_rows) + 1.25))
    return (width, height)


def short_dataset_label(dataset: str, backend: str = "") -> str:
    if dataset == "local_simulator":
        return "local"
    if dataset == "digitized_gkp_pennylane":
        return "PennyLane"
    if dataset == "digitized_gkp_local":
        return "local GKP"
    name = backend or dataset
    if name.startswith("ibm_"):
        return "IBM " + name.removeprefix("ibm_")
    if dataset.startswith("ibm_ibm_"):
        return "IBM " + dataset.removeprefix("ibm_ibm_")
    return dataset.replace("_", " ")


def compact_source_label(dataset: str, circuit: str, backend: str = "") -> str:
    source = "L" if dataset == "local_simulator" else "I"
    if dataset.startswith("digitized_gkp"):
        source = "PL"
    if dataset.startswith("ibm_") or backend.startswith("ibm_"):
        source = "I"
    if circuit == "clean":
        target = "clean"
    elif circuit.startswith("x_data_"):
        target = "X" + circuit.removeprefix("x_data_")
    elif circuit.startswith("q_shift_data_"):
        target = "q" + circuit.removeprefix("q_shift_data_")
    else:
        target = circuit.replace("_", " ")
    return f"{source}-{target}"


def metric_color(metric_name: str) -> str:
    lowered = metric_name.lower()
    if "contain" in lowered:
        return CONTAINS_COLOR
    if "exact" in lowered or "localization" in lowered:
        return EXACT_COLOR
    return AXIS_COLOR


def source_linestyle(dataset: str) -> str:
    return "-" if dataset.startswith("ibm_") or dataset.startswith("digitized_gkp") else (0, (4, 2))


def source_marker(dataset: str, fallback: str) -> str:
    if dataset == "local_simulator":
        return "D"
    return fallback


def style_heatmap_axis(ax: Any) -> None:
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.65)
        spine.set_color(AXIS_COLOR)
    ax.tick_params(axis="both", length=2.4, width=0.65, color=AXIS_COLOR)


def style_rate_axis(ax: Any, *, ymin: float, ymax: float = 1.02) -> None:
    ax.set_ylim(ymin, ymax)
    ax.set_yticks([tick for tick in (0.0, 0.25, 0.5, 0.75, 1.0) if ymin <= tick <= ymax])
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS_COLOR)
        ax.spines[side].set_linewidth(0.75)
    ax.tick_params(axis="both", length=2.4, width=0.65, color=AXIS_COLOR)


def style_bar_axis(ax: Any) -> None:
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS_COLOR)
        ax.spines[side].set_linewidth(0.75)


def save_journal_figure(fig: Any, prefix: Path, manuscript_dir: Path | None) -> None:
    for ext in (".pdf", ".png", ".svg"):
        out = prefix.with_suffix(ext)
        kwargs: dict[str, Any] = {
            "bbox_inches": "tight",
            "facecolor": "white",
            "edgecolor": "white",
            "pad_inches": 0.04,
        }
        if ext == ".png":
            kwargs["dpi"] = 600
        fig.savefig(out, **kwargs)
        if manuscript_dir is not None:
            manuscript_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, manuscript_dir / out.name)
