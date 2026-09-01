#!/usr/bin/env python3
"""Convert digitized-GKP sample records into LiDMaS+ decoder requests."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from gkp_digitized_syndrome import expected_syndrome, sanitize_label, syndrome_to_events
from surface_syndrome import build_surface_geometry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--raw-json", action="append", required=True)
    return parser.parse_args()


def _injected_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _iter_shots(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    if experiment.get("shot_records"):
        return list(experiment["shot_records"])
    shots: list[dict[str, Any]] = []
    for bitstring, count in sorted(experiment.get("counts", {}).items()):
        for _ in range(int(count)):
            shots.append({"bitstring": bitstring, "measured_syndrome": []})
    return shots


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    table_rows: list[dict[str, Any]] = []

    for raw in args.raw_json:
        raw_path = Path(raw)
        with raw_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        distance = int(payload["distance"])
        geom = build_surface_geometry(distance)
        n_data = int(payload["n_data"])
        n_checks = int(payload["n_checks"])
        source = str(payload.get("source", "digitized_gkp_local"))
        backend = str(payload.get("backend", source))
        dataset = sanitize_label(source)
        req_path = out_dir / f"decoder_requests_{dataset}.ndjson"
        truth_path = out_dir / f"truth_{dataset}.ndjson"
        line_count = 0

        with req_path.open("w", encoding="utf-8") as req_f, truth_path.open("w", encoding="utf-8") as truth_f:
            for experiment in payload.get("experiments", []):
                circuit_id = str(experiment["circuit_id"])
                injected = _injected_value(experiment.get("injected_q"))
                exp_syndrome = expected_syndrome(geom, injected)
                for shot_index, shot in enumerate(_iter_shots(experiment)):
                    syndrome = [int(bit) & 1 for bit in shot.get("measured_syndrome", [])]
                    if len(syndrome) != n_checks:
                        compact = str(shot.get("bitstring", "")).replace(" ", "")
                        if len(compact) >= n_checks + n_data:
                            c_low_to_high = [int(ch) for ch in reversed(compact)]
                            syndrome = c_low_to_high[:n_checks]
                        else:
                            raise ValueError(f"missing measured syndrome for {circuit_id} shot {shot_index}")
                    data_bits = [int(bit) & 1 for bit in shot.get("digitized_data", [])]
                    analog_values = shot.get("analog_z_values", [])
                    rec = {
                        "code_id": f"digitized_gkp_surface_d{distance}_z_checks",
                        "round_index": line_count,
                        "n_qubits": n_data,
                        "events": syndrome_to_events(syndrome),
                        "noise": {
                            "sigma": float(payload.get("sigma_shift", 0.0) or 0.0),
                            "gate_error_rate": 0.0,
                            "meas_error_rate": float(payload.get("measurement_error_rate", 0.0) or 0.0),
                            "idle_error_rate": 0.0,
                            "loss_prob_by_qubit": [],
                        },
                        "metadata": {
                            "dataset": dataset,
                            "source_backend": backend,
                            "source": source,
                            "job_id": str(payload.get("job_id", "")),
                            "generator": "paper05_digitized_gkp",
                            "code_family": "digitized_gkp",
                            "code_name": f"digitized_gkp_surface_d{distance}_z_checks",
                            "circuit_id": circuit_id,
                            "injected_q": "" if injected is None else str(injected),
                            "distance": str(distance),
                            "n_data": str(n_data),
                            "n_checks": str(n_checks),
                            "rounds": str(payload.get("rounds", "1")),
                            "bitstring": str(shot.get("bitstring", "")),
                            "measured_syndrome": "".join(str(bit) for bit in syndrome),
                            "digitized_data": "".join(str(bit) for bit in data_bits),
                            "expected_syndrome": "".join(str(bit) for bit in exp_syndrome),
                            "shot_index": str(shot_index),
                            "sigma_shift_scale": str(payload.get("sigma_shift_scale", "")),
                            "injected_shift_scale": str(payload.get("injected_shift_scale", "")),
                            "decision_width_scale": str(payload.get("decision_width_scale", "")),
                        },
                    }
                    req_f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    truth_f.write(
                        json.dumps(
                            {
                                "code_id": f"digitized_gkp_surface_d{distance}_z_checks",
                                "round_index": line_count,
                                "dataset": dataset,
                                "circuit_id": circuit_id,
                                "injected_q": injected,
                                "expected_syndrome": exp_syndrome,
                                "digitized_data": data_bits,
                                "analog_z_values": analog_values,
                                "logical_observable": "digitized_gkp_q_shift_z_syndrome",
                                "logical_truth": 0,
                            },
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    table_rows.append(
                        {
                            "dataset": dataset,
                            "source": source,
                            "backend": backend,
                            "job_id": str(payload.get("job_id", "")),
                            "circuit_id": circuit_id,
                            "injected_q": "" if injected is None else injected,
                            "shot_index": shot_index,
                            "bitstring": str(shot.get("bitstring", "")),
                            "measured_syndrome": "".join(str(bit) for bit in syndrome),
                            "digitized_data": "".join(str(bit) for bit in data_bits),
                            "syndrome_weight": sum(syndrome),
                            "expected_syndrome": "".join(str(bit) for bit in exp_syndrome),
                            "mean_abs_analog_z_value": (
                                sum(abs(float(v)) for v in analog_values) / len(analog_values) if analog_values else ""
                            ),
                        }
                    )
                    line_count += 1

        manifest_rows.append(
            {
                "dataset": dataset,
                "source": source,
                "backend": backend,
                "raw_json": str(raw_path),
                "request_file": req_path.name,
                "truth_file": truth_path.name,
                "request_lines": line_count,
            }
        )

    with (out_dir / "ingest_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["dataset", "source", "backend", "raw_json", "request_file", "truth_file", "request_lines"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)

    with (out_dir / "table_ingested_gkp_syndromes.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "dataset",
            "source",
            "backend",
            "job_id",
            "circuit_id",
            "injected_q",
            "shot_index",
            "bitstring",
            "measured_syndrome",
            "digitized_data",
            "syndrome_weight",
            "expected_syndrome",
            "mean_abs_analog_z_value",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(table_rows)

    print(f"Wrote {len(manifest_rows)} digitized-GKP request streams to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
