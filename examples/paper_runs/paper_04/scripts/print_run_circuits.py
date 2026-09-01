#!/usr/bin/env python3
"""Print circuit/logic snapshots used by paper_04 runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from generate_comparison_requests import SurfaceGeometry, build_surface_geometry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        default="examples/paper_runs/paper_04/results/03_analysis/runs",
        help="Root directory containing per-family runs.",
    )
    parser.add_argument(
        "--out-dir",
        default="examples/paper_runs/paper_04/results/03_analysis/circuit_prints",
        help="Output directory for printed circuit/logic text files.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_supports(geom: SurfaceGeometry) -> str:
    lines: list[str] = []
    lines.append(f"distance={geom.distance}")
    lines.append(f"n_data={geom.n_data}, n_x_checks={geom.n_x}, n_z_checks={geom.n_z}")
    lines.append("")
    lines.append("X-check supports (index: data-qubit list):")
    for idx, support in enumerate(geom.x_supports):
        lines.append(f"  X{idx:02d}: {support}")
    lines.append("")
    lines.append("Z-check supports (index: data-qubit list):")
    for idx, support in enumerate(geom.z_supports):
        lines.append(f"  Z{idx:02d}: {support}")
    lines.append("")
    return "\n".join(lines)


def _surface_qiskit_circuit_text(geom: SurfaceGeometry) -> str:
    try:
        from qiskit import QuantumCircuit  # type: ignore
    except Exception as exc:
        return f"Qiskit unavailable in this environment: {exc}\n"

    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x
    qc = QuantumCircuit(n_total, name="surface_round")

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

    return str(qc.draw(output="text", fold=-1))


def _surface_cirq_circuit_text(geom: SurfaceGeometry) -> str:
    try:
        import cirq  # type: ignore
    except Exception as exc:
        return f"Cirq unavailable in this environment: {exc}\n"

    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x
    qubits = cirq.LineQubit.range(n_total)
    x_anc = [qubits[x_offset + i] for i in range(geom.n_x)]
    z_anc = [qubits[z_offset + i] for i in range(geom.n_z)]

    ops = []
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
    return str(circuit)


def _surface_pennylane_circuit_text(geom: SurfaceGeometry) -> str:
    try:
        import pennylane as qml  # type: ignore
    except Exception as exc:
        return f"PennyLane unavailable in this environment: {exc}\n"

    n_total = geom.n_data + geom.n_x + geom.n_z
    x_offset = geom.n_data
    z_offset = geom.n_data + geom.n_x
    dev = qml.device("default.clifford", wires=n_total)

    @qml.set_shots(shots=1)
    @qml.qnode(dev)
    def circuit():
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

    try:
        drawer = qml.draw(circuit, expansion_strategy="device")
    except TypeError:
        drawer = qml.draw(circuit)
    return drawer()


def _gkp_logic_text(variant: str, geom: SurfaceGeometry) -> str:
    lines: list[str] = []
    lines.append(f"GKP digitized logic variant: {variant}")
    lines.append("")
    lines.append("No framework-native gate circuit is built for GKP in this run.")
    lines.append("Instead, repeated-round q/p shift states are projected through check supports")
    lines.append("and digitized into X/Z syndrome bits with variant-specific rules.")
    lines.append("")
    lines.append("Digitization rules:")
    lines.append("  - pennylane: periodic threshold with small bias")
    lines.append("  - qiskit: rounded scaled value with Gaussian perturbation")
    lines.append("  - cirq: sinusoidal phase-sign rule")
    lines.append("  - lidmas_reference: periodic threshold without framework bias")
    lines.append("")
    lines.append(_fmt_supports(geom))
    return "\n".join(lines)


def _run_meta_text(summary: dict[str, Any]) -> str:
    keys = [
        "shots",
        "rounds",
        "distance",
        "code_family",
        "n_qubits",
        "n_x_checks",
        "n_z_checks",
        "error_rate",
        "sigma",
        "seed",
        "emit_x_events",
        "emit_z_events",
        "pennylane_enabled",
        "qiskit_enabled",
        "cirq_enabled",
    ]
    lines = ["Run metadata:"]
    for key in keys:
        lines.append(f"  {key}: {summary.get(key)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Use current manuscript run geometry (distance from summary).
    surf_summary = _read_json(run_root / "surface/01_generate_comparison_requests/summary_generation.json")
    gkp_summary = _read_json(run_root / "gkp/01_generate_comparison_requests/summary_generation.json")

    surf_geom = build_surface_geometry(int(surf_summary["distance"]))
    gkp_geom = build_surface_geometry(int(gkp_summary["distance"]))

    # Shared metadata files.
    (out_dir / "surface_run_metadata.txt").write_text(_run_meta_text(surf_summary), encoding="utf-8")
    (out_dir / "gkp_run_metadata.txt").write_text(_run_meta_text(gkp_summary), encoding="utf-8")
    (out_dir / "surface_check_supports.txt").write_text(_fmt_supports(surf_geom), encoding="utf-8")
    (out_dir / "gkp_check_supports.txt").write_text(_fmt_supports(gkp_geom), encoding="utf-8")

    # Surface family circuits.
    (out_dir / "surface_pennylane_circuit.txt").write_text(
        _surface_pennylane_circuit_text(surf_geom), encoding="utf-8"
    )
    (out_dir / "surface_qiskit_circuit.txt").write_text(
        _surface_qiskit_circuit_text(surf_geom), encoding="utf-8"
    )
    (out_dir / "surface_cirq_circuit.txt").write_text(
        _surface_cirq_circuit_text(surf_geom), encoding="utf-8"
    )
    (out_dir / "surface_lidmas_reference_logic.txt").write_text(
        "LiDMaS+ reference path uses the classical parity-check sampler.\n\n" + _fmt_supports(surf_geom),
        encoding="utf-8",
    )

    # GKP family logic (digitized, not gate-circuit objects).
    for variant in ("pennylane", "qiskit", "cirq", "lidmas_reference"):
        (out_dir / f"gkp_{variant}_digitized_logic.txt").write_text(
            _gkp_logic_text(variant, gkp_geom), encoding="utf-8"
        )

    print(f"Wrote circuit/logic printouts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
