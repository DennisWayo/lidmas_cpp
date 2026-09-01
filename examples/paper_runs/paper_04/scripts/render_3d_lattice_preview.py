#!/usr/bin/env python3
"""Render a 3D preview of the indexed outer-code lattice for paper_04."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from generate_comparison_requests import SurfaceGeometry, build_surface_geometry
from render_2d_syndrome_layouts import STYLE, _layout_coords, _ordered_support_points


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        default="examples/paper_runs/paper_04/results/03_analysis/runs/surface/01_generate_comparison_requests/summary_generation.json",
        help="Generation summary JSON used to recover the run distance.",
    )
    parser.add_argument(
        "--out-dir",
        default="examples/paper_runs/paper_04/results/03_analysis/syndrome_layout_figures",
        help="Output directory for the 3D preview figure.",
    )
    return parser.parse_args()


def _load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _patch_3d(points: list[tuple[float, float]], z: float) -> list[tuple[float, float, float]]:
    return [(x, y, z) for x, y in _ordered_support_points(points)]


def render_3d_lattice(geom: SurfaceGeometry, out_dir: Path) -> None:
    data_coords, x_coords, z_coords = _layout_coords(geom)
    fig = plt.figure(figsize=(9.2, 7.2), dpi=320)
    ax = fig.add_subplot(111, projection="3d")

    z_data = 0.0
    z_x = 0.42
    z_z = -0.42
    z_x_patch = 0.18
    z_z_patch = -0.18

    # Stabilizer sheets.
    x_polys = [_patch_3d([data_coords[dq] for dq in support], z_x_patch) for support in geom.x_supports]
    z_polys = [_patch_3d([data_coords[dq] for dq in support], z_z_patch) for support in geom.z_supports]
    ax.add_collection3d(
        Poly3DCollection(x_polys, facecolors=STYLE["x_stab"], edgecolors="none", alpha=0.42, zorder=0)
    )
    ax.add_collection3d(
        Poly3DCollection(z_polys, facecolors=STYLE["z_stab"], edgecolors="none", alpha=0.46, zorder=0)
    )

    # Dashed support links from ancillas to data qubits.
    for x_idx, support in enumerate(geom.x_supports):
        cx, cy = x_coords[x_idx]
        for dq in support:
            qx, qy = data_coords[dq]
            ax.plot(
                [cx, qx],
                [cy, qy],
                [z_x, z_data],
                color=STYLE["support"],
                linewidth=0.8,
                alpha=0.65,
                linestyle=(0, (2.5, 2.5)),
            )

    for z_idx, support in enumerate(geom.z_supports):
        cx, cy = z_coords[z_idx]
        for dq in support:
            qx, qy = data_coords[dq]
            ax.plot(
                [cx, qx],
                [cy, qy],
                [z_z, z_data],
                color=STYLE["support"],
                linewidth=0.8,
                alpha=0.65,
                linestyle=(0, (2.5, 2.5)),
            )

    # Nodes.
    dx = [x for x, _ in data_coords.values()]
    dy = [y for _, y in data_coords.values()]
    ax.scatter(dx, dy, [z_data] * len(dx), s=42, color=STYLE["data"], edgecolors="white", linewidths=0.7, depthshade=False)

    xx = [x for x, _ in x_coords.values()]
    xy = [y for _, y in x_coords.values()]
    ax.scatter(xx, xy, [z_x] * len(xx), s=54, color=STYLE["x"], edgecolors="white", linewidths=0.7, depthshade=False)

    zx = [x for x, _ in z_coords.values()]
    zy = [y for _, y in z_coords.values()]
    ax.scatter(zx, zy, [z_z] * len(zx), s=54, color=STYLE["z"], edgecolors="white", linewidths=0.7, depthshade=False)

    # Sparse labels keep the preview readable in perspective.
    for dq, (x, y) in data_coords.items():
        ax.text(x + 0.03, y + 0.03, z_data + 0.03, f"D{dq}", fontsize=5.0, color=STYLE["data_text"])
    for x_idx, (x, y) in x_coords.items():
        ax.text(x - 0.08, y - 0.06, z_x + 0.04, f"X{x_idx:02d}", fontsize=5.2, color=STYLE["x_text"])
    for z_idx, (x, y) in z_coords.items():
        ax.text(x + 0.03, y + 0.03, z_z - 0.03, f"Z{z_idx:02d}", fontsize=5.2, color=STYLE["z_text"])

    d = geom.distance
    ax.set_xlim(-0.55, d - 1 + 0.55)
    ax.set_ylim(d - 1 + 0.55, -0.55)
    ax.set_zlim(-0.72, 0.72)
    ax.set_box_aspect((1.0, 1.0, 0.34))
    ax.view_init(elev=29, azim=-55)
    ax.set_xlabel("lattice x", labelpad=8)
    ax.set_ylabel("lattice y", labelpad=8)
    ax.set_zlabel("syndrome layer", labelpad=8)
    ax.set_zticks([z_z, z_data, z_x])
    ax.set_zticklabels(["Z", "data", "X"])
    ax.set_title("3D indexed outer-code lattice preview", pad=16)
    ax.grid(alpha=0.16)

    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["data"], markeredgecolor="white", label="Data qubit"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["x"], markeredgecolor="white", label="X ancilla"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=STYLE["z"], markeredgecolor="white", label="Z ancilla"),
        Patch(facecolor=STYLE["x_stab"], edgecolor="none", alpha=0.42, label="X stabilizer sheet"),
        Patch(facecolor=STYLE["z_stab"], edgecolor="none", alpha=0.46, label="Z stabilizer sheet"),
    ]
    fig.legend(handles=legend_handles, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.98), fontsize=9)
    fig.subplots_adjust(top=0.88, left=0.02, right=0.98, bottom=0.02)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_base = out_dir / "figure_3d_lattice_preview"
    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_base.with_suffix(ext), bbox_inches="tight", dpi=320)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    summary = _load_summary(Path(args.summary))
    geom = build_surface_geometry(int(summary["distance"]))
    render_3d_lattice(geom, Path(args.out_dir))
    print(f"Wrote 3D lattice preview to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
