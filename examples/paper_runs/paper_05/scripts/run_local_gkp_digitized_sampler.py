#!/usr/bin/env python3
"""Sample PennyLane-backed digitized-GKP syndrome records for paper_05."""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import random
from pathlib import Path
from typing import Any

from gkp_digitized_syndrome import (
    SQRT_PI,
    apply_shift_noise,
    cbit_values_to_bitstring,
    digitized_data_bits,
    experiment_specs,
    expected_syndrome,
    z_syndrome_from_q_shifts,
)
from surface_syndrome import build_surface_geometry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--distance", type=int, default=5)
    parser.add_argument("--targets", default="representative")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--sigma-shift-scale", type=float, default=0.015)
    parser.add_argument("--measurement-error-rate", type=float, default=0.01)
    parser.add_argument("--jump-prob", type=float, default=0.001)
    parser.add_argument("--jump-scale", type=float, default=0.5)
    parser.add_argument("--decision-width-scale", type=float, default=0.25)
    parser.add_argument("--injected-shift-scale", type=float, default=0.56)
    parser.add_argument("--seed", type=int, default=20260706)
    parser.add_argument(
        "--pennylane-mode",
        choices=("required", "auto", "disabled"),
        default="required",
        help="Use PennyLane default.gaussian for finite-squeezed q-readout noise.",
    )
    parser.add_argument(
        "--pennylane-squeeze-r",
        type=float,
        default=2.0,
        help="Single-mode squeezing parameter used by the PennyLane Gaussian readout proxy.",
    )
    parser.add_argument(
        "--pennylane-noise-scale",
        type=float,
        default=1.0,
        help="Scale applied to PennyLane QuadX samples before adding them to q-shifts.",
    )
    return parser.parse_args()


