#!/usr/bin/env python3
"""Build paper_05 repetition-code syndrome circuit artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from repetition_syndrome import build_qiskit_circuit, circuit_metadata, experiment_specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--n-data", type=int, default=5)
    parser.add_argument("--targets", default="all")
    return parser.parse_args()


def write_qasm(path: Path, circuit: object) -> None:
    try:
        from qiskit import qasm3  # type: ignore

        text = qasm3.dumps(circuit)
    except Exception:
        try:
            text = circuit.qasm()  # type: ignore[attr-defined]
        except Exception:
            text = "// QASM export unavailable in this Qiskit installation.\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.n_data < 3:
        raise SystemExit("Error: --n-data must be at least 3.")

    out_dir = Path(args.out_dir)
    qasm_dir = out_dir / "qasm"
    out_dir.mkdir(parents=True, exist_ok=True)
    qasm_dir.mkdir(parents=True, exist_ok=True)

    specs = experiment_specs(args.n_data, args.targets)
    manifest_rows: list[dict[str, object]] = []
    drawings: list[str] = []

    for spec in specs:
        circuit = build_qiskit_circuit(args.n_data, spec)
        meta = circuit_metadata(args.n_data, spec)
        qasm_path = qasm_dir / f"{spec.circuit_id}.qasm"
        write_qasm(qasm_path, circuit)

        drawing = circuit.draw(output="text", fold=110)
        drawings.append(f"=== {spec.circuit_id} ===\n{drawing}\n")

        row = {
            **meta,
            "n_qubits_total": circuit.num_qubits,
            "n_clbits": circuit.num_clbits,
            "depth": circuit.depth(),
            "qasm_file": str(qasm_path.relative_to(out_dir)),
        }
        manifest_rows.append(row)

    with (out_dir / "circuit_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "code_family": "repetition",
                "n_data": args.n_data,
                "n_checks": args.n_data - 1,
                "targets": args.targets,
                "circuits": manifest_rows,
            },
            f,
            indent=2,
        )
        f.write("\n")

    fields = [
        "circuit_id",
        "label",
        "n_data",
        "n_checks",
        "injected_x",
        "expected_syndrome",
        "n_qubits_total",
        "n_clbits",
        "depth",
        "qasm_file",
    ]
    with (out_dir / "circuit_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    (out_dir / "circuit_drawings.txt").write_text("\n".join(drawings), encoding="utf-8")
    print(f"Wrote {len(specs)} repetition-code syndrome circuits to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
