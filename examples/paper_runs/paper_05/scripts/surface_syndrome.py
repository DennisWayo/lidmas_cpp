#!/usr/bin/env python3
"""Distance-d surface-code Z-check syndrome helpers for paper_05."""

from __future__ import annotations

import collections
import functools
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SurfaceGeometry:
    distance: int
    n_data: int
    n_x: int
    n_z: int
    x_supports: list[list[int]]
    z_supports: list[list[int]]


@dataclass(frozen=True)
class ExperimentSpec:
    circuit_id: str
    injected_x: int | None
    label: str


def sanitize_label(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    clean = clean.strip("_")
    return clean or "dataset"


def build_surface_geometry(distance: int) -> SurfaceGeometry:
    if distance < 3 or (distance % 2) == 0:
        raise ValueError("surface-code distance must be odd and >= 3")

    d = distance
    n_data = 2 * d * (d - 1)
    n_x = d * d
    n_z = (d - 1) * (d - 1)

    def h_index(x: int, y: int) -> int:
        return y * (d - 1) + x

    def v_index(x: int, y: int) -> int:
        h_count = d * (d - 1)
        return h_count + y * d + x

    x_supports: list[list[int]] = []
    for y in range(d):
        for x in range(d):
            support: list[int] = []
            if x > 0:
                support.append(h_index(x - 1, y))
            if x < d - 1:
                support.append(h_index(x, y))
            if y > 0:
                support.append(v_index(x, y - 1))
            if y < d - 1:
                support.append(v_index(x, y))
            x_supports.append(support)

    z_supports: list[list[int]] = []
    for y in range(d - 1):
        for x in range(d - 1):
            z_supports.append(
                [
                    h_index(x, y),
                    h_index(x, y + 1),
                    v_index(x, y),
                    v_index(x + 1, y),
                ]
            )

    return SurfaceGeometry(
        distance=d,
        n_data=n_data,
        n_x=n_x,
        n_z=n_z,
        x_supports=x_supports,
        z_supports=z_supports,
    )


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
    if value in {"all_unique", "unique"}:
        out: list[int | None] = [None]
        seen: set[tuple[int, ...]] = set()
        for q in range(geom.n_data):
            syndrome = tuple(i for i, support in enumerate(geom.z_supports) if q in support)
            if syndrome in seen:
                continue
            seen.add(syndrome)
            out.append(q)
        return out
    if value in {"middle", "mid"}:
        return [None, geom.n_data // 2]
    if value in {"clean", "none"}:
        return [None]

    out = [None]
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
            specs.append(ExperimentSpec(circuit_id="clean", injected_x=None, label="clean"))
        else:
            specs.append(ExperimentSpec(circuit_id=f"x_data_{target}", injected_x=target, label=f"X on data {target}"))
    return specs


def syndrome_from_data_bits(geom: SurfaceGeometry, data_bits: list[int]) -> list[int]:
    syndrome: list[int] = []
    for support in geom.z_supports:
        parity = 0
        for q in support:
            parity ^= data_bits[q] & 1
        syndrome.append(parity)
    return syndrome


def expected_syndrome(geom: SurfaceGeometry, injected_x: int | None) -> list[int]:
    data_bits = [0] * geom.n_data
    if injected_x is not None:
        data_bits[injected_x] = 1
    return syndrome_from_data_bits(geom, data_bits)


def cbit_values_to_bitstring(cbits_low_to_high: list[int]) -> str:
    return "".join(str(int(v) & 1) for v in reversed(cbits_low_to_high))


def parse_bitstring(bitstring: str, geom: SurfaceGeometry) -> tuple[list[int], list[int]]:
    compact = bitstring.replace(" ", "").strip()
    expected = geom.n_z + geom.n_data
    if len(compact) != expected:
        raise ValueError(f"bitstring length {len(compact)} does not match expected {expected}: {bitstring!r}")
    c_low_to_high = [int(ch) for ch in reversed(compact)]
    syndrome = c_low_to_high[: geom.n_z]
    data = c_low_to_high[geom.n_z : geom.n_z + geom.n_data]
    return syndrome, data


def syndrome_to_events(syndrome: list[int], *, time_ns: int = 1000) -> list[dict[str, Any]]:
    return [{"index": idx, "time_ns": time_ns, "type": "Z"} for idx, bit in enumerate(syndrome) if bit & 1]


def syndrome_to_int(syndrome: list[int]) -> int:
    value = 0
    for idx, bit in enumerate(syndrome):
        if bit & 1:
            value |= 1 << idx
    return value


def int_to_syndrome(value: int, n_checks: int) -> list[int]:
    return [(value >> idx) & 1 for idx in range(n_checks)]


def _column_masks(geom: SurfaceGeometry) -> list[int]:
    masks: list[int] = []
    for q in range(geom.n_data):
        bits = [0] * geom.n_z
        for idx, support in enumerate(geom.z_supports):
            if q in support:
                bits[idx] = 1
        masks.append(syndrome_to_int(bits))
    return masks


@functools.cache
def _decoder_table(distance: int) -> tuple[tuple[int, ...], ...]:
    geom = build_surface_geometry(distance)
    n_states = 1 << geom.n_z
    columns = _column_masks(geom)
    corrections: list[tuple[int, ...] | None] = [None] * n_states
    corrections[0] = ()
    queue: collections.deque[int] = collections.deque([0])

    while queue:
        state = queue.popleft()
        current = corrections[state]
        if current is None:
            continue
        for q, mask in enumerate(columns):
            next_state = state ^ mask
            candidate = tuple(sorted((*current, q)))
            if corrections[next_state] is None or (len(candidate), candidate) < (len(corrections[next_state]), corrections[next_state]):
                corrections[next_state] = candidate
                queue.append(next_state)

    return tuple(c if c is not None else () for c in corrections)


def decode_min_weight(geom: SurfaceGeometry, syndrome: list[int]) -> list[int]:
    table = _decoder_table(geom.distance)
    return list(table[syndrome_to_int(syndrome)])


def correction_syndrome(geom: SurfaceGeometry, correction_indices: list[int]) -> list[int]:
    bits = [0] * geom.n_data
    for idx in correction_indices:
        if 0 <= idx < geom.n_data:
            bits[idx] ^= 1
    return syndrome_from_data_bits(geom, bits)


def build_qiskit_circuit(distance: int, spec: ExperimentSpec) -> Any:
    try:
        from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional environment
        raise SystemExit("Qiskit is required to build surface-code syndrome circuits.") from exc

    geom = build_surface_geometry(distance)
    data = QuantumRegister(geom.n_data, "d")
    anc = QuantumRegister(geom.n_z, "z")
    meas = ClassicalRegister(geom.n_z + geom.n_data, "meas")
    qc = QuantumCircuit(data, anc, meas, name=spec.circuit_id)

    if spec.injected_x is not None:
        qc.x(data[spec.injected_x])
        qc.barrier(data)

    for check_idx, support in enumerate(geom.z_supports):
        for data_idx in support:
            qc.cx(data[data_idx], anc[check_idx])

    qc.barrier(data, anc)
    for idx in range(geom.n_z):
        qc.measure(anc[idx], meas[idx])
    for idx in range(geom.n_data):
        qc.measure(data[idx], meas[geom.n_z + idx])
    return qc


def circuit_metadata(distance: int, spec: ExperimentSpec) -> dict[str, Any]:
    geom = build_surface_geometry(distance)
    return {
        "circuit_id": spec.circuit_id,
        "label": spec.label,
        "code_family": "surface",
        "code_name": f"surface_d{distance}_z_checks",
        "distance": distance,
        "n_data": geom.n_data,
        "n_x_checks": geom.n_x,
        "n_checks": geom.n_z,
        "injected_x": "" if spec.injected_x is None else spec.injected_x,
        "expected_syndrome": "".join(str(bit) for bit in expected_syndrome(geom, spec.injected_x)),
        "check_type": "Z",
        "classical_bit_order": "low-to-high: z_syndrome[0..n_z-1], data[0..n_data-1]",
        "bitstring_order": "Qiskit count keys are parsed as high-to-low classical bits.",
    }
