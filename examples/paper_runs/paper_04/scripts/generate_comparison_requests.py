#!/usr/bin/env python3
"""Generate paper_04 decoder_io request streams from repeated-round surface-code circuits."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class SurfaceGeometry:
    distance: int
    n_data: int
    n_x: int
    n_z: int
    x_supports: list[list[int]]
    z_supports: list[list[int]]


RoundSampler = Callable[[list[int], list[int]], tuple[list[int], list[int]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument(
        "--code-family",
        choices=("surface", "gkp"),
        default="surface",
        help="Code family for request generation.",
    )
    parser.add_argument("--shots", type=int, default=2500, help="Number of request lines per dataset.")
    parser.add_argument("--distance", type=int, default=5, help="Surface-code distance (odd, >=3).")
    parser.add_argument(
        "--rounds",
        type=int,
        default=4,
        help="Number of repeated stabilizer-measurement rounds per request.",
    )
    parser.add_argument(
        "--n-qubits",
        type=int,
        default=0,
        help="Optional compatibility field. If set and mismatched, derived geometry value is used.",
    )
    parser.add_argument(
        "--n-syndrome",
        type=int,
        default=0,
        help="Optional legacy field. Ignored; geometry determines check counts.",
    )
    parser.add_argument("--error-rate", type=float, default=0.08, help="Base data noise rate.")
    parser.add_argument("--sigma", type=float, default=0.18, help="Sigma value in request noise metadata.")
    parser.add_argument("--seed", type=int, default=20260409, help="RNG seed.")
    parser.add_argument(
        "--emit-x-events",
        type=int,
        choices=(0, 1),
        default=0,
        help="Whether to export X-type detector events to decoder_io (default: 0).",
    )
    parser.add_argument(
        "--emit-z-events",
        type=int,
        choices=(0, 1),
        default=1,
        help="Whether to export Z-type detector events to decoder_io (default: 1).",
    )
    parser.add_argument(
        "--pennylane-mode",
        choices=("auto", "required", "disabled"),
        default="auto",
        help="auto: use PennyLane if available; required: fail if unavailable; disabled: synthetic fallback only.",
    )
    parser.add_argument(
        "--qiskit-mode",
        choices=("auto", "required", "disabled"),
        default="auto",
        help="auto: use Qiskit if available; required: fail if unavailable; disabled: synthetic fallback only.",
    )
    parser.add_argument(
        "--cirq-mode",
        choices=("auto", "required", "disabled"),
        default="auto",
        help="auto: use Cirq if available; required: fail if unavailable; disabled: synthetic fallback only.",
    )
    return parser.parse_args()


def build_surface_geometry(distance: int) -> SurfaceGeometry:
    if distance < 3 or (distance % 2) == 0:
        raise SystemExit("Error: --distance must be odd and >= 3.")

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
            support = [
                h_index(x, y),
                h_index(x, y + 1),
                v_index(x, y),
                v_index(x + 1, y),
            ]
            z_supports.append(support)

    return SurfaceGeometry(
        distance=d,
        n_data=n_data,
        n_x=n_x,
        n_z=n_z,
        x_supports=x_supports,
        z_supports=z_supports,
    )


def _load_pennylane(mode: str) -> tuple[Any | None, bool]:
    if mode == "disabled":
        return None, False
    try:
        import pennylane as qml  # type: ignore
    except Exception:
        if mode == "required":
            raise SystemExit(
                "Error: PennyLane not found, but --pennylane-mode=required was set. "
                "Install with: pip install pennylane"
            )
        return None, False
    return qml, True


def _load_qiskit(mode: str) -> tuple[Any | None, Any | None, bool]:
    if mode == "disabled":
        return None, None, False
    try:
        from qiskit import QuantumCircuit  # type: ignore
        from qiskit.quantum_info import StabilizerState  # type: ignore
    except Exception:
        if mode == "required":
            raise SystemExit(
                "Error: Qiskit not found, but --qiskit-mode=required was set. "
                "Install with: pip install qiskit"
            )
        return None, None, False
    return QuantumCircuit, StabilizerState, True


def _load_cirq(mode: str) -> tuple[Any | None, bool]:
    if mode == "disabled":
        return None, False
    try:
        import cirq  # type: ignore
    except Exception:
        if mode == "required":
            raise SystemExit(
                "Error: Cirq not found, but --cirq-mode=required was set. "
                "Install with: pip install cirq"
            )
        return None, False
    return cirq, True


def _build_classical_round_sampler(geom: SurfaceGeometry) -> RoundSampler:
    def sampler(x_bits: list[int], z_bits: list[int]) -> tuple[list[int], list[int]]:
        sx = [0] * geom.n_x
        sz = [0] * geom.n_z
        for i, support in enumerate(geom.x_supports):
            parity = 0
            for q in support:
                parity ^= (z_bits[q] & 1)
            sx[i] = parity
        for i, support in enumerate(geom.z_supports):
            parity = 0
            for q in support:
                parity ^= (x_bits[q] & 1)
            sz[i] = parity
        return sx, sz

    return sampler


def _build_pennylane_round_sampler(qml: Any, geom: SurfaceGeometry) -> RoundSampler:
    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x
    dev = qml.device("default.clifford", wires=n_total)

    @qml.set_shots(shots=1)
    @qml.qnode(dev)
    def circuit(x_bits, z_bits):
        for i in range(geom.n_data):
            if int(x_bits[i]) & 1:
                qml.PauliX(i)
            if int(z_bits[i]) & 1:
                qml.PauliZ(i)

        for c_idx, support in enumerate(geom.x_supports):
            anc = x_offset + c_idx
            qml.Hadamard(anc)
            for dq in support:
                qml.CNOT(wires=[anc, dq])
            qml.Hadamard(anc)

        for c_idx, support in enumerate(geom.z_supports):
            anc = z_offset + c_idx
            for dq in support:
                qml.CNOT(wires=[dq, anc])

        measures = [qml.sample(qml.PauliZ(x_offset + i)) for i in range(geom.n_x)]
        measures.extend(qml.sample(qml.PauliZ(z_offset + i)) for i in range(geom.n_z))
        return measures

    def sampler(x_bits: list[int], z_bits: list[int]) -> tuple[list[int], list[int]]:
        raw = circuit(tuple(x_bits), tuple(z_bits))
        vals: list[int] = []
        for item in raw:
            v = item
            if hasattr(v, "item"):
                v = v.item()
            iv = int(v)
            vals.append(0 if iv == 1 else 1)
        sx = vals[: geom.n_x]
        sz = vals[geom.n_x :]
        return sx, sz

    return sampler


def _build_qiskit_round_sampler(QuantumCircuit: Any, StabilizerState: Any, geom: SurfaceGeometry) -> RoundSampler:
    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x

    def sampler(x_bits: list[int], z_bits: list[int]) -> tuple[list[int], list[int]]:
        qc = QuantumCircuit(n_total)

        for i, bit in enumerate(x_bits):
            if bit & 1:
                qc.x(i)
        for i, bit in enumerate(z_bits):
            if bit & 1:
                qc.z(i)

        for c_idx, support in enumerate(geom.x_supports):
            anc = x_offset + c_idx
            qc.h(anc)
            for dq in support:
                qc.cx(anc, dq)
            qc.h(anc)

        for c_idx, support in enumerate(geom.z_supports):
            anc = z_offset + c_idx
            for dq in support:
                qc.cx(dq, anc)

        st = StabilizerState(qc)
        bitstring = st.sample_memory(shots=1)[0]

        def bit_at(qubit_index: int) -> int:
            return int(bitstring[n_total - 1 - qubit_index])

        sx = [bit_at(x_offset + i) for i in range(geom.n_x)]
        sz = [bit_at(z_offset + i) for i in range(geom.n_z)]
        return sx, sz

    return sampler


def _build_cirq_round_sampler(cirq: Any, geom: SurfaceGeometry, seed: int) -> RoundSampler:
    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x
    qubits = cirq.LineQubit.range(n_total)
    x_anc = [qubits[x_offset + i] for i in range(geom.n_x)]
    z_anc = [qubits[z_offset + i] for i in range(geom.n_z)]
    sim = cirq.CliffordSimulator(seed=seed)

    def sampler(x_bits: list[int], z_bits: list[int]) -> tuple[list[int], list[int]]:
        ops = []

        for i, bit in enumerate(x_bits):
            if bit & 1:
                ops.append(cirq.X(qubits[i]))
        for i, bit in enumerate(z_bits):
            if bit & 1:
                ops.append(cirq.Z(qubits[i]))

        for c_idx, support in enumerate(geom.x_supports):
            anc = x_anc[c_idx]
            ops.append(cirq.H(anc))
            for dq in support:
                ops.append(cirq.CNOT(anc, qubits[dq]))
            ops.append(cirq.H(anc))

        for c_idx, support in enumerate(geom.z_supports):
            anc = z_anc[c_idx]
            for dq in support:
                ops.append(cirq.CNOT(qubits[dq], anc))

        circuit = cirq.Circuit(
            ops,
            cirq.measure(*x_anc, key="mx"),
            cirq.measure(*z_anc, key="mz"),
        )
        result = sim.run(circuit, repetitions=1)
        sx = [int(v) for v in result.measurements["mx"][0].tolist()]
        sz = [int(v) for v in result.measurements["mz"][0].tolist()]
        return sx, sz

    return sampler


def _apply_data_noise(x_bits: list[int], z_bits: list[int], p_gate: float, p_idle: float, rng: random.Random) -> None:
    for i in range(len(x_bits)):
        if rng.random() < p_gate:
            x_bits[i] ^= 1
        if rng.random() < p_gate:
            z_bits[i] ^= 1
        if rng.random() < p_idle:
            x_bits[i] ^= 1
        if rng.random() < (p_idle * 0.5):
            z_bits[i] ^= 1


def _apply_measurement_noise(bits: list[int], p_meas: float, rng: random.Random) -> None:
    for i in range(len(bits)):
        if rng.random() < p_meas:
            bits[i] ^= 1


def _logical_x_indices(geom: SurfaceGeometry) -> list[int]:
    y_mid = geom.distance // 2
    return [y_mid * (geom.distance - 1) + x for x in range(geom.distance - 1)]


def _error_indices(bits: list[int]) -> list[int]:
    return [idx for idx, bit in enumerate(bits) if bit & 1]


def _parity_on(indices: list[int], bits: list[int]) -> int:
    parity = 0
    for idx in indices:
        if 0 <= idx < len(bits):
            parity ^= bits[idx] & 1
    return parity


def _truth_record(
    *,
    code_id: str,
    shot_index: int,
    dataset_name: str,
    geom: SurfaceGeometry,
    x_bits: list[int],
    z_bits: list[int],
    truth_model: str,
) -> dict[str, Any]:
    logical_indices = _logical_x_indices(geom)
    return {
        "code_id": code_id,
        "round_index": shot_index,
        "dataset": dataset_name,
        "n_qubits": geom.n_data,
        "logical_observable": "x_error_midline_parity",
        "logical_indices": logical_indices,
        "logical_truth": _parity_on(logical_indices, x_bits),
        "x_error_indices": _error_indices(x_bits),
        "z_error_indices": _error_indices(z_bits),
        "truth_model": truth_model,
    }


def _simulate_repeated_round_events(
    *,
    geom: SurfaceGeometry,
    rounds: int,
    p_gate: float,
    p_meas: float,
    p_idle: float,
    round_sampler: RoundSampler,
    rng: random.Random,
    emit_x_events: bool,
    emit_z_events: bool,
) -> tuple[list[dict[str, Any]], list[int], list[int]]:
    x_bits = [0] * geom.n_data
    z_bits = [0] * geom.n_data
    prev_sx = [0] * geom.n_x
    prev_sz = [0] * geom.n_z
    events: list[dict[str, Any]] = []

    for r in range(rounds):
        _apply_data_noise(x_bits, z_bits, p_gate=p_gate, p_idle=p_idle, rng=rng)
        sx, sz = round_sampler(x_bits, z_bits)
        _apply_measurement_noise(sx, p_meas, rng)
        _apply_measurement_noise(sz, p_meas, rng)

        if emit_x_events:
            for i in range(geom.n_x):
                if (sx[i] ^ prev_sx[i]) & 1:
                    events.append({"index": i, "time_ns": (r + 1) * 1000, "type": "X"})
        if emit_z_events:
            for i in range(geom.n_z):
                if (sz[i] ^ prev_sz[i]) & 1:
                    events.append({"index": i, "time_ns": (r + 1) * 1000 + 100, "type": "Z"})

        prev_sx = sx
        prev_sz = sz

    return events, x_bits, z_bits


def _digitize_periodic(value: float, period: float, width: float, bias: float = 0.0) -> int:
    if period <= 0.0:
        return 0
    v = value + bias
    wrapped = (v + 0.5 * period) % period - 0.5 * period
    return 1 if abs(wrapped) > width else 0


def _build_gkp_round_sampler(geom: SurfaceGeometry, variant: str, rng: random.Random) -> RoundSampler:
    sqrt_pi = math.sqrt(math.pi)

    def sampler(q_shift: list[int], p_shift: list[int]) -> tuple[list[int], list[int]]:
        raise RuntimeError("unreachable")

    def from_float_states(q_shift_f: list[float], p_shift_f: list[float]) -> tuple[list[int], list[int]]:
        sx: list[int] = []
        sz: list[int] = []

        for support in geom.x_supports:
            if not support:
                sx.append(0)
                continue
            scale = math.sqrt(float(len(support)))
            value = sum(p_shift_f[q] for q in support) / scale
            if variant == "pennylane":
                bit = _digitize_periodic(value, period=sqrt_pi, width=0.22 * sqrt_pi, bias=0.04 * sqrt_pi)
            elif variant == "qiskit":
                scaled = (value / (0.5 * sqrt_pi)) + rng.gauss(0.0, 0.08)
                bit = int(abs(int(round(scaled))) % 2 == 1)
            elif variant == "cirq":
                phase = value / sqrt_pi
                bit = int(math.sin(math.pi * phase) > 0.0)
            else:
                bit = _digitize_periodic(value, period=sqrt_pi, width=0.25 * sqrt_pi, bias=0.0)
            sx.append(bit)

        for support in geom.z_supports:
            if not support:
                sz.append(0)
                continue
            scale = math.sqrt(float(len(support)))
            value = sum(q_shift_f[q] for q in support) / scale
            if variant == "pennylane":
                bit = _digitize_periodic(value, period=sqrt_pi, width=0.22 * sqrt_pi, bias=-0.03 * sqrt_pi)
            elif variant == "qiskit":
                scaled = (value / (0.5 * sqrt_pi)) + rng.gauss(0.0, 0.08)
                bit = int(abs(int(round(scaled))) % 2 == 1)
            elif variant == "cirq":
                phase = value / sqrt_pi
                bit = int(math.cos(math.pi * phase) < 0.0)
            else:
                bit = _digitize_periodic(value, period=sqrt_pi, width=0.25 * sqrt_pi, bias=0.0)
            sz.append(bit)

        return sx, sz

    def sampler_adapter(x_bits: list[int], z_bits: list[int]) -> tuple[list[int], list[int]]:
        q_shift_f = [float(v) for v in x_bits]
        p_shift_f = [float(v) for v in z_bits]
        return from_float_states(q_shift_f, p_shift_f)

    sampler = sampler_adapter
    sampler.from_float_states = from_float_states  # type: ignore[attr-defined]
    return sampler


def _apply_gkp_shift_noise(
    q_shift: list[float],
    p_shift: list[float],
    sigma_shift: float,
    jump_prob: float,
    jump_scale: float,
    rng: random.Random,
) -> None:
    for i in range(len(q_shift)):
        q_shift[i] += rng.gauss(0.0, sigma_shift)
        p_shift[i] += rng.gauss(0.0, sigma_shift)
        if rng.random() < jump_prob:
            q_shift[i] += jump_scale if rng.random() < 0.5 else -jump_scale
        if rng.random() < jump_prob:
            p_shift[i] += jump_scale if rng.random() < 0.5 else -jump_scale


def _simulate_gkp_repeated_round_events(
    *,
    geom: SurfaceGeometry,
    rounds: int,
    sigma_shift: float,
    p_meas: float,
    jump_prob: float,
    jump_scale: float,
    round_sampler: RoundSampler,
    rng: random.Random,
    emit_x_events: bool,
    emit_z_events: bool,
) -> tuple[list[dict[str, Any]], list[int], list[int]]:
    q_shift = [0.0] * geom.n_data
    p_shift = [0.0] * geom.n_data
    prev_sx = [0] * geom.n_x
    prev_sz = [0] * geom.n_z
    events: list[dict[str, Any]] = []

    for r in range(rounds):
        _apply_gkp_shift_noise(
            q_shift=q_shift,
            p_shift=p_shift,
            sigma_shift=sigma_shift,
            jump_prob=jump_prob,
            jump_scale=jump_scale,
            rng=rng,
        )
        if hasattr(round_sampler, "from_float_states"):
            sx, sz = round_sampler.from_float_states(q_shift, p_shift)  # type: ignore[attr-defined]
        else:
            sx, sz = round_sampler([int(v) for v in q_shift], [int(v) for v in p_shift])
        _apply_measurement_noise(sx, p_meas, rng)
        _apply_measurement_noise(sz, p_meas, rng)

        if emit_x_events:
            for i in range(geom.n_x):
                if (sx[i] ^ prev_sx[i]) & 1:
                    events.append({"index": i, "time_ns": (r + 1) * 1000, "type": "X"})
        if emit_z_events:
            for i in range(geom.n_z):
                if (sz[i] ^ prev_sz[i]) & 1:
                    events.append({"index": i, "time_ns": (r + 1) * 1000 + 100, "type": "Z"})

        prev_sx = sx
        prev_sz = sz

    sqrt_pi = math.sqrt(math.pi)
    x_bits = [_digitize_periodic(v, period=sqrt_pi, width=0.25 * sqrt_pi, bias=0.0) for v in q_shift]
    z_bits = [_digitize_periodic(v, period=sqrt_pi, width=0.25 * sqrt_pi, bias=0.0) for v in p_shift]
    return events, x_bits, z_bits


def _write_dataset(
    path: Path,
    *,
    truth_path: Path,
    dataset_name: str,
    code_id: str,
    shots: int,
    rounds: int,
    geom: SurfaceGeometry,
    sigma: float,
    p_gate: float,
    p_meas: float,
    p_idle: float,
    seed: int,
    source_backend: str,
    round_sampler: RoundSampler,
    emit_x_events: bool,
    emit_z_events: bool,
) -> dict[str, Any]:
    nonempty = 0
    total_events = 0
    rng = random.Random(seed)

    with path.open("w", encoding="utf-8") as f, truth_path.open("w", encoding="utf-8") as tf:
        for shot_index in range(shots):
            events, x_bits, z_bits = _simulate_repeated_round_events(
                geom=geom,
                rounds=rounds,
                p_gate=p_gate,
                p_meas=p_meas,
                p_idle=p_idle,
                round_sampler=round_sampler,
                rng=rng,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
            if events:
                nonempty += 1
            total_events += len(events)

            rec = {
                "code_id": code_id,
                "round_index": shot_index,
                "n_qubits": geom.n_data,
                "events": events,
                "noise": {
                    "sigma": sigma,
                    "gate_error_rate": p_gate,
                    "meas_error_rate": p_meas,
                    "idle_error_rate": p_idle,
                    "loss_prob_by_qubit": [],
                },
                "metadata": {
                    "dataset": dataset_name,
                    "source_backend": source_backend,
                    "seed": str(seed),
                    "distance": str(geom.distance),
                    "rounds": str(rounds),
                    "x_checks": str(geom.n_x),
                    "z_checks": str(geom.n_z),
                    "emit_x_events": str(1 if emit_x_events else 0),
                    "emit_z_events": str(1 if emit_z_events else 0),
                    "generator": "surface_stabilizer_rounds",
                },
            }
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            tf.write(
                json.dumps(
                    _truth_record(
                        code_id=code_id,
                        shot_index=shot_index,
                        dataset_name=dataset_name,
                        geom=geom,
                        x_bits=x_bits,
                        z_bits=z_bits,
                        truth_model="surface_final_pauli_state",
                    ),
                    separators=(",", ":"),
                )
                + "\n"
            )

    return {
        "dataset": dataset_name,
        "request_file": path.name,
        "truth_file": truth_path.name,
        "request_lines": shots,
        "avg_request_events": float(total_events) / float(max(shots, 1)),
        "nonempty_request_event_rate": float(nonempty) / float(max(shots, 1)),
        "source_backend": source_backend,
    }


def _write_dataset_gkp(
    path: Path,
    *,
    truth_path: Path,
    dataset_name: str,
    code_id: str,
    shots: int,
    rounds: int,
    geom: SurfaceGeometry,
    sigma: float,
    sigma_shift: float,
    p_meas: float,
    jump_prob: float,
    jump_scale: float,
    seed: int,
    source_backend: str,
    round_sampler: RoundSampler,
    emit_x_events: bool,
    emit_z_events: bool,
) -> dict[str, Any]:
    nonempty = 0
    total_events = 0
    rng = random.Random(seed)

    with path.open("w", encoding="utf-8") as f, truth_path.open("w", encoding="utf-8") as tf:
        for shot_index in range(shots):
            events, x_bits, z_bits = _simulate_gkp_repeated_round_events(
                geom=geom,
                rounds=rounds,
                sigma_shift=sigma_shift,
                p_meas=p_meas,
                jump_prob=jump_prob,
                jump_scale=jump_scale,
                round_sampler=round_sampler,
                rng=rng,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
            if events:
                nonempty += 1
            total_events += len(events)

            rec = {
                "code_id": code_id,
                "round_index": shot_index,
                "n_qubits": geom.n_data,
                "events": events,
                "noise": {
                    "sigma": sigma,
                    "gate_error_rate": 0.0,
                    "meas_error_rate": p_meas,
                    "idle_error_rate": 0.0,
                    "loss_prob_by_qubit": [],
                },
                "metadata": {
                    "dataset": dataset_name,
                    "source_backend": source_backend,
                    "seed": str(seed),
                    "distance": str(geom.distance),
                    "rounds": str(rounds),
                    "x_checks": str(geom.n_x),
                    "z_checks": str(geom.n_z),
                    "emit_x_events": str(1 if emit_x_events else 0),
                    "emit_z_events": str(1 if emit_z_events else 0),
                    "generator": "gkp_digitized_rounds",
                },
            }
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            tf.write(
                json.dumps(
                    _truth_record(
                        code_id=code_id,
                        shot_index=shot_index,
                        dataset_name=dataset_name,
                        geom=geom,
                        x_bits=x_bits,
                        z_bits=z_bits,
                        truth_model="gkp_reference_digitized_shift",
                    ),
                    separators=(",", ":"),
                )
                + "\n"
            )

    return {
        "dataset": dataset_name,
        "request_file": path.name,
        "truth_file": truth_path.name,
        "request_lines": shots,
        "avg_request_events": float(total_events) / float(max(shots, 1)),
        "nonempty_request_event_rate": float(nonempty) / float(max(shots, 1)),
        "source_backend": source_backend,
    }


def main() -> int:
    args = parse_args()
    if args.shots <= 0:
        raise SystemExit("Error: --shots must be positive.")
    if args.rounds <= 0:
        raise SystemExit("Error: --rounds must be positive.")
    if args.error_rate < 0.0 or args.error_rate > 1.0:
        raise SystemExit("Error: --error-rate must be within [0, 1].")

    geom = build_surface_geometry(args.distance)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.n_qubits > 0 and args.n_qubits != geom.n_data:
        print(
            f"Warning: requested --n-qubits={args.n_qubits}, but distance {geom.distance} "
            f"implies n_qubits={geom.n_data}; using derived value.",
            file=sys.stderr,
        )
    # Keep existing request-level semantics: meas > gate > idle.
    p_gate = min(1.0, max(0.0, args.error_rate * 0.5))
    p_meas = min(1.0, max(0.0, args.error_rate))
    p_idle = min(1.0, max(0.0, args.error_rate * 0.4))
    emit_x_events = bool(args.emit_x_events)
    emit_z_events = bool(args.emit_z_events)
    if not emit_x_events and not emit_z_events:
        raise SystemExit("Error: at least one of --emit-x-events or --emit-z-events must be 1.")

    qml, pennylane_enabled = _load_pennylane(args.pennylane_mode)
    QuantumCircuit, StabilizerState, qiskit_enabled = _load_qiskit(args.qiskit_mode)
    cirq_mod, cirq_enabled = _load_cirq(args.cirq_mode)
    classical_sampler = _build_classical_round_sampler(geom)

    if pennylane_enabled:
        pennylane_sampler = _build_pennylane_round_sampler(qml, geom)
        pennylane_backend = "pennylane_surface_rounds"
    else:
        pennylane_sampler = classical_sampler
        pennylane_backend = "synthetic_fallback"

    if qiskit_enabled:
        qiskit_sampler = _build_qiskit_round_sampler(QuantumCircuit, StabilizerState, geom)
        qiskit_backend = "qiskit_surface_rounds"
    else:
        qiskit_sampler = classical_sampler
        qiskit_backend = "synthetic_fallback"

    if cirq_enabled:
        cirq_sampler = _build_cirq_round_sampler(cirq_mod, geom, seed=args.seed + 17)
        cirq_backend = "cirq_surface_rounds"
    else:
        cirq_sampler = classical_sampler
        cirq_backend = "synthetic_fallback"

    code_id = f"{args.code_family}_d{geom.distance}"
    rows: list[dict[str, Any]] = []

    if args.code_family == "surface":
        rows.append(
            _write_dataset(
                out_dir / "decoder_requests_pennylane.ndjson",
                truth_path=out_dir / "truth_pennylane.ndjson",
                dataset_name="pennylane",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                p_gate=p_gate,
                p_meas=p_meas,
                p_idle=p_idle,
                seed=args.seed,
                source_backend=pennylane_backend,
                round_sampler=pennylane_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset(
                out_dir / "decoder_requests_qiskit.ndjson",
                truth_path=out_dir / "truth_qiskit.ndjson",
                dataset_name="qiskit",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                p_gate=p_gate,
                p_meas=p_meas,
                p_idle=p_idle,
                seed=args.seed + 37,
                source_backend=qiskit_backend,
                round_sampler=qiskit_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset(
                out_dir / "decoder_requests_cirq.ndjson",
                truth_path=out_dir / "truth_cirq.ndjson",
                dataset_name="cirq",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                p_gate=p_gate,
                p_meas=p_meas,
                p_idle=p_idle,
                seed=args.seed + 57,
                source_backend=cirq_backend,
                round_sampler=cirq_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset(
                out_dir / "decoder_requests_lidmas_reference.ndjson",
                truth_path=out_dir / "truth_lidmas_reference.ndjson",
                dataset_name="lidmas_reference",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                p_gate=p_gate,
                p_meas=p_meas,
                p_idle=p_idle,
                seed=args.seed + 77,
                source_backend="lidmas_surface_reference",
                round_sampler=classical_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
    else:
        sigma_shift = max(1e-4, args.sigma * (0.75 + 1.1 * args.error_rate))
        jump_prob = min(0.35, max(0.0, args.error_rate * 0.25))
        jump_scale = math.sqrt(math.pi) * 0.5

        gkp_pennylane_sampler = _build_gkp_round_sampler(geom, "pennylane", random.Random(args.seed + 101))
        gkp_qiskit_sampler = _build_gkp_round_sampler(geom, "qiskit", random.Random(args.seed + 131))
        gkp_cirq_sampler = _build_gkp_round_sampler(geom, "cirq", random.Random(args.seed + 151))
        gkp_ref_sampler = _build_gkp_round_sampler(geom, "lidmas_reference", random.Random(args.seed + 171))

        rows.append(
            _write_dataset_gkp(
                out_dir / "decoder_requests_pennylane.ndjson",
                truth_path=out_dir / "truth_pennylane.ndjson",
                dataset_name="pennylane",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                sigma_shift=sigma_shift,
                p_meas=p_meas,
                jump_prob=jump_prob,
                jump_scale=jump_scale,
                seed=args.seed,
                source_backend="pennylane_gkp_digitized",
                round_sampler=gkp_pennylane_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset_gkp(
                out_dir / "decoder_requests_qiskit.ndjson",
                truth_path=out_dir / "truth_qiskit.ndjson",
                dataset_name="qiskit",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                sigma_shift=sigma_shift,
                p_meas=p_meas,
                jump_prob=jump_prob,
                jump_scale=jump_scale,
                seed=args.seed + 37,
                source_backend="qiskit_gkp_digitized",
                round_sampler=gkp_qiskit_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset_gkp(
                out_dir / "decoder_requests_cirq.ndjson",
                truth_path=out_dir / "truth_cirq.ndjson",
                dataset_name="cirq",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                sigma_shift=sigma_shift,
                p_meas=p_meas,
                jump_prob=jump_prob,
                jump_scale=jump_scale,
                seed=args.seed + 57,
                source_backend="cirq_gkp_digitized",
                round_sampler=gkp_cirq_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )
        rows.append(
            _write_dataset_gkp(
                out_dir / "decoder_requests_lidmas_reference.ndjson",
                truth_path=out_dir / "truth_lidmas_reference.ndjson",
                dataset_name="lidmas_reference",
                code_id=code_id,
                shots=args.shots,
                rounds=args.rounds,
                geom=geom,
                sigma=args.sigma,
                sigma_shift=sigma_shift,
                p_meas=p_meas,
                jump_prob=jump_prob,
                jump_scale=jump_scale,
                seed=args.seed + 77,
                source_backend="lidmas_gkp_reference",
                round_sampler=gkp_ref_sampler,
                emit_x_events=emit_x_events,
                emit_z_events=emit_z_events,
            )
        )

    manifest_path = out_dir / "table_request_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "request_file",
                "truth_file",
                "request_lines",
                "avg_request_events",
                "nonempty_request_event_rate",
                "source_backend",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "avg_request_events": f"{float(row['avg_request_events']):.6f}",
                    "nonempty_request_event_rate": f"{float(row['nonempty_request_event_rate']):.6f}",
                }
            )

    summary = {
        "shots": args.shots,
        "rounds": args.rounds,
        "distance": geom.distance,
        "code_family": args.code_family,
        "n_qubits": geom.n_data,
        "n_x_checks": geom.n_x,
        "n_z_checks": geom.n_z,
        "error_rate": args.error_rate,
        "sigma": args.sigma,
        "seed": args.seed,
        "pennylane_mode": args.pennylane_mode,
        "qiskit_mode": args.qiskit_mode,
        "cirq_mode": args.cirq_mode,
        "emit_x_events": emit_x_events,
        "emit_z_events": emit_z_events,
        "pennylane_enabled": pennylane_enabled,
        "qiskit_enabled": qiskit_enabled,
        "cirq_enabled": cirq_enabled,
        "datasets": rows,
    }
    with (out_dir / "summary_generation.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    if not pennylane_enabled:
        print(
            "Warning: PennyLane not available; generated 'pennylane' dataset using synthetic fallback.",
            file=sys.stderr,
        )
    if not qiskit_enabled:
        print(
            "Warning: Qiskit not available; generated 'qiskit' dataset using synthetic fallback.",
            file=sys.stderr,
        )
    if not cirq_enabled:
        print(
            "Warning: Cirq not available; generated 'cirq' dataset using synthetic fallback.",
            file=sys.stderr,
        )

    print(f"Wrote request datasets and manifest to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
