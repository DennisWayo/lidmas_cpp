#!/usr/bin/env python3
"""Render 2D syndrome-layout figures for paper_04 runs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Polygon

from generate_comparison_requests import SurfaceGeometry, build_surface_geometry

STYLE = {
    "bg": "#FFFFFF",
    "support": "#111827",
    "data": "#DC2626",
    "data_text": "#7F1D1D",
    "x": "#2B7BBB",
    "x_text": "#1D4ED8",
    "x_stab": "#AFC7F2",
    "z": "#4DA64D",
    "z_text": "#166534",
    "z_stab": "#B9DDB4",
}

LABEL_BBOX = {"facecolor": "white", "edgecolor": "none", "alpha": 0.74, "pad": 0.04}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.facecolor": STYLE["bg"],
        "figure.facecolor": STYLE["bg"],
        "savefig.facecolor": STYLE["bg"],
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        default="examples/paper_runs/paper_04/results/03_analysis/runs",
        help="Root directory containing per-family run outputs.",
    )
    parser.add_argument(
        "--out-dir",
        default="examples/paper_runs/paper_04/results/03_analysis/syndrome_layout_figures",
        help="Output directory for 2D syndrome layout figures.",
    )
    return parser.parse_args()


def _load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _layout_coords(geom: SurfaceGeometry) -> tuple[dict[int, tuple[float, float]], dict[int, tuple[float, float]], dict[int, tuple[float, float]]]:
    d = geom.distance
    data: dict[int, tuple[float, float]] = {}
    x_checks: dict[int, tuple[float, float]] = {}
    z_checks: dict[int, tuple[float, float]] = {}

    idx = 0
    # Horizontal data qubits h(x, y): between X(x, y) and X(x+1, y)
    for y in range(d):
        for x in range(d - 1):
            data[idx] = (x + 0.5, float(y))
            idx += 1
    # Vertical data qubits v(x, y): between X(x, y) and X(x, y+1)
    for y in range(d - 1):
        for x in range(d):
            data[idx] = (float(x), y + 0.5)
            idx += 1

    for y in range(d):
        for x in range(d):
            x_idx = y * d + x
            x_checks[x_idx] = (float(x), float(y))

    z_idx = 0
    for y in range(d - 1):
        for x in range(d - 1):
            z_checks[z_idx] = (x + 0.5, y + 0.5)
            z_idx += 1

    return data, x_checks, z_checks


def _ordered_support_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def _draw_stabilizer_patch(ax: Any, points: list[tuple[float, float]], color: str, zorder: int) -> None:
    ordered = _ordered_support_points(points)
    if len(ordered) >= 3:
        ax.add_patch(
            Polygon(
                ordered,
                closed=True,
                facecolor=color,
                edgecolor="none",
                alpha=0.55,
                zorder=zorder,
            )
        )
    elif len(ordered) == 2:
        (x0, y0), (x1, y1) = ordered
        ax.plot([x0, x1], [y0, y1], color=color, linewidth=12.0, alpha=0.40, solid_capstyle="round", zorder=zorder)


def _draw_panel(
    ax: Any,
    geom: SurfaceGeometry,
    *,
    show_x: bool,
    show_z: bool,
    indexed: bool,
    title: str,
) -> None:
    data_coords, x_coords, z_coords = _layout_coords(geom)
    d = geom.distance

    def _is_int(v: float) -> bool:
        return abs(v - round(v)) < 1e-9

    # Draw translucent stabilizer regions first, then overlay dashed supports.
    if show_x:
        for support in geom.x_supports:
            _draw_stabilizer_patch(ax, [data_coords[dq] for dq in support], STYLE["x_stab"], zorder=0)

    if show_z:
        for support in geom.z_supports:
            _draw_stabilizer_patch(ax, [data_coords[dq] for dq in support], STYLE["z_stab"], zorder=0)

    if show_x:
        for x_idx, support in enumerate(geom.x_supports):
            cx, cy = x_coords[x_idx]
            for dq in support:
                qx, qy = data_coords[dq]
                ax.plot(
                    [cx, qx],
                    [cy, qy],
                    color=STYLE["support"],
                    linewidth=0.85,
                    alpha=0.72,
                    linestyle=(0, (2.5, 2.5)),
                    zorder=1,
                )

    if show_z:
        for z_idx, support in enumerate(geom.z_supports):
            cx, cy = z_coords[z_idx]
            for dq in support:
                qx, qy = data_coords[dq]
                ax.plot(
                    [cx, qx],
                    [cy, qy],
                    color=STYLE["support"],
                    linewidth=0.85,
                    alpha=0.72,
                    linestyle=(0, (2.5, 2.5)),
                    zorder=1,
                )

    # Data qubits.
    for dq, (qx, qy) in data_coords.items():
        ax.scatter(qx, qy, s=54, color=STYLE["data"], edgecolors="white", linewidths=0.8, zorder=5)
        if indexed:
            # Route data labels by edge orientation to reduce overlap with check labels.
            if _is_int(qy):  # horizontal data edge
                ddx, ddy = (0.06, -0.08)
            else:  # vertical data edge
                ddx, ddy = (0.07, 0.08)
            ax.text(
                qx + ddx,
                qy + ddy,
                f"D{dq}",
                fontsize=6.0,
                color=STYLE["data_text"],
                zorder=6,
                bbox=LABEL_BBOX,
            )

    # X checks.
    if show_x:
        xs = [x for x, _ in x_coords.values()]
        ys = [y for _, y in x_coords.values()]
        ax.scatter(
            xs,
            ys,
            s=72,
            marker="o",
            color=STYLE["x"],
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label="X checks",
        )
        if indexed:
            for x_idx, (cx, cy) in x_coords.items():
                # Keep X labels above checks and nudge outer columns inward.
                xdx = -0.13
                if cx <= 0.0:
                    xdx = -0.10
                elif cx >= d - 1:
                    xdx = -0.16
                ax.text(
                    cx + xdx,
                    cy - 0.19,
                    f"X{x_idx:02d}",
                    fontsize=6.0,
                    color=STYLE["x_text"],
                    zorder=5,
                    bbox=LABEL_BBOX,
                )

    # Z checks.
    if show_z:
        xs = [x for x, _ in z_coords.values()]
        ys = [y for _, y in z_coords.values()]
        ax.scatter(
            xs,
            ys,
            s=72,
            marker="o",
            color=STYLE["z"],
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label="Z checks",
        )
        if indexed:
            for z_idx, (cx, cy) in z_coords.items():
                # Place Z labels below checks, alternating side to avoid dense runs.
                zdx = -0.15 if (z_idx % 2 == 0) else 0.05
                if cx <= 0.7:
                    zdx = 0.04
                elif cx >= d - 1.3:
                    zdx = -0.18
                ax.text(
                    cx + zdx,
                    cy + 0.13,
                    f"Z{z_idx:02d}",
                    fontsize=6.0,
                    color=STYLE["z_text"],
                    zorder=5,
                    bbox=LABEL_BBOX,
                )
    ax.set_xlim(-0.60, d - 1 + 0.60)
    ax.set_ylim(d - 1 + 0.60, -0.60)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlabel("")
    ax.set_ylabel("")


def _save_all(fig: Any, out_base: Path) -> None:
    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_base.with_suffix(ext), bbox_inches="tight", dpi=360)


def render_surface_figures(geom: SurfaceGeometry, out_dir: Path) -> None:
    # Compact manuscript-facing view.
    fig, axes = plt.subplots(1, 3, figsize=(15.8, 5.3), constrained_layout=True)
    _draw_panel(axes[0], geom, show_x=True, show_z=False, indexed=False, title="Surface: X-check supports")
    _draw_panel(axes[1], geom, show_x=False, show_z=True, indexed=False, title="Surface: Z-check supports")
    _draw_panel(axes[2], geom, show_x=True, show_z=True, indexed=False, title="Surface: Combined support graph")

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["data"], markeredgecolor="white", label="Data qubit"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["x"], markeredgecolor="white", label="X ancilla qubit"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["z"], markeredgecolor="white", label="Z ancilla qubit"),
        Patch(facecolor=STYLE["x_stab"], edgecolor="none", alpha=0.55, label="X stabilizer"),
        Patch(facecolor=STYLE["z_stab"], edgecolor="none", alpha=0.55, label="Z stabilizer"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.13), fontsize=10)
    _save_all(fig, out_dir / "figure_surface_2d_syndrome_layout")
    plt.close(fig)

    # Indexed engineering/debug view.
    fig_idx, ax_idx = plt.subplots(figsize=(7.8, 6.8), constrained_layout=True)
    _draw_panel(
        ax_idx,
        geom,
        show_x=True,
        show_z=True,
        indexed=True,
        title="Surface: Indexed support graph (data/check ids)",
    )
    _save_all(fig_idx, out_dir / "figure_surface_2d_syndrome_layout_indexed")
    plt.close(fig_idx)

    # Indexed manuscript-facing triptych view (X-only, Z-only, combined).
    fig_all_idx, axes_all_idx = plt.subplots(1, 3, figsize=(17.2, 5.7), constrained_layout=True)
    _draw_panel(
        axes_all_idx[0],
        geom,
        show_x=True,
        show_z=False,
        indexed=True,
        title="Surface: X-check supports (indexed)",
    )
    _draw_panel(
        axes_all_idx[1],
        geom,
        show_x=False,
        show_z=True,
        indexed=True,
        title="Surface: Z-check supports (indexed)",
    )
    _draw_panel(
        axes_all_idx[2],
        geom,
        show_x=True,
        show_z=True,
        indexed=True,
        title="Surface: Combined support graph (indexed)",
    )
    fig_all_idx.legend(handles=handles, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.13), fontsize=10)
    _save_all(fig_all_idx, out_dir / "figure_surface_2d_syndrome_layout_all_indexed")
    plt.close(fig_all_idx)


def render_gkp_figures(geom: SurfaceGeometry, out_dir: Path) -> None:
    # Same topology as surface, with GKP annotation.
    fig, ax = plt.subplots(figsize=(7.6, 6.4), constrained_layout=True)
    _draw_panel(
        ax,
        geom,
        show_x=True,
        show_z=True,
        indexed=False,
        title=(
            "Digitized-GKP outer support topology\n"
            "(shared by PennyLane / Qiskit / Cirq / LiDMaS+ variants)"
        ),
    )
    _save_all(fig, out_dir / "figure_gkp_2d_syndrome_layout")
    plt.close(fig)

    # Indexed engineering/debug view.
    fig_idx, ax_idx = plt.subplots(figsize=(8.4, 7.2), constrained_layout=True)
    _draw_panel(
        ax_idx,
        geom,
        show_x=True,
        show_z=True,
        indexed=True,
        title=(
            "Digitized-GKP outer support topology (indexed)\n"
            "(shared by PennyLane / Qiskit / Cirq / LiDMaS+ variants)"
        ),
    )
    _save_all(fig_idx, out_dir / "figure_gkp_2d_syndrome_layout_indexed")
    plt.close(fig_idx)


def _draw_gkp_phase_space(ax: Any, *, indexed: bool = False) -> None:
    sqrt_pi = math.sqrt(math.pi)
    lim = 2.5 * sqrt_pi

    # Stabilizer decision boundaries.
    for k in range(-2, 3):
        x = (k + 0.5) * sqrt_pi
        y = (k + 0.5) * sqrt_pi
        ax.axvline(x, color="#94A3B8", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
        ax.axhline(y, color="#94A3B8", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)

    # GKP peak lattice (conceptual envelope).
    for i in range(-2, 3):
        for j in range(-2, 3):
            q = i * sqrt_pi
            p = j * sqrt_pi
            w = 1.0 if (i == 0 and j == 0) else 0.6
            ax.scatter(q, p, s=36 * w, color="#2563EB", alpha=0.78, zorder=3)
            ax.add_patch(Circle((q, p), radius=0.10 * sqrt_pi, edgecolor="#2563EB", facecolor="none", alpha=0.35, zorder=2))
            if indexed:
                ax.text(
                    q + 0.08 * sqrt_pi,
                    p + 0.08 * sqrt_pi,
                    f"({i},{j})",
                    fontsize=6.3,
                    color="#1D4ED8",
                    zorder=4,
                )

    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.grid(color="#CBD5E1", alpha=0.45, linewidth=0.6)
    ax.set_xlabel("q quadrature")
    ax.set_ylabel("p quadrature")
    title = "Inner GKP code (indexed phase-space cell)" if indexed else "Inner GKP code (single-mode phase-space cell)"
    ax.set_title(
        title + "\n" + r"Peak spacing $\sqrt{\pi}$; dashed lines indicate digitization boundaries.",
        fontsize=10,
        pad=10,
    )


def _draw_outer_minimap(ax: Any, geom: SurfaceGeometry, *, indexed: bool = False) -> None:
    _draw_panel(
        ax,
        geom,
        show_x=True,
        show_z=True,
        indexed=indexed,
        title="Outer code support graph (indexed)" if indexed else "Outer code support graph",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")


def render_gkp_inner_outer_figures(geom: SurfaceGeometry, out_dir: Path) -> None:
    # Standalone inner-code conceptual figure.
    fig_inner, ax_inner = plt.subplots(figsize=(6.2, 5.5), constrained_layout=True)
    _draw_gkp_phase_space(ax_inner)
    _save_all(fig_inner, out_dir / "figure_gkp_inner_code_phase_space")
    plt.close(fig_inner)

    fig_inner_idx, ax_inner_idx = plt.subplots(figsize=(6.4, 5.7), constrained_layout=True)
    _draw_gkp_phase_space(ax_inner_idx, indexed=True)
    _save_all(fig_inner_idx, out_dir / "figure_gkp_inner_code_phase_space_indexed")
    plt.close(fig_inner_idx)

    # Concatenated schematic: inner GKP -> outer support graph.
    fig_cat, axes = plt.subplots(1, 2, figsize=(12.4, 5.4), constrained_layout=True)
    _draw_gkp_phase_space(axes[0])
    _draw_outer_minimap(axes[1], geom)
    axes[0].set_title("Inner code: GKP digitization space", fontsize=10, pad=10)
    axes[1].set_title("Outer code: support topology", fontsize=10, pad=10)

    # Cross-panel mapping annotation.
    axes[0].annotate(
        "",
        xy=(1.03, 0.5),
        xycoords="axes fraction",
        xytext=(-0.03, 0.5),
        textcoords=axes[1].transAxes,
        arrowprops={"arrowstyle": "->", "color": "#0F172A", "lw": 1.6},
    )
    _save_all(fig_cat, out_dir / "figure_gkp_concatenated_inner_outer")
    plt.close(fig_cat)

    # Indexed concatenated schematic (right panel indexed).
    fig_cat_idx, axes_idx = plt.subplots(1, 2, figsize=(13.2, 6.2), constrained_layout=True)
    _draw_gkp_phase_space(axes_idx[0], indexed=True)
    _draw_outer_minimap(axes_idx[1], geom, indexed=True)
    axes_idx[0].set_title("Inner code: GKP digitization space", fontsize=10, pad=10)
    axes_idx[1].set_title("Outer code: support topology (indexed)", fontsize=10, pad=10)

    axes_idx[0].annotate(
        "",
        xy=(1.03, 0.5),
        xycoords="axes fraction",
        xytext=(-0.03, 0.5),
        textcoords=axes_idx[1].transAxes,
        arrowprops={"arrowstyle": "->", "color": "#0F172A", "lw": 1.6},
    )
    _save_all(fig_cat_idx, out_dir / "figure_gkp_concatenated_inner_outer_indexed")
    plt.close(fig_cat_idx)


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    surface_summary = _load_summary(run_root / "surface/01_generate_comparison_requests/summary_generation.json")
    gkp_summary = _load_summary(run_root / "gkp/01_generate_comparison_requests/summary_generation.json")

    surface_geom = build_surface_geometry(int(surface_summary["distance"]))
    gkp_geom = build_surface_geometry(int(gkp_summary["distance"]))

    render_surface_figures(surface_geom, out_dir)
    render_gkp_figures(gkp_geom, out_dir)
    render_gkp_inner_outer_figures(gkp_geom, out_dir)
    print(f"Wrote 2D syndrome layout figures to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
