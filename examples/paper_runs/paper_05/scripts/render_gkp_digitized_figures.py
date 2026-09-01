#!/usr/bin/env python3
"""Render conceptual digitized-GKP encoding figures for paper_05."""

from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from gkp_digitized_syndrome import SQRT_PI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manuscript-dir")
    return parser.parse_args()


def save_fig(fig: Any, prefix: Path, manuscript_dir: Path | None) -> None:
    for ext in (".pdf", ".png", ".svg"):
        out = prefix.with_suffix(ext)
        fig.savefig(out, bbox_inches="tight")
        if manuscript_dir is not None:
            manuscript_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, manuscript_dir / out.name)


def add_panel_label(ax: Any, label: str) -> None:
    ax.text(
        0.5,
        -0.34,
        label,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.0,
        color="#111827",
        clip_on=False,
    )


def draw_phase_space(ax: Any) -> None:
    from matplotlib.patches import FancyArrowPatch, Rectangle

    xs = np.arange(-2, 3) * SQRT_PI
    ys = np.arange(-2, 3) * SQRT_PI
    for x in xs:
        ax.axvline(x, color="#E5E7EB", linewidth=0.8, zorder=0)
    for y in ys:
        ax.axhline(y, color="#E5E7EB", linewidth=0.8, zorder=0)
    xx, yy = np.meshgrid(xs, ys)
    ax.scatter(xx.ravel(), yy.ravel(), s=32, color="#2563EB", edgecolor="white", linewidth=0.6, zorder=2)
    cell = 0.25 * SQRT_PI
    ax.add_patch(
        Rectangle(
            (-cell, -cell),
            2 * cell,
            2 * cell,
            facecolor="#D1FAE5",
            alpha=0.45,
            edgecolor="#059669",
            linewidth=1.8,
            linestyle="-",
        )
    )
    ax.add_patch(
        FancyArrowPatch(
            (0.0, 0.0),
            (0.58 * SQRT_PI, 0.0),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.2,
            color="#DC2626",
            zorder=3,
        )
    )
    ax.text(0.22 * SQRT_PI, 0.18 * SQRT_PI, r"$\Delta q$", color="#DC2626", fontsize=8.4)
    ax.set_xlim(-2.25 * SQRT_PI, 2.25 * SQRT_PI)
    ax.set_ylim(-2.25 * SQRT_PI, 2.25 * SQRT_PI)
    ax.set_aspect("equal")
    ax.set_xlabel(r"$q$ quadrature")
    ax.set_ylabel(r"$p$ quadrature")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def draw_digitized_circuit_schematic(fig: Any, out_dir: Path, manuscript_dir: Path | None) -> None:
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

    ax = fig.add_subplot(111)
    ax.set_xlim(0.0, 18.0)
    ax.set_ylim(0.0, 7.9)
    ax.axis("off")

    mode_rows = [
        ("q1", 6.35),
        ("q5", 5.80),
        ("q10", 5.25),
        ("q14", 4.70),
        ("q17", 4.15),
        ("q22", 3.60),
        ("q32", 3.05),
        ("q37", 2.50),
    ]
    check_rows = [("Z0", 1.55), ("Z1...Z14", 1.05), ("Z15", 0.55)]
    columns = {
        "source": 1.70,
        "inject": 2.95,
        "noise": 4.15,
        "measure": 5.35,
        "bin": 6.55,
        "checks": 7.85,
        "request": 9.65,
        "decoder": 11.35,
        "out": 12.65,
    }

    colors = {
        "wire": "#6B7280",
        "grid": "#EEF2F7",
        "text": "#111827",
        "muted": "#64748B",
        "source": "#EAF3FF",
        "source_edge": "#4EA3F1",
        "inject": "#FFF1F2",
        "inject_edge": "#E0527D",
        "noise": "#F8FAFC",
        "noise_edge": "#94A3B8",
        "readout": "#ECFDF5",
        "readout_edge": "#10B981",
        "bin": "#F0FDFA",
        "bin_edge": "#14B8A6",
        "request": "#F5F3FF",
        "request_edge": "#7C3AED",
        "out": "#FFF7ED",
        "out_edge": "#F59E0B",
        "measure_gray": "#D1D5DB",
        "measure_gray_edge": "#6B7280",
    }

    def stage(x0: float, x1: float, label: str) -> None:
        ax.add_patch(
            Rectangle(
                (x0, 1.95),
                x1 - x0,
                4.75,
                facecolor="#F8FAFC",
                edgecolor="none",
                alpha=0.18,
                zorder=0,
            )
        )
        ax.text((x0 + x1) / 2.0, 6.93, label, ha="center", va="bottom", fontsize=7.1, color=colors["muted"])

    def rounded(
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        *,
        face: str,
        edge: str,
        fs: float = 7.6,
        weight: str = "normal",
        text_color: str = "#111827",
        lw: float = 0.9,
    ) -> None:
        ax.add_patch(
            FancyBboxPatch(
                (x - w / 2.0, y - h / 2.0),
                w,
                h,
                boxstyle="round,pad=0.015,rounding_size=0.035",
                facecolor=face,
                edgecolor=edge,
                linewidth=lw,
                zorder=4,
            )
        )
        ax.text(x, y, text, ha="center", va="center", fontsize=fs, weight=weight, color=text_color, zorder=5)

    def arrow(x0: float, y0: float, x1: float, y1: float, *, color: str = "#64748B", lw: float = 0.9) -> None:
        ax.add_patch(
            FancyArrowPatch(
                (x0, y0),
                (x1, y1),
                arrowstyle="-|>",
                mutation_scale=8.5,
                linewidth=lw,
                color=color,
                shrinkA=1.0,
                shrinkB=1.0,
                zorder=2,
            )
        )

    def meter(x: float, y: float) -> None:
        rounded(x, y, 0.56, 0.30, r"$M_q$", face=colors["readout"], edge=colors["readout_edge"], fs=7.2)
        ax.plot([x - 0.17, x, x + 0.17], [y - 0.02, y + 0.09, y - 0.02], color=colors["readout_edge"], linewidth=0.75, zorder=6)

    def measure_symbol(x: float, y: float, scale: float = 1.0) -> None:
        rounded(
            x,
            y,
            0.34 * scale,
            0.28 * scale,
            r"$M$",
            face=colors["measure_gray"],
            edge=colors["measure_gray_edge"],
            fs=6.6 * scale,
        )
        ax.plot(
            [x - 0.11 * scale, x + 0.02 * scale, x + 0.13 * scale],
            [y - 0.02 * scale, y + 0.08 * scale, y - 0.02 * scale],
            color="#374151",
            linewidth=0.65 * scale,
            zorder=7,
        )

    for x0, x1, label in [
        (1.18, 2.25, "CV source"),
        (2.45, 3.40, r"$q$ injection"),
        (3.68, 4.62, "shift noise"),
        (4.88, 6.98, "readout and binning"),
        (7.24, 8.52, "outer checks"),
        (9.02, 12.95, "request and correction"),
    ]:
        stage(x0, x1, label)

    ax.text(0.40, 6.90, "mode", fontsize=7.2, color=colors["muted"], ha="left")
    ax.text(0.40, 1.86, "check", fontsize=7.2, color=colors["muted"], ha="left")

    for label, y in mode_rows:
        ax.text(0.62, y, label, ha="right", va="center", fontsize=7.8, color=colors["text"])
        ax.plot([0.78, 7.08], [y, y], color=colors["wire"], linewidth=0.85, zorder=1)
        rounded(columns["source"], y, 0.62, 0.28, r"$G_{\rm CV}$", face=colors["source"], edge=colors["source_edge"], fs=7.0)
        rounded(columns["inject"], y, 0.58, 0.28, r"$D_q$", face=colors["inject"], edge=colors["inject_edge"], fs=7.3)
        rounded(columns["noise"], y, 0.58, 0.28, r"$N_\sigma$", face=colors["noise"], edge=colors["noise_edge"], fs=7.2)
        meter(columns["measure"], y)
        rounded(columns["bin"], y, 0.50, 0.28, r"$b$", face=colors["bin"], edge=colors["bin_edge"], fs=7.4, weight="bold")
        arrow(columns["bin"] + 0.31, y, 7.06, y, color=colors["bin_edge"], lw=0.70)

    ax.plot([7.08, 7.08], [2.25, 6.60], color=colors["bin_edge"], linewidth=1.35, zorder=2)
    for label, y in check_rows:
        ax.text(0.62, y, label, ha="right", va="center", fontsize=7.5, color=colors["text"])
        ax.plot([0.78, 8.44], [y, y], color="#D1D5DB", linewidth=0.78, zorder=1)
        arrow(7.08, 4.35, columns["checks"] - 0.38, y, color=colors["bin_edge"], lw=0.82)
        rounded(columns["checks"], y, 0.66, 0.30, r"$Z_j$", face="#FFFFFF", edge=colors["bin_edge"], fs=7.1)
        arrow(columns["checks"] + 0.40, y, columns["request"] - 0.85, y, color="#0F766E", lw=0.92)

    ax.add_patch(
        FancyBboxPatch(
            (7.33, 0.28),
            1.15,
            1.62,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="none",
            edgecolor="#99F6E4",
            linewidth=0.8,
            zorder=1,
        )
    )

    rounded(
        columns["request"],
        1.05,
        1.28,
        0.96,
        "LiDMaS+\nrequest\nschema",
        face=colors["request"],
        edge=colors["request_edge"],
        fs=7.3,
        weight="bold",
    )
    rounded(
        columns["decoder"],
        1.05,
        1.32,
        0.96,
        "minimum-\nweight\ncorrection",
        face="#FFFFFF",
        edge=colors["request_edge"],
        fs=7.2,
    )
    rounded(
        columns["out"],
        1.05,
        0.82,
        0.74,
        r"$C$",
        face=colors["out"],
        edge=colors["out_edge"],
        fs=10.5,
        weight="bold",
    )
    arrow(columns["request"] + 0.72, 1.05, columns["decoder"] - 0.76, 1.05, color=colors["request_edge"], lw=1.15)
    arrow(columns["decoder"] + 0.76, 1.05, columns["out"] - 0.48, 1.05, color=colors["out_edge"], lw=1.0)

    for x, y, c in [(12.24, 1.47, "#0EA5E9"), (12.34, 1.56, "#E0527D"), (12.45, 1.45, "#14B8A6")]:
        ax.add_patch(Circle((x, y), 0.035, facecolor=c, edgecolor="white", linewidth=0.3, zorder=7))

    inset_x0 = 14.0
    ax.plot([inset_x0, inset_x0], [0.85, 6.85], color="#94A3B8", linewidth=0.8, linestyle=(0, (5, 4)), zorder=1)
    ax.text(
        inset_x0 + 0.12,
        7.00,
        "measurement-bit ordering inset",
        fontsize=6.8,
        color=colors["muted"],
        ha="left",
        va="bottom",
    )
    for idx, number in enumerate([8, 1, 7, 0, 6, 2, 9, 3]):
        x = inset_x0 + 0.58 + idx * 0.46
        y = 6.55 - idx * 0.42
        ax.plot([inset_x0, x + 0.34], [y, y], color="#CBD5E1", linewidth=0.65, linestyle=(0, (3, 3)), zorder=0)
        measure_symbol(x, y, scale=0.92)
        ax.plot([x, x], [y - 0.18, 0.80], color="#6B7280", linewidth=0.65, linestyle=(0, (2, 3)), zorder=1)
        arrow(x, 0.80, x, 0.58, color="#6B7280", lw=0.65)
        ax.text(x, 0.47, str(number), fontsize=6.2, color="#374151", ha="center", va="top")

    ax.text(
        8.85,
        0.20,
        "Binary events preserve the same outer Z-check ordering as the surface-code branch.",
        fontsize=7.0,
        color=colors["muted"],
        ha="center",
    )

    save_fig(fig, out_dir / "figure_gkp_digitized_circuit_schematic", manuscript_dir)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    manuscript_dir = Path(args.manuscript_dir) if args.manuscript_dir else None
    out_dir.mkdir(parents=True, exist_ok=True)
    if manuscript_dir is not None:
        manuscript_dir.mkdir(parents=True, exist_ok=True)

    import matplotlib  # type: ignore

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, axes = plt.subplots(1, 3, figsize=(7.8, 2.85), gridspec_kw={"width_ratios": [1.12, 1.0, 1.22]})
    fig.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.32, wspace=0.36)
    draw_phase_space(axes[0])

    axes[1].axis("off")
    axes[1].set_xlim(0.0, 1.0)
    axes[1].set_ylim(0.0, 1.0)

    def flow_box(y: float, text: str, *, face: str, edge: str) -> None:
        axes[1].add_patch(
            FancyBboxPatch(
                (0.10, y - 0.095),
                0.78,
                0.19,
                boxstyle="round,pad=0.018,rounding_size=0.025",
                facecolor=face,
                edgecolor=edge,
                linewidth=0.8,
                zorder=2,
            )
        )
        axes[1].text(0.49, y, text, ha="center", va="center", fontsize=8.0, color="#111827", zorder=3)

    flow_box(0.76, r"$y_j=|S_j|^{-1/2}\sum_{i\in S_j}\Delta q_i$", face="#F8FAFC", edge="#94A3B8")
    flow_box(0.49, r"$\tilde y_j=y_j\ {\rm mod}\ \sqrt{\pi}$", face="#EFF6FF", edge="#60A5FA")
    flow_box(0.22, r"$b_j=\mathbf{1}(|\tilde y_j|>0.25\sqrt{\pi})$", face="#ECFDF5", edge="#10B981")
    for y0, y1 in [(0.655, 0.595), (0.385, 0.325)]:
        axes[1].add_patch(
            FancyArrowPatch(
                (0.49, y0),
                (0.49, y1),
                transform=axes[1].transAxes,
                arrowstyle="-|>",
                mutation_scale=11,
                linewidth=1.1,
                color="#475569",
            )
        )

    ax = axes[2]
    ax.axis("off")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    data_x = np.linspace(0.12, 0.88, 8)
    check_x = np.array([0.25, 0.50, 0.75])
    data_y = 0.72
    check_y = 0.34
    edge_sets = {
        0: [0, 1, 3, 4],
        1: [1, 2, 4, 6],
        2: [3, 5, 6, 7],
    }
    for check_index, data_indices in edge_sets.items():
        for data_index in data_indices:
            ax.plot(
                [check_x[check_index], data_x[data_index]],
                [check_y, data_y],
                color="#CBD5E1",
                linewidth=0.9,
                zorder=1,
            )
    ax.scatter(data_x, np.full_like(data_x, data_y), s=46, color="#2563EB", edgecolor="white", linewidth=0.7, zorder=3)
    ax.scatter(check_x, np.full_like(check_x, check_y), s=62, marker="s", color="#059669", edgecolor="white", linewidth=0.8, zorder=4)
    for x, label in zip(data_x, ["1", "5", "10", "14", "17", "22", "32", "37"]):
        ax.text(x, data_y + 0.095, label, ha="center", va="center", fontsize=6.6, color="#374151")
    for x, label in zip(check_x, [r"$Z_0$", r"$Z_j$", r"$Z_{15}$"]):
        ax.text(x, check_y - 0.12, label, ha="center", va="center", fontsize=7.4, color="#111827")
    ax.text(0.50, 0.08, "binary bits inherit the surface-code Z-check order", ha="center", va="center", fontsize=7.3, color="#64748B")

    add_panel_label(axes[0], "(a) GKP lattice")
    add_panel_label(axes[1], "(b) Analog-to-binary map")
    add_panel_label(axes[2], "(c) Outer checks")
    save_fig(fig, out_dir / "figure_gkp_digitized_encoding_schematic", manuscript_dir)
    plt.close(fig)

    fig = plt.figure(figsize=(10.8, 5.3))
    draw_digitized_circuit_schematic(fig, out_dir, manuscript_dir)
    print(f"Wrote digitized-GKP figures to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
