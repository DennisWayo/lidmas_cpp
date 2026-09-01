#!/usr/bin/env python3
"""Generate local paper_05 surface-code Z-check syndrome measurements."""

from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path
from typing import Any

from surface_syndrome import (
    build_surface_geometry,
    cbit_values_to_bitstring,
    experiment_specs,
    expected_syndrome,
    syndrome_from_data_bits,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--distance", type=int, default=5)
    parser.add_argument("--targets", default="representative")
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--measurement-error-rate", type=float, default=0.02)
    parser.add_argument("--background-data-error-rate", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260705)
    return parser.parse_args()


def maybe_flip(bit: int, p: float, rng: random.Random) -> int:
    return bit ^ int(rng.random() < p)


def main() -> int:
    args = parse_args()
    if args.shots <= 0:
        raise SystemExit("Error: --shots must be positive.")
    if not 0.0 <= args.measurement_error_rate <= 1.0:
        raise SystemExit("Error: --measurement-error-rate must be in [0, 1].")
    if not 0.0 <= args.background_data_error_rate <= 1.0:
        raise SystemExit("Error: --background-data-error-rate must be in [0, 1].")

    geom = build_surface_geometry(args.distance)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    experiments: list[dict[str, Any]] = []

    for spec in experiment_specs(args.distance, args.targets):
        counts: collections.Counter[str] = collections.Counter()
        shot_records: list[dict[str, Any]] = []
        for shot in range(args.shots):
            data_bits = [0] * geom.n_data
            if spec.injected_x is not None:
                data_bits[spec.injected_x] ^= 1
            background_flips: list[int] = []
            for idx in range(geom.n_data):
                if rng.random() < args.background_data_error_rate:
                    data_bits[idx] ^= 1
                    background_flips.append(idx)

            ideal_syndrome = syndrome_from_data_bits(geom, data_bits)
            measured_syndrome = [maybe_flip(bit, args.measurement_error_rate, rng) for bit in ideal_syndrome]
            measured_data = [maybe_flip(bit, args.measurement_error_rate, rng) for bit in data_bits]
            bitstring = cbit_values_to_bitstring([*measured_syndrome, *measured_data])
            counts[bitstring] += 1
            shot_records.append(
                {
                    "shot_index": shot,
                    "bitstring": bitstring,
                    "measured_syndrome": measured_syndrome,
                    "measured_data": measured_data,
                    "ideal_syndrome": ideal_syndrome,
                    "background_flips": background_flips,
                }
            )

        experiments.append(
            {
                "circuit_id": spec.circuit_id,
                "label": spec.label,
                "injected_x": spec.injected_x,
                "expected_syndrome": expected_syndrome(geom, spec.injected_x),
                "counts": dict(sorted(counts.items())),
                "shot_records": shot_records,
            }
        )

    payload = {
        "schema": "paper05_surface_results_v1",
        "source": "local_simulator",
        "backend": "local_surface_z_sampler",
        "job_id": f"local-surface-d{args.distance}-{args.seed}",
        "code_family": "surface",
        "code_name": f"surface_d{args.distance}_z_checks",
        "distance": args.distance,
        "shots": args.shots,
        "n_data": geom.n_data,
        "n_checks": geom.n_z,
        "measurement_error_rate": args.measurement_error_rate,
        "background_data_error_rate": args.background_data_error_rate,
        "seed": args.seed,
        "experiments": experiments,
    }
    out_path = out_dir / "local_surface_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote local surface-code results to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
