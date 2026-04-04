#!/usr/bin/env python3
"""Generate a clean surface-code explanatory schematic for talks."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


COLOR_BG = "#FFFFFF"
COLOR_GRID = "#DADDE3"
COLOR_DATA = "#222222"
COLOR_X_CHECK = "#2C7BE5"
COLOR_Z_CHECK = "#F59F00"
COLOR_ERROR = "#E63946"
COLOR_TEXT = "#222222"
COLOR_BOUNDARY = "#6B7280"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distance", type=int, default=7, help="Lattice width/height in data-qubit points.")
    parser.add_argument(
        "--out-dir",
        default="talk_assets",
        help="Output folder for generated schematic files.",
    )
    parser.add_argument(
        "--basename",
        default="surface_code_schematic_clean",
        help="Output filename base (without extension).",
    )
    return parser.parse_args()


def _is_inside(x: float, y: float, d: int) -> bool:
    return -1e-9 <= x <= d - 1 + 1e-9 and -1e-9 <= y <= d - 1 + 1e-9


def draw_surface_panel(ax: plt.Axes, d: int, error_kind: str) -> None:
    # Data qubits on integer lattice points.
    data_points = [(x, y) for x in range(d) for y in range(d)]

    # Plaquette checks on half-integer centers; checkerboard alternates X and Z checks.
    check_points: list[tuple[float, float, str]] = []
    for x in range(d - 1):
        for y in range(d - 1):
            ctype = "X" if (x + y) % 2 == 0 else "Z"
            check_points.append((x + 0.5, y + 0.5, ctype))

    # Draw coupling lines between checks and adjacent data qubits.
    for cx, cy, _ in check_points:
        neighbors = [
            (cx - 0.5, cy - 0.5),
            (cx + 0.5, cy - 0.5),
            (cx - 0.5, cy + 0.5),
            (cx + 0.5, cy + 0.5),
        ]
        for nx, ny in neighbors:
            if _is_inside(nx, ny, d):
                ax.plot([cx, nx], [cy, ny], color=COLOR_GRID, lw=0.7, zorder=1)

    # Draw checks.
    x_checks = [(x, y) for x, y, t in check_points if t == "X"]
    z_checks = [(x, y) for x, y, t in check_points if t == "Z"]
    ax.scatter(
        [p[0] for p in x_checks],
        [p[1] for p in x_checks],
        s=90,
        marker="s",
        facecolor=COLOR_X_CHECK,
        edgecolor="#1B4F9A",
        linewidth=0.8,
        zorder=2,
    )
    ax.scatter(
        [p[0] for p in z_checks],
        [p[1] for p in z_checks],
        s=90,
        marker="D",
        facecolor=COLOR_Z_CHECK,
        edgecolor="#A66A00",
        linewidth=0.8,
        zorder=2,
    )

    # Draw data qubits.
    ax.scatter(
        [p[0] for p in data_points],
        [p[1] for p in data_points],
        s=85,
        marker="o",
        facecolor=COLOR_BG,
        edgecolor=COLOR_DATA,
        linewidth=1.2,
        zorder=3,
    )

    # Choose one center data qubit as the injected error.
    ex, ey = d // 2, d // 2
    ax.scatter(
        [ex],
        [ey],
        s=145,
        marker="o",
        facecolor=COLOR_ERROR,
        edgecolor="#8A1F29",
        linewidth=1.0,
        zorder=5,
    )

    # Error type determines which check family is excited.
    target_check = "X" if error_kind == "Z" else "Z"
    triggered: list[tuple[float, float]] = []
    for sx in (-0.5, 0.5):
        for sy in (-0.5, 0.5):
            cx, cy = ex + sx, ey + sy
            if not _is_inside(cx, cy, d):
                continue
            parity = (int(cx - 0.5) + int(cy - 0.5)) % 2
            ctype = "X" if parity == 0 else "Z"
            if ctype == target_check:
                triggered.append((cx, cy))

    # Highlight triggered checks with red rings and labels.
    for cx, cy in triggered:
        ax.scatter(
            [cx],
            [cy],
            s=250,
            marker="o",
            facecolor="none",
            edgecolor=COLOR_ERROR,
            linewidth=2.0,
            zorder=6,
        )
        ax.text(
            cx + 0.16,
            cy + 0.16,
            "s=1",
            fontsize=9,
            color=COLOR_ERROR,
            zorder=7,
        )

    # Patch boundary and labels.
    ax.plot(
        [-0.35, d - 0.65, d - 0.65, -0.35, -0.35],
        [-0.35, -0.35, d - 0.65, d - 0.65, -0.35],
        color=COLOR_BOUNDARY,
        lw=1.4,
        linestyle=(0, (4, 2)),
        zorder=0,
    )
    ax.text((d - 1) / 2.0, d - 0.25, "rough boundary (X)", ha="center", va="bottom", fontsize=9, color=COLOR_BOUNDARY)
    ax.text((d - 1) / 2.0, -0.55, "rough boundary (X)", ha="center", va="top", fontsize=9, color=COLOR_BOUNDARY)
    ax.text(-0.55, (d - 1) / 2.0, "smooth (Z)", ha="right", va="center", rotation=90, fontsize=9, color=COLOR_BOUNDARY)
    ax.text(d - 0.45, (d - 1) / 2.0, "smooth (Z)", ha="left", va="center", rotation=270, fontsize=9, color=COLOR_BOUNDARY)

    if error_kind == "Z":
        ax.set_title("Phase-flip (Z) on data qubit -> X-check syndromes", fontsize=12, color=COLOR_TEXT, pad=10)
    else:
        ax.set_title("Bit-flip (X) on data qubit -> Z-check syndromes", fontsize=12, color=COLOR_TEXT, pad=10)

    ax.set_xlim(-0.95, d - 0.05)
    ax.set_ylim(-0.95, d - 0.05)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def build_figure(distance: int) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.6), facecolor=COLOR_BG)
    draw_surface_panel(axes[0], distance, error_kind="Z")
    draw_surface_panel(axes[1], distance, error_kind="X")

    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="None", markersize=8, markerfacecolor=COLOR_BG, markeredgecolor=COLOR_DATA, label="Data qubit"),
        Line2D([0], [0], marker="s", linestyle="None", markersize=8, markerfacecolor=COLOR_X_CHECK, markeredgecolor="#1B4F9A", label="X-check ancilla"),
        Line2D([0], [0], marker="D", linestyle="None", markersize=8, markerfacecolor=COLOR_Z_CHECK, markeredgecolor="#A66A00", label="Z-check ancilla"),
        Line2D([0], [0], marker="o", linestyle="None", markersize=9, markerfacecolor=COLOR_ERROR, markeredgecolor="#8A1F29", label="Data-qubit error"),
        Line2D([0], [0], marker="o", linestyle="None", markersize=11, markerfacecolor="none", markeredgewidth=2.0, markeredgecolor=COLOR_ERROR, label="Triggered syndrome"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.5, -0.01),
        fontsize=10,
    )

    fig.suptitle(
        "Surface-Code Syndrome Intuition (Conceptual Planar Patch)",
        fontsize=16,
        color=COLOR_TEXT,
        y=0.98,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.935,
        "A single data error excites neighboring checks of the opposite type: Z errors excite X checks, X errors excite Z checks.",
        ha="center",
        fontsize=10.5,
        color="#444444",
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.92))
    return fig


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / args.basename

    fig = build_figure(distance=max(5, args.distance))
    fig.savefig(base.with_suffix(".png"), dpi=400, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), dpi=400, bbox_inches="tight")
    fig.savefig(base.with_suffix(".svg"), dpi=400, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {base.with_suffix('.png')}")
    print(f"Wrote {base.with_suffix('.pdf')}")
    print(f"Wrote {base.with_suffix('.svg')}")


if __name__ == "__main__":
    main()
