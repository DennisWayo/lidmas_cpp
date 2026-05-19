#!/usr/bin/env python3
"""Refresh vendor calibration snapshots for LiDMaS+.

This script ingests the best available live/provider-adjacent signals and writes
a normalized calibration catalog consumed by LiDMaS+ simulator and UI flows.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    id: str
    label: str
    vendor: str
    hardware_target: str
    backend: str
    captured_at: str
    source: str
    metrics: dict[str, float]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def default_catalog() -> list[Snapshot]:
    return [
        Snapshot(
            id="ibm_kingston_2026q2",
            label="IBM Kingston (2026-Q2)",
            vendor="ibm",
            hardware_target="superconducting",
            backend="ibm_kingston",
            captured_at="2026-04-21T10:20:30Z",
            source="seed_default",
            metrics={
                "avg_1q_gate_error": 0.00092,
                "avg_2q_gate_error": 0.0116,
                "avg_readout_error": 0.0208,
                "avg_t1_us": 91.2,
                "avg_t2_us": 73.4,
                "zz_coupling_khz": 18.1,
            },
        ),
        Snapshot(
            id="ibm_torino_2026q1",
            label="IBM Torino (2026-Q1)",
            vendor="ibm",
            hardware_target="superconducting",
            backend="ibm_torino",
            captured_at="2026-02-02T08:13:40Z",
            source="seed_default",
            metrics={
                "avg_1q_gate_error": 0.00106,
                "avg_2q_gate_error": 0.0124,
                "avg_readout_error": 0.0237,
                "avg_t1_us": 84.7,
                "avg_t2_us": 66.9,
                "zz_coupling_khz": 20.4,
            },
        ),
        Snapshot(
            id="ankaa_r3_2026q2",
            label="Ankaa R3 Replay (2026-Q2)",
            vendor="ankaa",
            hardware_target="superconducting",
            backend="ankaa_r3_replay",
            captured_at="2026-04-08T12:04:00Z",
            source="seed_default",
            metrics={
                "avg_1q_gate_error": 0.00118,
                "avg_2q_gate_error": 0.0141,
                "avg_readout_error": 0.0279,
                "avg_t1_us": 72.5,
                "avg_t2_us": 58.3,
                "zz_coupling_khz": 24.9,
            },
        ),
        Snapshot(
            id="ionq_forte_2026q2",
            label="IonQ Forte (2026-Q2)",
            vendor="ionq",
            hardware_target="trapped_ion",
            backend="ionq_forte",
            captured_at="2026-03-18T15:06:00Z",
            source="seed_default",
            metrics={
                "avg_1q_gate_error": 0.00034,
                "avg_ms_gate_error": 0.0036,
                "avg_readout_error": 0.0122,
                "avg_coherence_ms": 710.0,
                "heating_quanta_per_ms": 0.083,
                "addressing_crosstalk": 0.018,
            },
        ),
        Snapshot(
            id="xanadu_aurora_2026q2",
            label="Xanadu Aurora (2026-Q2)",
            vendor="xanadu",
            hardware_target="photonic",
            backend="xanadu_aurora",
            captured_at="2026-04-09T11:20:00Z",
            source="seed_default",
            metrics={
                "photon_loss_rate": 0.047,
                "mode_mismatch": 0.019,
                "phase_drift_deg": 2.4,
                "detector_dark_count_rate": 0.0064,
                "homodyne_efficiency": 0.937,
                "non_gaussian_injection_failure": 0.031,
            },
        ),
        Snapshot(
            id="xanadu_borealis_2026q1",
            label="Xanadu Borealis (2026-Q1)",
            vendor="xanadu",
            hardware_target="photonic",
            backend="xanadu_borealis",
            captured_at="2026-01-26T14:40:00Z",
            source="seed_default",
            metrics={
                "photon_loss_rate": 0.053,
                "mode_mismatch": 0.024,
                "phase_drift_deg": 2.9,
                "detector_dark_count_rate": 0.0078,
                "homodyne_efficiency": 0.921,
                "non_gaussian_injection_failure": 0.038,
            },
        ),
    ]


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _nduv_name(item: Any) -> str:
    if hasattr(item, "name"):
        return str(getattr(item, "name"))
    if isinstance(item, dict):
        return str(item.get("name", ""))
    return ""


def _nduv_value(item: Any) -> float | None:
    if hasattr(item, "value"):
        return parse_float(getattr(item, "value"))
    if isinstance(item, dict):
        return parse_float(item.get("value"))
    return None


def _extract_ibm_metrics(properties: Any) -> dict[str, float]:
    gate_errors_1q: list[float] = []
    gate_errors_2q: list[float] = []
    readout_errors: list[float] = []
    t1_values: list[float] = []
    t2_values: list[float] = []
    zz_values: list[float] = []

    for gate in getattr(properties, "gates", []) or []:
        qubits = getattr(gate, "qubits", []) or []
        params = getattr(gate, "parameters", []) or []
        for param in params:
            name = _nduv_name(param).lower()
            value = _nduv_value(param)
            if value is None:
                continue
            if "error" in name:
                if len(qubits) >= 2:
                    gate_errors_2q.append(value)
                else:
                    gate_errors_1q.append(value)
            if "zz" in name:
                zz_values.append(abs(value))

    for qubit in getattr(properties, "qubits", []) or []:
        for param in qubit:
            name = _nduv_name(param).lower()
            value = _nduv_value(param)
            if value is None:
                continue
            if name == "t1":
                t1_values.append(value)
            elif name == "t2":
                t2_values.append(value)
            elif "readout_error" in name or "prob_meas" in name:
                readout_errors.append(value)

    avg_1q = sum(gate_errors_1q) / len(gate_errors_1q) if gate_errors_1q else 0.001
    avg_2q = sum(gate_errors_2q) / len(gate_errors_2q) if gate_errors_2q else 0.012
    avg_readout = sum(readout_errors) / len(readout_errors) if readout_errors else 0.022
    avg_t1 = sum(t1_values) / len(t1_values) if t1_values else 80.0
    avg_t2 = sum(t2_values) / len(t2_values) if t2_values else 70.0
    avg_zz = sum(zz_values) / len(zz_values) if zz_values else 18.0

    return {
        "avg_1q_gate_error": clamp(avg_1q, 1e-5, 0.2),
        "avg_2q_gate_error": clamp(avg_2q, 1e-5, 0.3),
        "avg_readout_error": clamp(avg_readout, 1e-5, 0.4),
        "avg_t1_us": clamp(avg_t1, 1.0, 10_000.0),
        "avg_t2_us": clamp(avg_t2, 1.0, 10_000.0),
        "zz_coupling_khz": clamp(avg_zz, 0.1, 1000.0),
    }


def _load_ibm_runtime_service() -> Any:
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "qiskit-ibm-runtime unavailable; install with "
            "`python3 -m pip install --upgrade qiskit-ibm-runtime`"
        ) from exc
    return QiskitRuntimeService


def refresh_ibm_snapshots(
    *,
    ibm_backends: list[str],
    token: str | None,
    instance: str | None,
    defaults: dict[str, Snapshot],
) -> tuple[list[Snapshot], list[str]]:
    notes: list[str] = []
    if not token:
        notes.append("IBM token not set; using default IBM snapshots.")
        return [defaults["ibm_kingston_2026q2"], defaults["ibm_torino_2026q1"]], notes

    runtime_service = _load_ibm_runtime_service()
    kwargs: dict[str, Any] = {"token": token}
    if instance and instance.strip():
        kwargs["instance"] = instance.strip()

    service = runtime_service(channel="ibm_quantum_platform", **kwargs)
    now = utc_now_iso()
    refreshed: dict[str, Snapshot] = {}
    for backend_name in ibm_backends:
        backend = service.backend(backend_name)
        properties = backend.properties(refresh=True)
        if properties is None:
            notes.append(f"IBM backend {backend_name}: no properties payload; default retained.")
            continue
        metrics = _extract_ibm_metrics(properties)
        if backend_name == "ibm_kingston":
            refreshed["ibm_kingston_2026q2"] = Snapshot(
                id="ibm_kingston_2026q2",
                label="IBM Kingston (Live)",
                vendor="ibm",
                hardware_target="superconducting",
                backend="ibm_kingston",
                captured_at=now,
                source="ibm_live_metadata_probe",
                metrics=metrics,
            )
        elif backend_name == "ibm_torino":
            refreshed["ibm_torino_2026q1"] = Snapshot(
                id="ibm_torino_2026q1",
                label="IBM Torino (Live)",
                vendor="ibm",
                hardware_target="superconducting",
                backend="ibm_torino",
                captured_at=now,
                source="ibm_live_metadata_probe",
                metrics=metrics,
            )

    if "ibm_kingston_2026q2" not in refreshed:
        refreshed["ibm_kingston_2026q2"] = defaults["ibm_kingston_2026q2"]
    if "ibm_torino_2026q1" not in refreshed:
        refreshed["ibm_torino_2026q1"] = defaults["ibm_torino_2026q1"]
    return [refreshed["ibm_kingston_2026q2"], refreshed["ibm_torino_2026q1"]], notes


def refresh_ankaa_snapshot(ankaa_fixture_path: Path, default_snapshot: Snapshot) -> tuple[Snapshot, list[str]]:
    notes: list[str] = []
    if not ankaa_fixture_path.is_file():
        notes.append(f"Ankaa fixture not found at {ankaa_fixture_path}; default retained.")
        return default_snapshot, notes
    try:
        payload = json.loads(ankaa_fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Failed to parse Ankaa fixture: {exc}; default retained.")
        return default_snapshot, notes

    hard = payload.get("hard_measurements")
    if not isinstance(hard, dict) or not hard:
        notes.append("Ankaa fixture missing hard_measurements; default retained.")
        return default_snapshot, notes

    total = 0
    ones = 0
    flips = 0
    flip_ref = 0
    for matrix in hard.values():
        if not isinstance(matrix, list):
            continue
        for row in matrix:
            if not isinstance(row, list) or not row:
                continue
            prev = int(row[0]) if row else 0
            for raw in row:
                value = 1 if int(raw) != 0 else 0
                total += 1
                ones += value
                if flip_ref > 0 and value != prev:
                    flips += 1
                prev = value
                flip_ref += 1

    if total <= 0:
        notes.append("Ankaa fixture has no usable bit entries; default retained.")
        return default_snapshot, notes

    activity = ones / total
    flip_rate = flips / max(1, flip_ref - 1)
    now = utc_now_iso()
    snapshot = Snapshot(
        id=default_snapshot.id,
        label="Ankaa R3 Replay (Live Fixture)",
        vendor="ankaa",
        hardware_target="superconducting",
        backend="ankaa_r3_replay",
        captured_at=now,
        source="ankaa_fixture_refresh",
        metrics={
            "avg_1q_gate_error": clamp(0.0007 + activity * 0.0021, 0.0001, 0.03),
            "avg_2q_gate_error": clamp(0.0075 + flip_rate * 0.05, 0.001, 0.08),
            "avg_readout_error": clamp(0.009 + activity * 0.045, 0.002, 0.12),
            "avg_t1_us": clamp(95 - flip_rate * 620, 20, 250),
            "avg_t2_us": clamp(80 - flip_rate * 560, 15, 220),
            "zz_coupling_khz": clamp(12 + flip_rate * 65, 2, 120),
        },
    )
    return snapshot, notes


def refresh_xanadu_snapshots(
    *,
    counts_json_path: Path,
    default_aurora: Snapshot,
    default_borealis: Snapshot,
) -> tuple[list[Snapshot], list[str]]:
    notes: list[str] = []
    if not counts_json_path.is_file():
        notes.append(f"Xanadu counts JSON not found at {counts_json_path}; defaults retained.")
        return [default_aurora, default_borealis], notes

    try:
        payload = json.loads(counts_json_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Failed to parse Xanadu counts JSON: {exc}; defaults retained.")
        return [default_aurora, default_borealis], notes

    rows = payload.get("counts")
    if not isinstance(rows, list) or not rows:
        notes.append("Xanadu counts JSON has no counts array; defaults retained.")
        return [default_aurora, default_borealis], notes

    total = 0
    detectors = 0
    nonzero_sum = 0.0
    dispersion_weight = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        sample = row.get("sample")
        count = int(row.get("count", 0))
        if not isinstance(sample, list) or count <= 0:
            continue
        if detectors == 0:
            detectors = max(1, len(sample))
        total += count
        nonzero = sum(1 for value in sample if int(value) != 0)
        nonzero_sum += nonzero * count
        mean_abs = sum(abs(int(value)) for value in sample) / max(1, len(sample))
        dispersion_weight += mean_abs * count

    if total <= 0 or detectors <= 0:
        notes.append("Xanadu counts JSON has no usable sample counts; defaults retained.")
        return [default_aurora, default_borealis], notes

    nonzero_ratio = nonzero_sum / (total * detectors)
    mean_dispersion = dispersion_weight / total

    photon_loss_rate = clamp(0.02 + (1 - nonzero_ratio) * 0.08, 0.005, 0.2)
    mode_mismatch = clamp(0.01 + mean_dispersion * 0.018, 0.005, 0.2)
    phase_drift_deg = clamp(1.4 + mean_dispersion * 1.8 + (1 - nonzero_ratio) * 1.2, 0.4, 8.0)
    detector_dark_count_rate = clamp(0.002 + (1 - nonzero_ratio) * 0.012, 0.0005, 0.06)
    homodyne_efficiency = clamp(0.97 - photon_loss_rate * 0.55 - mode_mismatch * 0.32, 0.75, 0.99)
    non_gaussian_injection_failure = clamp(0.015 + mode_mismatch * 0.7 + photon_loss_rate * 0.4, 0.01, 0.3)

    now = utc_now_iso()
    aurora = Snapshot(
        id=default_aurora.id,
        label="Xanadu Aurora (Live Counts)",
        vendor="xanadu",
        hardware_target="photonic",
        backend="xanadu_aurora",
        captured_at=now,
        source="xanadu_counts_refresh",
        metrics={
            "photon_loss_rate": photon_loss_rate,
            "mode_mismatch": mode_mismatch,
            "phase_drift_deg": phase_drift_deg,
            "detector_dark_count_rate": detector_dark_count_rate,
            "homodyne_efficiency": homodyne_efficiency,
            "non_gaussian_injection_failure": non_gaussian_injection_failure,
        },
    )
    borealis = Snapshot(
        id=default_borealis.id,
        label="Xanadu Borealis (Live Counts Proxy)",
        vendor="xanadu",
        hardware_target="photonic",
        backend="xanadu_borealis",
        captured_at=now,
        source="xanadu_counts_refresh",
        metrics={
            "photon_loss_rate": clamp(photon_loss_rate * 1.12, 0.005, 0.25),
            "mode_mismatch": clamp(mode_mismatch * 1.2, 0.005, 0.25),
            "phase_drift_deg": clamp(phase_drift_deg * 1.15, 0.4, 10.0),
            "detector_dark_count_rate": clamp(detector_dark_count_rate * 1.22, 0.0005, 0.08),
            "homodyne_efficiency": clamp(homodyne_efficiency * 0.985, 0.7, 0.99),
            "non_gaussian_injection_failure": clamp(non_gaussian_injection_failure * 1.2, 0.01, 0.35),
        },
    )
    return [aurora, borealis], notes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        default="",
        help="Repo root path. If omitted, inferred from script location.",
    )
    parser.add_argument(
        "--out",
        default="hardware_integration/calibration/vendor_calibrations.live.json",
        help="Catalog output path relative to workspace root.",
    )
    parser.add_argument(
        "--ibm-backends",
        default="ibm_kingston,ibm_torino",
        help="Comma-separated IBM backend names for metadata ingestion.",
    )
    parser.add_argument(
        "--ibm-token-env",
        default="IBM_QUANTUM_API_KEY",
        help="Environment variable with IBM token.",
    )
    parser.add_argument(
        "--ibm-instance",
        default="",
        help="Optional IBM instance/CRN scope.",
    )
    parser.add_argument(
        "--ankaa-fixture",
        default="hardware_integration/ankaa/superconducting/ankaa_fixture_example.json",
        help="Ankaa replay fixture path relative to workspace root.",
    )
    parser.add_argument(
        "--xanadu-counts-json",
        default="hardware_integration/xanadu/xanadu_gkp_counts_example.json",
        help="Xanadu counts JSON path relative to workspace root.",
    )
    return parser.parse_args()


def resolve_workspace_root(raw: str) -> Path:
    if raw.strip():
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def main() -> int:
    args = parse_args()
    workspace_root = resolve_workspace_root(args.workspace_root)
    out_path = (workspace_root / args.out).resolve()
    ankaa_fixture_path = (workspace_root / args.ankaa_fixture).resolve()
    xanadu_counts_path = (workspace_root / args.xanadu_counts_json).resolve()

    defaults = {snapshot.id: snapshot for snapshot in default_catalog()}
    notes: list[str] = []

    ibm_backends = [item.strip() for item in args.ibm_backends.split(",") if item.strip()]
    if not ibm_backends:
        ibm_backends = ["ibm_kingston", "ibm_torino"]
    ibm_token = os.environ.get(args.ibm_token_env, "").strip() or None
    ibm_snapshots, ibm_notes = refresh_ibm_snapshots(
        ibm_backends=ibm_backends,
        token=ibm_token,
        instance=args.ibm_instance.strip() or None,
        defaults=defaults,
    )
    notes.extend(ibm_notes)

    ankaa_snapshot, ankaa_notes = refresh_ankaa_snapshot(
        ankaa_fixture_path=ankaa_fixture_path,
        default_snapshot=defaults["ankaa_r3_2026q2"],
    )
    notes.extend(ankaa_notes)

    xanadu_snapshots, xanadu_notes = refresh_xanadu_snapshots(
        counts_json_path=xanadu_counts_path,
        default_aurora=defaults["xanadu_aurora_2026q2"],
        default_borealis=defaults["xanadu_borealis_2026q1"],
    )
    notes.extend(xanadu_notes)

    snapshots: list[Snapshot] = []
    snapshots.extend(ibm_snapshots)
    snapshots.append(ankaa_snapshot)
    snapshots.append(defaults["ionq_forte_2026q2"])
    snapshots.extend(xanadu_snapshots)

    payload = {
        "schema_version": "v1",
        "generated_at": utc_now_iso(),
        "refresh_mode": "periodic_live_ingest",
        "snapshots": [
            {
                "id": snapshot.id,
                "label": snapshot.label,
                "vendor": snapshot.vendor,
                "hardware_target": snapshot.hardware_target,
                "backend": snapshot.backend,
                "captured_at": snapshot.captured_at,
                "source": snapshot.source,
                "metrics": {key: round(float(value), 8) for key, value in snapshot.metrics.items()},
            }
            for snapshot in snapshots
        ],
        "notes": notes,
    }
    _atomic_write_json(out_path, payload)
    print(f"[calibration-refresh] wrote {out_path}")
    print(f"[calibration-refresh] snapshots={len(snapshots)} notes={len(notes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
