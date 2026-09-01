#!/usr/bin/env python3
"""Shared repetition-code helpers for paper_05."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExperimentSpec:
    circuit_id: str
    injected_x: int | None
    label: str


def sanitize_label(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    clean = clean.strip("_")
    return clean or "dataset"


def parse_targets(targets: str, n_data: int) -> list[int | None]:
    value = targets.strip().lower()
    if value in {"all", "all_injected"}:
        return [None, *range(n_data)]
    if value in {"middle", "mid"}:
        return [None, n_data // 2]
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
        if idx < 0 or idx >= n_data:
            raise ValueError(f"target index {idx} outside [0, {n_data - 1}]")
        out.append(idx)
    return out


def experiment_specs(n_data: int, targets: str) -> list[ExperimentSpec]:
    specs: list[ExperimentSpec] = []
    seen: set[int | None] = set()
    for target in parse_targets(targets, n_data):
        if target in seen:
            continue
        seen.add(target)
        if target is None:
            specs.append(ExperimentSpec(circuit_id="clean", injected_x=None, label="clean"))
        else:
            specs.append(ExperimentSpec(circuit_id=f"x_data_{target}", injected_x=target, label=f"X on data {target}"))
    return specs


def expected_syndrome(n_data: int, injected_x: int | None) -> list[int]:
    syndrome = [0] * (n_data - 1)
    if injected_x is None:
        return syndrome
    if injected_x > 0:
        syndrome[injected_x - 1] ^= 1
    if injected_x < n_data - 1:
        syndrome[injected_x] ^= 1
    return syndrome


def syndrome_from_data_bits(data_bits: list[int]) -> list[int]:
    return [(data_bits[i] ^ data_bits[i + 1]) & 1 for i in range(len(data_bits) - 1)]


def cbit_values_to_bitstring(cbits_low_to_high: list[int]) -> str:
    return "".join(str(int(v) & 1) for v in reversed(cbits_low_to_high))


def parse_bitstring(bitstring: str, n_data: int) -> tuple[list[int], list[int]]:
    compact = bitstring.replace(" ", "").strip()
    n_checks = n_data - 1
    expected = n_checks + n_data
    if len(compact) != expected:
        raise ValueError(f"bitstring length {len(compact)} does not match expected {expected}: {bitstring!r}")
    c_low_to_high = [int(ch) for ch in reversed(compact)]
    syndrome = c_low_to_high[:n_checks]
    data = c_low_to_high[n_checks : n_checks + n_data]
    return syndrome, data


def syndrome_to_events(syndrome: list[int], *, time_ns: int = 1000) -> list[dict[str, Any]]:
    return [
        {"index": idx, "time_ns": time_ns, "type": "Z"}
        for idx, bit in enumerate(syndrome)
        if bit & 1
    ]


def decode_min_weight(syndrome: list[int], n_data: int) -> list[int]:
    """Return minimum-Hamming-weight data-bit correction matching a repetition syndrome."""
    target = [bit & 1 for bit in syndrome]
    best: tuple[int, tuple[int, ...]] | None = None
    for bits in itertools.product((0, 1), repeat=n_data):
        if syndrome_from_data_bits(list(bits)) != target:
            continue
        weight = sum(bits)
        if best is None or (weight, bits) < best:
            best = (weight, bits)
    if best is None:
        return []
    return [idx for idx, bit in enumerate(best[1]) if bit]


def correction_syndrome(correction_indices: list[int], n_data: int) -> list[int]:
    bits = [0] * n_data
    for idx in correction_indices:
        if 0 <= idx < n_data:
            bits[idx] ^= 1
    return syndrome_from_data_bits(bits)


def build_qiskit_circuit(n_data: int, spec: ExperimentSpec) -> Any:
    try:
        from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only when qiskit is absent
        raise SystemExit(
            "Qiskit is required to build the paper_05 circuit artifacts. "
            "Install qiskit or run inside the project .venv."
        ) from exc

    n_checks = n_data - 1
    data = QuantumRegister(n_data, "d")
    anc = QuantumRegister(n_checks, "a")
    meas = ClassicalRegister(n_checks + n_data, "meas")
    qc = QuantumCircuit(data, anc, meas, name=spec.circuit_id)

    if spec.injected_x is not None:
        qc.x(data[spec.injected_x])
        qc.barrier(data)

    for idx in range(n_checks):
        qc.cx(data[idx], anc[idx])
        qc.cx(data[idx + 1], anc[idx])

    qc.barrier(data, anc)
    for idx in range(n_checks):
        qc.measure(anc[idx], meas[idx])
    for idx in range(n_data):
        qc.measure(data[idx], meas[n_checks + idx])
    return qc


def circuit_metadata(n_data: int, spec: ExperimentSpec) -> dict[str, Any]:
    return {
        "circuit_id": spec.circuit_id,
        "label": spec.label,
        "n_data": n_data,
        "n_checks": n_data - 1,
        "injected_x": "" if spec.injected_x is None else spec.injected_x,
        "expected_syndrome": "".join(str(bit) for bit in expected_syndrome(n_data, spec.injected_x)),
        "classical_bit_order": "low-to-high: syndrome[0..n_checks-1], data[0..n_data-1]",
        "bitstring_order": "Qiskit count keys are parsed as high-to-low classical bits.",
    }
