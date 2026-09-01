#!/usr/bin/env python3
"""Digitized-GKP helper functions for paper_05.

The model used here is an off-hardware digitized companion to the IBM hardware runs.
Each data site is interpreted as a GKP oscillator mode. Small analog q-shifts
are accumulated, digitized through a square-lattice GKP cell, and mapped onto
the Z-check layer of the same outer surface-code incidence graph used by the
surface branch.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Any

from surface_syndrome import SurfaceGeometry, build_surface_geometry, expected_syndrome as surface_expected_syndrome


SQRT_PI = math.sqrt(math.pi)


@dataclass(frozen=True)
class ExperimentSpec:
    circuit_id: str
    injected_q: int | None
    label: str


def sanitize_label(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    clean = clean.strip("_")
    return clean or "dataset"


def _representative_targets(geom: SurfaceGeometry) -> list[int]:
    if geom.distance == 5:
        return [1, 5, 10, 14, 17, 22, 32, 37]
    out: list[int] = []
    seen: set[tuple[int, ...]] = set()
    for q in range(geom.n_data):
        syndrome = tuple(i for i, support in enumerate(geom.z_supports) if q in support)
        if syndrome in seen:
            continue
        seen.add(syndrome)
        out.append(q)
        if len(out) >= min(8, geom.n_data):
            break
    return out


def parse_targets(targets: str, geom: SurfaceGeometry) -> list[int | None]:
    value = targets.strip().lower()
    if value in {"representative", "rep", "selected"}:
        return [None, *_representative_targets(geom)]
    if value in {"all", "all_injected"}:
        return [None, *range(geom.n_data)]
    if value in {"middle", "mid"}:
        return [None, geom.n_data // 2]
    if value in {"clean", "none"}:
        return [None]

    out: list[int | None] = [None]
    for part in targets.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in {"clean", "none"}:
            continue
        idx = int(part)
        if idx < 0 or idx >= geom.n_data:
            raise ValueError(f"target index {idx} outside [0, {geom.n_data - 1}]")
        out.append(idx)
    return out


def experiment_specs(distance: int, targets: str) -> list[ExperimentSpec]:
    geom = build_surface_geometry(distance)
    specs: list[ExperimentSpec] = []
    seen: set[int | None] = set()
    for target in parse_targets(targets, geom):
        if target in seen:
            continue
        seen.add(target)
        if target is None:
            specs.append(ExperimentSpec(circuit_id="clean", injected_q=None, label="clean"))
        else:
            specs.append(
                ExperimentSpec(
                    circuit_id=f"q_shift_data_{target}",
                    injected_q=target,
                    label=f"q shift on data {target}",
                )
            )
    return specs


def digitize_periodic(value: float, *, period: float = SQRT_PI, width: float = 0.25 * SQRT_PI, bias: float = 0.0) -> int:
    """Return the binary bin for a periodic square-lattice GKP decision cell."""
    if period <= 0.0:
        return 0
    shifted = value + bias
    wrapped = (shifted + 0.5 * period) % period - 0.5 * period
    return int(abs(wrapped) > width)


def apply_shift_noise(
    q_shift: list[float],
    p_shift: list[float],
    *,
    sigma_shift: float,
    jump_prob: float,
    jump_scale: float,
    rng: random.Random,
) -> None:
    for idx in range(len(q_shift)):
        q_shift[idx] += rng.gauss(0.0, sigma_shift)
        p_shift[idx] += rng.gauss(0.0, sigma_shift)
        if rng.random() < jump_prob:
            q_shift[idx] += jump_scale if rng.random() < 0.5 else -jump_scale
        if rng.random() < jump_prob:
            p_shift[idx] += jump_scale if rng.random() < 0.5 else -jump_scale


def z_syndrome_from_q_shifts(
    geom: SurfaceGeometry,
    q_shift: list[float],
    *,
    decision_width: float = 0.25 * SQRT_PI,
    measurement_error_rate: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[list[int], list[float]]:
    syndrome: list[int] = []
    analog_values: list[float] = []
    for support in geom.z_supports:
        scale = math.sqrt(float(len(support))) if support else 1.0
        value = sum(q_shift[q] for q in support) / scale
        bit = digitize_periodic(value, width=decision_width)
        if rng is not None and rng.random() < measurement_error_rate:
            bit ^= 1
        syndrome.append(bit)
        analog_values.append(value)
    return syndrome, analog_values


def expected_syndrome(geom: SurfaceGeometry, injected_q: int | None) -> list[int]:
    return surface_expected_syndrome(geom, injected_q)


def syndrome_to_events(syndrome: list[int], *, time_ns: int = 1000) -> list[dict[str, Any]]:
    return [{"index": idx, "time_ns": time_ns, "type": "Z"} for idx, bit in enumerate(syndrome) if bit & 1]


def digitized_data_bits(q_shift: list[float], *, decision_width: float = 0.25 * SQRT_PI) -> list[int]:
    return [digitize_periodic(value, width=decision_width) for value in q_shift]


def cbit_values_to_bitstring(cbits_low_to_high: list[int]) -> str:
    return "".join(str(int(v) & 1) for v in reversed(cbits_low_to_high))