def _validate_probability(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise SystemExit(f"Error: --{name} must be in [0, 1].")


def _load_pennylane(mode: str) -> tuple[Any | None, str]:
    if mode == "disabled":
        return None, ""
    try:
        import numpy as np  # type: ignore
        import pennylane as qml  # type: ignore
    except Exception as exc:
        if mode == "required":
            raise SystemExit(
                "Error: PennyLane is required for this sampler. Install with: pip install pennylane"
            ) from exc
        print(
            "Warning: PennyLane unavailable; falling back to deterministic local digitization.",
            file=sys.stderr,
        )
        return None, ""
    return (qml, np), str(getattr(qml, "__version__", "unknown"))


def _build_quadx_noise_sampler(
    *,
    qml_np: Any | None,
    shots: int,
    squeeze_r: float,
    noise_scale: float,
    seed: int,
) -> tuple[Any, dict[str, Any]]:
    if qml_np is None:
        def local_noise() -> list[float]:
            return [0.0] * shots

        return local_noise, {
            "enabled": False,
            "device": "",
            "squeeze_r": "",
            "noise_scale": "",
        }

    qml, np = qml_np
    np.random.seed(seed + 7919)
    dev = qml.device("default.gaussian", wires=1)

    @qml.set_shots(shots=shots)
    @qml.qnode(dev)
    def sample_zero_mean_quadx():
        qml.SqueezedState(squeeze_r, 0.0, wires=0)
        return qml.sample(qml.QuadX(0))

    def pennylane_noise() -> list[float]:
        raw = sample_zero_mean_quadx()
        return [float(value) * noise_scale for value in raw]

    return pennylane_noise, {
        "enabled": True,
        "device": "default.gaussian",
        "squeeze_r": squeeze_r,
        "noise_scale": noise_scale,
    }


def main() -> int:
    args = parse_args()
    if args.shots <= 0:
        raise SystemExit("Error: --shots must be positive.")
    if args.rounds <= 0:
        raise SystemExit("Error: --rounds must be positive.")
    _validate_probability("measurement-error-rate", args.measurement_error_rate)
    _validate_probability("jump-prob", args.jump_prob)
    if not math.isfinite(args.pennylane_squeeze_r):
        raise SystemExit("Error: --pennylane-squeeze-r must be finite.")
    if not math.isfinite(args.pennylane_noise_scale) or args.pennylane_noise_scale < 0.0:
        raise SystemExit("Error: --pennylane-noise-scale must be finite and non-negative.")

    geom = build_surface_geometry(args.distance)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    qml_np, pennylane_version = _load_pennylane(args.pennylane_mode)
    quadx_noise, pennylane_meta = _build_quadx_noise_sampler(
        qml_np=qml_np,
        shots=args.shots,
        squeeze_r=args.pennylane_squeeze_r,
        noise_scale=args.pennylane_noise_scale,
        seed=args.seed,
    )
    sigma_shift = args.sigma_shift_scale * SQRT_PI
    jump_scale = args.jump_scale * SQRT_PI
    injected_shift = args.injected_shift_scale * SQRT_PI
    decision_width = args.decision_width_scale * SQRT_PI
    experiments: list[dict[str, Any]] = []

    for spec in experiment_specs(args.distance, args.targets):
        counts: collections.Counter[str] = collections.Counter()
        shot_records: list[dict[str, Any]] = []
        q_shift_by_shot = [[0.0] * geom.n_data for _ in range(args.shots)]
        p_shift_by_shot = [[0.0] * geom.n_data for _ in range(args.shots)]
        for q_shift in q_shift_by_shot:
            if spec.injected_q is not None:
                q_shift[spec.injected_q] += injected_shift

        round_syndromes_by_shot: list[list[str]] = [[] for _ in range(args.shots)]
        final_syndromes: list[list[int]] = [[0] * geom.n_z for _ in range(args.shots)]
        final_analog_values: list[list[float]] = [[0.0] * geom.n_z for _ in range(args.shots)]
        final_data_bits: list[list[int]] = [[0] * geom.n_data for _ in range(args.shots)]

        for round_index in range(args.rounds):
            readout_noise_by_mode = [quadx_noise() for _ in range(geom.n_data)]
            for shot in range(args.shots):
                q_shift = q_shift_by_shot[shot]
                p_shift = p_shift_by_shot[shot]
                apply_shift_noise(
                    q_shift,
                    p_shift,
                    sigma_shift=sigma_shift,
                    jump_prob=args.jump_prob,
                    jump_scale=jump_scale,
                    rng=rng,
                )
                q_readout = [q_shift[idx] + readout_noise_by_mode[idx][shot] for idx in range(geom.n_data)]
                measured_syndrome, analog_values = z_syndrome_from_q_shifts(
                    geom,
                    q_readout,
                    decision_width=decision_width,
                    measurement_error_rate=args.measurement_error_rate,
                    rng=rng,
                )
                round_syndromes_by_shot[shot].append("".join(str(bit) for bit in measured_syndrome))
                if round_index == args.rounds - 1:
                    final_syndromes[shot] = measured_syndrome
                    final_analog_values[shot] = analog_values
                    final_data_bits[shot] = digitized_data_bits(q_readout, decision_width=decision_width)

        for shot in range(args.shots):
            bitstring = cbit_values_to_bitstring([*final_syndromes[shot], *final_data_bits[shot]])
            counts[bitstring] += 1
            shot_records.append(
                {
                    "shot_index": shot,
                    "bitstring": bitstring,
                    "measured_syndrome": final_syndromes[shot],
                    "digitized_data": final_data_bits[shot],
                    "analog_z_values": [round(value, 8) for value in final_analog_values[shot]],
                    "round_syndromes": round_syndromes_by_shot[shot],
                }
            )

        experiments.append(
            {
                "circuit_id": spec.circuit_id,
                "label": spec.label,
                "injected_q": spec.injected_q,
                "expected_syndrome": expected_syndrome(geom, spec.injected_q),
                "counts": dict(sorted(counts.items())),
                "shot_records": shot_records,
            }
        )

    payload = {
        "schema": "paper05_digitized_gkp_results_v1",
        "source": "digitized_gkp_pennylane" if pennylane_meta["enabled"] else "digitized_gkp_local",
        "backend": (
            "pennylane_default_gaussian_digitized_gkp"
            if pennylane_meta["enabled"]
            else "local_digitized_gkp_sampler"
        ),
        "job_id": (
            f"pennylane-gkp-d{args.distance}-{args.seed}"
            if pennylane_meta["enabled"]
            else f"local-gkp-d{args.distance}-{args.seed}"
        ),
        "code_family": "digitized_gkp",
        "code_name": f"digitized_gkp_surface_d{args.distance}_z_checks",
        "distance": args.distance,
        "shots": args.shots,
        "rounds": args.rounds,
        "n_data": geom.n_data,
        "n_checks": geom.n_z,
        "sigma_shift": sigma_shift,
        "sigma_shift_scale": args.sigma_shift_scale,
        "measurement_error_rate": args.measurement_error_rate,
        "jump_prob": args.jump_prob,
        "jump_scale": jump_scale,
        "jump_scale_pi": args.jump_scale,
        "decision_width": decision_width,
        "decision_width_scale": args.decision_width_scale,
        "injected_shift": injected_shift,
        "injected_shift_scale": args.injected_shift_scale,
        "seed": args.seed,
        "pennylane_enabled": bool(pennylane_meta["enabled"]),
        "pennylane_version": pennylane_version,
        "pennylane_device": pennylane_meta["device"],
        "pennylane_squeeze_r": pennylane_meta["squeeze_r"],
        "pennylane_noise_scale": pennylane_meta["noise_scale"],
        "interpretation": (
            "PennyLane default.gaussian finite-squeezed q-readout proxy with classical "
            "GKP displacement noise and modular outer-code binning."
            if pennylane_meta["enabled"]
            else "Local deterministic digitized-GKP fallback without PennyLane quadrature readout."
        ),
        "experiments": experiments,
    }
    out_path = out_dir / "local_gkp_digitized_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    source_label = "PennyLane-backed" if pennylane_meta["enabled"] else "local"
    print(f"Wrote {source_label} digitized-GKP results to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
