#!/usr/bin/env python3
"""Build the paper_05 digitized-GKP model metadata."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from gkp_digitized_syndrome import SQRT_PI, experiment_specs, expected_syndrome
from surface_syndrome import build_surface_geometry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--distance", type=int, default=5)
    parser.add_argument("--targets", default="representative")
    parser.add_argument("--decision-width-scale", type=float, default=0.25)
    parser.add_argument("--injected-shift-scale", type=float, default=0.56)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    geom = build_surface_geometry(args.distance)
    specs = experiment_specs(args.distance, args.targets)
    target_rows = []
    for spec in specs:
        target_rows.append(
            {
                "circuit_id": spec.circuit_id,
                "label": spec.label,
                "injected_q": "" if spec.injected_q is None else spec.injected_q,
                "expected_z_syndrome": "".join(str(bit) for bit in expected_syndrome(geom, spec.injected_q)),
            }
        )

    payload = {
        "schema": "paper05_digitized_gkp_model_v1",
        "code_family": "digitized_gkp",
        "code_name": f"digitized_gkp_surface_d{args.distance}_z_checks",
        "distance": args.distance,
        "n_gkp_modes": geom.n_data,
        "n_x_checks_outer": geom.n_x,
        "n_z_checks_outer": geom.n_z,
        "sqrt_pi": SQRT_PI,
        "decision_width": args.decision_width_scale * SQRT_PI,
        "decision_width_scale": args.decision_width_scale,
        "injected_shift": args.injected_shift_scale * SQRT_PI,
        "injected_shift_scale": args.injected_shift_scale,
        "outer_z_supports": geom.z_supports,
        "targets": target_rows,
        "interpretation": (
            "PennyLane-backed digitized-GKP companion model. Gaussian-CV q-readout "
            "samples and analog q-shifts are binned into Z-check syndrome bits on "
            "the outer distance-d surface graph."
        ),
    }

    with (out_dir / "gkp_digitized_model.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    with (out_dir / "table_gkp_digitized_targets.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["circuit_id", "label", "injected_q", "expected_z_syndrome"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(target_rows)
    print(f"Wrote digitized-GKP model metadata to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
