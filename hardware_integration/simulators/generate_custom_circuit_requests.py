#!/usr/bin/env python3
"""Generate custom-circuit decoder_io requests with a two-layer noise model.

Layer 1: physical channel
  - surface mode: stochastic Pauli frame perturbations
  - gkp mode: analog displacement drift/kicks mapped to effective Pauli bits

Layer 2: outer stabilizer extraction
  - repeated-round parity extraction over a distance-d surface-code geometry
  - detector events emitted as syndrome changes between rounds
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPERCONDUCTING_GATES = {"h", "x", "y", "z", "s", "t", "rx", "ry", "rz", "cx", "cz", "measure"}
TRAPPED_ION_GATES = {"x", "y", "z", "rx", "ry", "rz", "ms", "measure"}
PHOTONIC_GATES = {"disp", "sq", "phase", "bs", "kerr", "cubic", "measure"}
VALID_GATES = SUPERCONDUCTING_GATES | TRAPPED_ION_GATES | PHOTONIC_GATES
CIRCUIT_HARDWARE_TARGETS = ("superconducting", "trapped_ion", "photonic")
CIRCUIT_NOISE_PRESETS = ("low", "medium", "high", "custom")

NOISE_CHANNELS_BY_TARGET: dict[str, tuple[str, ...]] = {
    "superconducting": (
        "amplitude_damping",
        "dephasing",
        "depolarizing",
        "readout_error",
        "crosstalk_zz",
    ),
    "trapped_ion": (
        "dephasing",
        "ms_overrotation",
        "motional_heating",
        "addressing_crosstalk",
        "spam_error",
    ),
    "photonic": (
        "photon_loss",
        "mode_mismatch",
        "phase_drift",
        "detector_dark_count",
        "non_gaussian_injection_failure",
    ),
}

CHANNEL_PROFILE_CONTRIBUTIONS: dict[str, dict[str, float]] = {
    "amplitude_damping": {
        "surface_background_scale": 0.70,
        "gkp_sigma_scale": 0.45,
        "gkp_jump_scale": 0.25,
    },
    "dephasing": {
        "surface_z_bias": 0.55,
        "surface_background_scale": 0.25,
        "gkp_sigma_scale": 0.35,
    },
    "depolarizing": {
        "surface_gate_scale": 0.80,
        "gkp_jump_scale": 0.40,
    },
    "readout_error": {
        "surface_meas_scale": 1.00,
        "gkp_meas_scale": 0.90,
    },
    "crosstalk_zz": {
        "surface_gate_scale": 0.25,
        "surface_z_bias": 0.60,
        "gkp_jump_scale": 0.25,
    },
    "ms_overrotation": {
        "surface_gate_scale": 0.90,
        "gkp_jump_scale": 0.50,
    },
    "motional_heating": {
        "surface_background_scale": 0.85,
        "gkp_sigma_scale": 0.80,
        "gkp_jump_scale": 0.35,
    },
    "addressing_crosstalk": {
        "surface_gate_scale": 0.40,
        "surface_z_bias": 0.25,
        "gkp_jump_scale": 0.30,
    },
    "spam_error": {
        "surface_meas_scale": 1.00,
        "gkp_meas_scale": 0.95,
    },
    "photon_loss": {
        "surface_background_scale": 1.00,
        "surface_meas_scale": 0.45,
        "gkp_sigma_scale": 1.10,
        "gkp_jump_scale": 0.65,
    },
    "mode_mismatch": {
        "surface_gate_scale": 0.85,
        "gkp_sigma_scale": 0.55,
    },
    "phase_drift": {
        "surface_z_bias": 0.75,
        "gkp_sigma_scale": 0.60,
        "gkp_meas_scale": 0.25,
    },
    "detector_dark_count": {
        "surface_meas_scale": 1.20,
        "gkp_meas_scale": 1.15,
    },
    "non_gaussian_injection_failure": {
        "surface_gate_scale": 0.60,
        "gkp_sigma_scale": 0.45,
        "gkp_jump_scale": 1.00,
    },
}


@dataclass(frozen=True)
class GateOp:
    gate: str
    target: int
    control: int | None
    parameter: float | None


@dataclass(frozen=True)
class SurfaceGeometry:
    distance: int
    n_data: int
    n_x: int
    n_z: int
    x_supports: list[list[int]]
    z_supports: list[list[int]]


@dataclass(frozen=True)
class FrameworkStyle:
    q_bias: float
    p_bias: float
    threshold_scale: float


@dataclass(frozen=True)
class HardwareNoiseProfile:
    surface_gate_scale: float
    surface_meas_scale: float
    surface_background_scale: float
    surface_z_bias: float
    gkp_sigma_scale: float
    gkp_jump_scale: float
    gkp_meas_scale: float


@dataclass(frozen=True)
class CircuitNoiseChannel:
    enabled: bool
    level: float


@dataclass(frozen=True)
class CircuitNoiseConfig:
    preset: str
    channels: dict[str, CircuitNoiseChannel]


@dataclass(frozen=True)
class CompileArtifactContext:
    total_duration_ns: float
    transpiled_depth: int
    swap_insertions: int
    schedule_conflicts: int


@dataclass(frozen=True)
class VendorCalibrationSnapshot:
    id: str
    vendor: str
    hardware_target: str
    backend: str
    captured_at: str
    source: str
    metrics: dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="Output directory for request artifacts.")
    parser.add_argument("--framework", required=True, choices=("pennylane", "qiskit", "cirq"))
    parser.add_argument("--shots", type=int, required=True, help="Number of request rows.")
    parser.add_argument("--distance", type=int, default=5, help="Surface distance (odd and >=3).")
    parser.add_argument("--rounds", type=int, default=4, help="Stabilizer rounds per request.")
    parser.add_argument("--error-rate", type=float, default=0.08, help="Base noise intensity.")
    parser.add_argument("--sigma", type=float, default=0.18, help="Physical noise sigma metadata.")
    parser.add_argument("--seed", type=int, default=20260515, help="Random seed.")
    parser.add_argument("--code-family", choices=("surface", "gkp"), default="surface")
    parser.add_argument("--circuit-name", default="custom_design")
    parser.add_argument("--circuit-qubits", type=int, required=True)
    parser.add_argument("--circuit-qasm", default="", help="Optional OpenQASM payload for metadata.")
    parser.add_argument(
        "--circuit-hardware-target",
        default="superconducting",
        choices=CIRCUIT_HARDWARE_TARGETS,
        help="Hardware target profile for custom-circuit noise synthesis.",
    )
    parser.add_argument(
        "--circuit-gate-plan",
        required=True,
        help="JSON array for gate operations [{gate,target,control?,parameter?}].",
    )
    parser.add_argument(
        "--circuit-noise-config",
        default="",
        help="Optional JSON payload for hardware-specific noise channels.",
    )
    parser.add_argument(
        "--circuit-detector-model",
        default="",
        help="Optional detector model hint (threshold|pnr_approx) for photonic synthesis.",
    )
    parser.add_argument(
        "--circuit-compile-artifact",
        default="",
        help="Optional deterministic compile artifact JSON from UI/compiler.",
    )
    parser.add_argument(
        "--circuit-calibration-snapshot",
        default="",
        help="Optional vendor calibration snapshot id to bind compile/noise synthesis.",
    )
    parser.add_argument(
        "--circuit-calibration-catalog",
        default="",
        help="Optional path to vendor calibration catalog JSON.",
    )
    return parser.parse_args()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


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


def allowed_gates_for_framework_target(framework: str, hardware_target: str) -> set[str]:
    if hardware_target == "photonic":
        return PHOTONIC_GATES
    if hardware_target == "trapped_ion":
        if framework != "pennylane":
            return SUPERCONDUCTING_GATES
        return TRAPPED_ION_GATES
    return SUPERCONDUCTING_GATES


def parse_gate_plan(raw: str, qubits: int, allowed_gates: set[str], hardware_target: str) -> list[GateOp]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid --circuit-gate-plan JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise SystemExit("Error: --circuit-gate-plan must be a JSON array.")

    ops: list[GateOp] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SystemExit(f"Error: gate plan entry #{idx + 1} must be an object.")
        gate = str(item.get("gate", "")).strip().lower()
        if gate not in VALID_GATES:
            raise SystemExit(f"Error: unsupported gate '{gate}' at entry #{idx + 1}.")
        if gate not in allowed_gates:
            allowed_label = ", ".join(sorted(allowed_gates))
            raise SystemExit(
                f"Error: gate '{gate}' is not allowed for hardware target '{hardware_target}'. "
                f"Allowed gates: {allowed_label}."
            )
        try:
            target = int(item.get("target"))
        except (TypeError, ValueError):
            raise SystemExit(f"Error: gate entry #{idx + 1} has invalid target.")
        if target < 0 or target >= qubits:
            raise SystemExit(f"Error: gate entry #{idx + 1} target out of range for {qubits} qubits.")

        control_raw = item.get("control", None)
        control = None if control_raw is None else int(control_raw)
        if gate in {"cx", "cz", "ms", "bs"}:
            if control is None:
                raise SystemExit(f"Error: gate entry #{idx + 1} requires control qubit.")
            if control < 0 or control >= qubits:
                raise SystemExit(f"Error: gate entry #{idx + 1} control out of range for {qubits} qubits.")
            if control == target:
                raise SystemExit(f"Error: gate entry #{idx + 1} control and target must differ.")
        else:
            control = None

        parameter = None
        if gate in {"rx", "ry", "rz", "ms", "disp", "sq", "phase", "bs", "kerr", "cubic"}:
            parameter_raw = item.get("parameter", None)
            if parameter_raw is None:
                raise SystemExit(f"Error: gate entry #{idx + 1} requires parameter.")
            try:
                parameter = float(parameter_raw)
            except (TypeError, ValueError):
                raise SystemExit(f"Error: gate entry #{idx + 1} parameter must be numeric.")

        ops.append(GateOp(gate=gate, target=target, control=control, parameter=parameter))

    if not ops:
        raise SystemExit("Error: circuit gate plan must include at least one operation.")
    return ops


def build_data_adjacency(geom: SurfaceGeometry) -> list[list[int]]:
    neighbors: list[set[int]] = [set() for _ in range(geom.n_data)]

    for support in geom.x_supports:
        for i, left in enumerate(support):
            for right in support[i + 1 :]:
                neighbors[left].add(right)
                neighbors[right].add(left)
    for support in geom.z_supports:
        for i, left in enumerate(support):
            for right in support[i + 1 :]:
                neighbors[left].add(right)
                neighbors[right].add(left)

    return [sorted(entry) for entry in neighbors]


def map_logical_to_data(circuit_qubits: int, n_data: int) -> list[int]:
    if circuit_qubits <= 1:
        return [0]
    mapping: list[int] = []
    for q in range(circuit_qubits):
        idx = int(round((q * (n_data - 1)) / float(circuit_qubits - 1)))
        mapping.append(clamp(idx, 0, n_data - 1))  # type: ignore[arg-type]
    return [int(v) for v in mapping]


def framework_style(framework: str, hardware_target: str) -> FrameworkStyle:
    if framework == "pennylane" and hardware_target == "trapped_ion":
        return FrameworkStyle(q_bias=-0.015 * math.sqrt(math.pi), p_bias=0.02 * math.sqrt(math.pi), threshold_scale=0.9)
    if framework == "pennylane" and hardware_target == "photonic":
        return FrameworkStyle(q_bias=0.04 * math.sqrt(math.pi), p_bias=-0.02 * math.sqrt(math.pi), threshold_scale=1.12)
    if framework == "pennylane":
        return FrameworkStyle(q_bias=-0.03 * math.sqrt(math.pi), p_bias=0.04 * math.sqrt(math.pi), threshold_scale=0.94)
    if framework == "qiskit":
        return FrameworkStyle(q_bias=0.0, p_bias=0.0, threshold_scale=1.0)
    return FrameworkStyle(q_bias=0.02 * math.sqrt(math.pi), p_bias=-0.02 * math.sqrt(math.pi), threshold_scale=1.08)


def hardware_noise_profile(hardware_target: str) -> HardwareNoiseProfile:
    if hardware_target == "trapped_ion":
        return HardwareNoiseProfile(
            surface_gate_scale=0.74,
            surface_meas_scale=0.82,
            surface_background_scale=0.58,
            surface_z_bias=0.92,
            gkp_sigma_scale=0.88,
            gkp_jump_scale=0.55,
            gkp_meas_scale=0.84,
        )
    if hardware_target == "photonic":
        return HardwareNoiseProfile(
            surface_gate_scale=1.18,
            surface_meas_scale=1.12,
            surface_background_scale=1.24,
            surface_z_bias=1.24,
            gkp_sigma_scale=1.24,
            gkp_jump_scale=1.38,
            gkp_meas_scale=1.16,
        )
    return HardwareNoiseProfile(
        surface_gate_scale=1.0,
        surface_meas_scale=1.0,
        surface_background_scale=1.0,
        surface_z_bias=1.0,
        gkp_sigma_scale=1.0,
        gkp_jump_scale=1.0,
        gkp_meas_scale=1.0,
    )


def noise_preset_level(preset: str) -> float:
    if preset == "low":
        return 0.25
    if preset == "high":
        return 0.8
    return 0.5


def parse_circuit_noise_config(raw: str, hardware_target: str) -> CircuitNoiseConfig | None:
    payload_text = raw.strip()
    if not payload_text:
        return None

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid --circuit-noise-config JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit("Error: --circuit-noise-config must be a JSON object.")

    preset_raw = payload.get("preset", "medium")
    if not isinstance(preset_raw, str):
        raise SystemExit("Error: --circuit-noise-config.preset must be a string.")
    preset = preset_raw.strip().lower()
    if preset not in CIRCUIT_NOISE_PRESETS:
        allowed = ", ".join(CIRCUIT_NOISE_PRESETS)
        raise SystemExit(f"Error: --circuit-noise-config.preset must be one of: {allowed}.")

    channels_raw = payload.get("channels", {})
    if channels_raw is None:
        channels_raw = {}
    if not isinstance(channels_raw, dict):
        raise SystemExit("Error: --circuit-noise-config.channels must be an object.")

    allowed_channels = set(NOISE_CHANNELS_BY_TARGET[hardware_target])
    unknown_channels = sorted(str(key) for key in channels_raw.keys() if str(key) not in allowed_channels)
    if unknown_channels:
        raise SystemExit(
            "Error: --circuit-noise-config contains unsupported channel(s) for "
            f"{hardware_target}: {', '.join(unknown_channels)}."
        )

    default_level = noise_preset_level(preset)
    default_enabled = preset != "custom"
    channels: dict[str, CircuitNoiseChannel] = {}
    for key in NOISE_CHANNELS_BY_TARGET[hardware_target]:
        item = channels_raw.get(key, None)
        if item is None:
            channels[key] = CircuitNoiseChannel(enabled=default_enabled, level=default_level)
            continue
        if not isinstance(item, dict):
            raise SystemExit(
                f"Error: --circuit-noise-config.channels.{key} must be an object with enabled/level fields."
            )

        enabled_raw = item.get("enabled", default_enabled)
        if not isinstance(enabled_raw, bool):
            raise SystemExit(f"Error: --circuit-noise-config.channels.{key}.enabled must be boolean.")
        level_raw = item.get("level", default_level)
        try:
            level = float(level_raw)
        except (TypeError, ValueError):
            raise SystemExit(f"Error: --circuit-noise-config.channels.{key}.level must be numeric.")
        channels[key] = CircuitNoiseChannel(enabled=enabled_raw, level=clamp(level, 0.0, 1.0))

    return CircuitNoiseConfig(preset=preset, channels=channels)


def effective_noise_profile(
    hardware_target: str, noise_config: CircuitNoiseConfig | None
) -> tuple[HardwareNoiseProfile, dict[str, float]]:
    base = hardware_noise_profile(hardware_target)
    factors = {
        "surface_gate_scale": 1.0,
        "surface_meas_scale": 1.0,
        "surface_background_scale": 1.0,
        "surface_z_bias": 1.0,
        "gkp_sigma_scale": 1.0,
        "gkp_jump_scale": 1.0,
        "gkp_meas_scale": 1.0,
    }
    if noise_config is not None:
        for key, channel in noise_config.channels.items():
            if not channel.enabled:
                continue
            contribution = CHANNEL_PROFILE_CONTRIBUTIONS.get(key, {})
            for factor_key, coefficient in contribution.items():
                factors[factor_key] += coefficient * channel.level

    for factor_key, value in list(factors.items()):
        factors[factor_key] = clamp(value, 0.5, 3.0)

    profile = HardwareNoiseProfile(
        surface_gate_scale=base.surface_gate_scale * factors["surface_gate_scale"],
        surface_meas_scale=base.surface_meas_scale * factors["surface_meas_scale"],
        surface_background_scale=base.surface_background_scale * factors["surface_background_scale"],
        surface_z_bias=base.surface_z_bias * factors["surface_z_bias"],
        gkp_sigma_scale=base.gkp_sigma_scale * factors["gkp_sigma_scale"],
        gkp_jump_scale=base.gkp_jump_scale * factors["gkp_jump_scale"],
        gkp_meas_scale=base.gkp_meas_scale * factors["gkp_meas_scale"],
    )
    return profile, factors


def noise_config_to_dict(noise_config: CircuitNoiseConfig | None) -> dict[str, Any]:
    if noise_config is None:
        return {}
    channels: dict[str, dict[str, Any]] = {}
    for key, channel in noise_config.channels.items():
        channels[key] = {
            "enabled": channel.enabled,
            "level": round(channel.level, 4),
        }
    return {"preset": noise_config.preset, "channels": channels}


def noise_profile_to_dict(profile: HardwareNoiseProfile) -> dict[str, float]:
    return {
        "surface_gate_scale": round(profile.surface_gate_scale, 6),
        "surface_meas_scale": round(profile.surface_meas_scale, 6),
        "surface_background_scale": round(profile.surface_background_scale, 6),
        "surface_z_bias": round(profile.surface_z_bias, 6),
        "gkp_sigma_scale": round(profile.gkp_sigma_scale, 6),
        "gkp_jump_scale": round(profile.gkp_jump_scale, 6),
        "gkp_meas_scale": round(profile.gkp_meas_scale, 6),
    }


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_snapshot_from_payload(raw: Any) -> VendorCalibrationSnapshot | None:
    if not isinstance(raw, dict):
        return None
    try:
        snapshot_id = str(raw.get("id", "")).strip()
        vendor = str(raw.get("vendor", "")).strip().lower()
        hardware_target = str(raw.get("hardware_target", "")).strip().lower()
        backend = str(raw.get("backend", "")).strip()
        captured_at = str(raw.get("captured_at", "")).strip()
        source = str(raw.get("source", "")).strip()
    except Exception:  # noqa: BLE001
        return None

    if not snapshot_id or not vendor or not hardware_target or not backend or not captured_at or not source:
        return None
    if hardware_target not in CIRCUIT_HARDWARE_TARGETS:
        return None
    metrics_raw = raw.get("metrics", {})
    if not isinstance(metrics_raw, dict):
        metrics_raw = {}
    metrics: dict[str, float] = {}
    for key, value in metrics_raw.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(numeric) or math.isinf(numeric):
            continue
        metrics[str(key)] = numeric

    return VendorCalibrationSnapshot(
        id=snapshot_id,
        vendor=vendor,
        hardware_target=hardware_target,
        backend=backend,
        captured_at=captured_at,
        source=source,
        metrics=metrics,
    )


def vendor_calibration_catalog(catalog_path: str | None = None) -> dict[str, VendorCalibrationSnapshot]:
    snapshots = [
        VendorCalibrationSnapshot(
            id="ibm_kingston_2026q2",
            vendor="ibm",
            hardware_target="superconducting",
            backend="ibm_kingston",
            captured_at="2026-04-21T10:20:30Z",
            source="ibm_live_metadata_probe",
            metrics={
                "avg_1q_gate_error": 0.00092,
                "avg_2q_gate_error": 0.0116,
                "avg_readout_error": 0.0208,
                "avg_t1_us": 91.2,
                "avg_t2_us": 73.4,
                "zz_coupling_khz": 18.1,
            },
        ),
        VendorCalibrationSnapshot(
            id="ibm_torino_2026q1",
            vendor="ibm",
            hardware_target="superconducting",
            backend="ibm_torino",
            captured_at="2026-02-02T08:13:40Z",
            source="ibm_live_metadata_probe",
            metrics={
                "avg_1q_gate_error": 0.00106,
                "avg_2q_gate_error": 0.0124,
                "avg_readout_error": 0.0237,
                "avg_t1_us": 84.7,
                "avg_t2_us": 66.9,
                "zz_coupling_khz": 20.4,
            },
        ),
        VendorCalibrationSnapshot(
            id="ankaa_r3_2026q2",
            vendor="ankaa",
            hardware_target="superconducting",
            backend="ankaa_r3_replay",
            captured_at="2026-04-08T12:04:00Z",
            source="ankaa_fixture_calibration",
            metrics={
                "avg_1q_gate_error": 0.00118,
                "avg_2q_gate_error": 0.0141,
                "avg_readout_error": 0.0279,
                "avg_t1_us": 72.5,
                "avg_t2_us": 58.3,
                "zz_coupling_khz": 24.9,
            },
        ),
        VendorCalibrationSnapshot(
            id="ionq_forte_2026q2",
            vendor="ionq",
            hardware_target="trapped_ion",
            backend="ionq_forte",
            captured_at="2026-03-18T15:06:00Z",
            source="pennylane_hardware_profile",
            metrics={
                "avg_1q_gate_error": 0.00034,
                "avg_ms_gate_error": 0.0036,
                "avg_readout_error": 0.0122,
                "avg_coherence_ms": 710.0,
                "heating_quanta_per_ms": 0.083,
                "addressing_crosstalk": 0.018,
            },
        ),
        VendorCalibrationSnapshot(
            id="xanadu_aurora_2026q2",
            vendor="xanadu",
            hardware_target="photonic",
            backend="xanadu_aurora",
            captured_at="2026-04-09T11:20:00Z",
            source="xanadu_remote_slice_calibration",
            metrics={
                "photon_loss_rate": 0.047,
                "mode_mismatch": 0.019,
                "phase_drift_deg": 2.4,
                "detector_dark_count_rate": 0.0064,
                "homodyne_efficiency": 0.937,
                "non_gaussian_injection_failure": 0.031,
            },
        ),
        VendorCalibrationSnapshot(
            id="xanadu_borealis_2026q1",
            vendor="xanadu",
            hardware_target="photonic",
            backend="xanadu_borealis",
            captured_at="2026-01-26T14:40:00Z",
            source="xanadu_remote_slice_calibration",
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
    catalog = {snapshot.id: snapshot for snapshot in snapshots}

    if catalog_path is not None and catalog_path.strip():
        live_path = Path(catalog_path).expanduser().resolve()
    else:
        live_path = repository_root() / "hardware_integration/calibration/vendor_calibrations.live.json"

    if not live_path.is_file():
        return catalog

    try:
        payload = json.loads(live_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return catalog

    raw_snapshots = payload.get("snapshots", [])
    if not isinstance(raw_snapshots, list):
        return catalog
    for raw in raw_snapshots:
        snapshot = _parse_snapshot_from_payload(raw)
        if snapshot is None:
            continue
        catalog[snapshot.id] = snapshot

    return catalog


def default_calibration_snapshot_id(framework: str, hardware_target: str) -> str | None:
    if hardware_target == "photonic":
        return "xanadu_aurora_2026q2"
    if hardware_target == "trapped_ion":
        return "ionq_forte_2026q2"
    if framework in {"qiskit", "cirq"}:
        return "ibm_kingston_2026q2"
    return "ankaa_r3_2026q2"


def resolve_calibration_snapshot(
    *,
    raw_snapshot_id: str,
    raw_catalog_path: str,
    compile_artifact: dict[str, Any] | None,
    framework: str,
    hardware_target: str,
) -> VendorCalibrationSnapshot | None:
    catalog = vendor_calibration_catalog(raw_catalog_path)
    candidate = raw_snapshot_id.strip().lower()
    if not candidate and compile_artifact is not None:
        artifact_candidate = str(compile_artifact.get("calibration_snapshot_id", "")).strip().lower()
        candidate = artifact_candidate
    if not candidate:
        fallback = default_calibration_snapshot_id(framework, hardware_target)
        candidate = fallback or ""
    if not candidate:
        return None
    snapshot = catalog.get(candidate)
    if snapshot is None:
        known_ids = ", ".join(sorted(catalog.keys()))
        raise SystemExit(
            "Error: unknown --circuit-calibration-snapshot "
            f"{candidate!r}. Known snapshots: {known_ids}."
        )
    if snapshot.hardware_target != hardware_target:
        raise SystemExit(
            "Error: calibration snapshot "
            f"{snapshot.id!r} targets {snapshot.hardware_target} but circuit target is {hardware_target}."
        )
    return snapshot


def calibration_snapshot_to_dict(snapshot: VendorCalibrationSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    return {
        "id": snapshot.id,
        "vendor": snapshot.vendor,
        "hardware_target": snapshot.hardware_target,
        "backend": snapshot.backend,
        "captured_at": snapshot.captured_at,
        "source": snapshot.source,
        "metrics": {key: round(float(value), 8) for key, value in snapshot.metrics.items()},
    }


def apply_vendor_calibration_adjustments(
    profile: HardwareNoiseProfile,
    hardware_target: str,
    snapshot: VendorCalibrationSnapshot | None,
) -> tuple[HardwareNoiseProfile, dict[str, float]]:
    factors = {
        "cal_one_qubit_scale": 1.0,
        "cal_two_qubit_scale": 1.0,
        "cal_measurement_scale": 1.0,
        "cal_timing_scale": 1.0,
        "cal_background_scale": 1.0,
        "cal_z_bias_scale": 1.0,
    }
    if snapshot is None:
        return profile, factors

    metrics = snapshot.metrics
    if hardware_target == "superconducting":
        one_q = float(metrics.get("avg_1q_gate_error", 0.001))
        two_q = float(metrics.get("avg_2q_gate_error", 0.012))
        readout = float(metrics.get("avg_readout_error", 0.022))
        t1_us = float(metrics.get("avg_t1_us", 80.0))
        t2_us = float(metrics.get("avg_t2_us", 70.0))
        zz_khz = float(metrics.get("zz_coupling_khz", 18.0))
        factors["cal_one_qubit_scale"] = clamp(0.75 + (one_q / 0.0012) * 0.25, 0.65, 2.2)
        factors["cal_two_qubit_scale"] = clamp(0.6 + (two_q / 0.012) * 0.85, 0.65, 2.3)
        factors["cal_measurement_scale"] = clamp(0.5 + (readout / 0.022) * 0.95, 0.6, 2.3)
        factors["cal_timing_scale"] = clamp(0.88 + (100 / max(t1_us, 1.0)) * 0.06 + (90 / max(t2_us, 1.0)) * 0.06, 0.8, 1.25)
        factors["cal_background_scale"] = clamp((82 / max(t1_us, 1.0)) * 0.55 + (72 / max(t2_us, 1.0)) * 0.45, 0.55, 2.3)
        factors["cal_z_bias_scale"] = clamp(0.85 + zz_khz / 36.0, 0.8, 2.3)
    elif hardware_target == "trapped_ion":
        one_q = float(metrics.get("avg_1q_gate_error", 0.0004))
        ms_err = float(metrics.get("avg_ms_gate_error", 0.0035))
        readout = float(metrics.get("avg_readout_error", 0.012))
        coherence_ms = float(metrics.get("avg_coherence_ms", 700.0))
        heating = float(metrics.get("heating_quanta_per_ms", 0.08))
        addressing = float(metrics.get("addressing_crosstalk", 0.018))
        factors["cal_one_qubit_scale"] = clamp(0.7 + (one_q / 0.00045) * 0.35, 0.6, 2.0)
        factors["cal_two_qubit_scale"] = clamp(0.65 + (ms_err / 0.004) * 0.8, 0.65, 2.2)
        factors["cal_measurement_scale"] = clamp(0.55 + (readout / 0.013) * 0.9, 0.6, 2.2)
        factors["cal_timing_scale"] = clamp(0.82 + (800 / max(coherence_ms, 1.0)) * 0.08, 0.78, 1.2)
        factors["cal_background_scale"] = clamp(
            0.62 + (heating / 0.09) * 0.65 + (700 / max(coherence_ms, 1.0)) * 0.2,
            0.55,
            2.1,
        )
        factors["cal_z_bias_scale"] = clamp(0.9 + (addressing / 0.03) * 0.55, 0.85, 2.0)
    else:
        loss = float(metrics.get("photon_loss_rate", 0.05))
        mismatch = float(metrics.get("mode_mismatch", 0.02))
        phase_deg = float(metrics.get("phase_drift_deg", 2.5))
        dark_count = float(metrics.get("detector_dark_count_rate", 0.007))
        efficiency = float(metrics.get("homodyne_efficiency", 0.93))
        non_gaussian_failure = float(metrics.get("non_gaussian_injection_failure", 0.035))
        factors["cal_one_qubit_scale"] = clamp(0.75 + (mismatch / 0.025) * 0.75, 0.65, 2.4)
        factors["cal_two_qubit_scale"] = clamp(
            0.8 + (non_gaussian_failure / 0.04) * 0.8 + (loss / 0.06) * 0.35,
            0.7,
            2.6,
        )
        factors["cal_measurement_scale"] = clamp(
            0.6 + (dark_count / 0.008) * 0.8 + ((1 - efficiency) / 0.08) * 0.7,
            0.65,
            2.7,
        )
        factors["cal_timing_scale"] = clamp(
            0.9 + (loss / 0.06) * 0.18 + ((1 - efficiency) / 0.08) * 0.12,
            0.85,
            1.32,
        )
        factors["cal_background_scale"] = clamp(0.85 + (loss / 0.06) * 0.8 + (phase_deg / 3.2) * 0.42, 0.75, 2.8)
        factors["cal_z_bias_scale"] = clamp(0.9 + (phase_deg / 3.0) * 0.7, 0.85, 2.5)

    adjusted = HardwareNoiseProfile(
        surface_gate_scale=profile.surface_gate_scale * factors["cal_two_qubit_scale"],
        surface_meas_scale=profile.surface_meas_scale * factors["cal_measurement_scale"],
        surface_background_scale=profile.surface_background_scale * factors["cal_background_scale"],
        surface_z_bias=profile.surface_z_bias * factors["cal_z_bias_scale"],
        gkp_sigma_scale=profile.gkp_sigma_scale * factors["cal_background_scale"] * factors["cal_timing_scale"],
        gkp_jump_scale=profile.gkp_jump_scale * factors["cal_two_qubit_scale"],
        gkp_meas_scale=profile.gkp_meas_scale * factors["cal_measurement_scale"],
    )
    return adjusted, factors


def parse_compile_artifact(raw: str) -> tuple[dict[str, Any] | None, CompileArtifactContext | None]:
    payload_text = raw.strip()
    if not payload_text:
        return None, None
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid --circuit-compile-artifact JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Error: --circuit-compile-artifact must be a JSON object.")

    def as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    context = CompileArtifactContext(
        total_duration_ns=max(0.0, as_float(payload.get("total_duration_ns", 0.0))),
        transpiled_depth=max(0, as_int(payload.get("transpiled_depth", 0))),
        swap_insertions=max(0, as_int(payload.get("swap_insertions", 0))),
        schedule_conflicts=max(0, as_int(payload.get("schedule_conflicts", 0))),
    )
    return payload, context


def apply_compile_artifact_adjustments(
    profile: HardwareNoiseProfile,
    compile_ctx: CompileArtifactContext | None,
    detector_model: str | None,
    hardware_target: str,
) -> tuple[HardwareNoiseProfile, dict[str, float]]:
    if compile_ctx is None:
        compile_factors = {
            "timing_scale": 1.0,
            "routing_scale": 1.0,
            "schedule_scale": 1.0,
            "detector_scale": 1.0,
        }
        return profile, compile_factors

    timing_scale = clamp(1.0 + (compile_ctx.total_duration_ns / 25000.0) * 0.01, 0.85, 1.6)
    routing_scale = clamp(1.0 + compile_ctx.swap_insertions * 0.04, 0.9, 2.0)
    schedule_scale = clamp(1.0 + compile_ctx.schedule_conflicts * 0.03, 0.9, 2.0)
    detector_scale = 1.0
    if hardware_target == "photonic":
        if detector_model == "pnr_approx":
            detector_scale = 0.92
        elif detector_model == "threshold":
            detector_scale = 1.06

    compile_factors = {
        "timing_scale": timing_scale,
        "routing_scale": routing_scale,
        "schedule_scale": schedule_scale,
        "detector_scale": detector_scale,
    }

    adjusted = HardwareNoiseProfile(
        surface_gate_scale=profile.surface_gate_scale * timing_scale * routing_scale,
        surface_meas_scale=profile.surface_meas_scale * detector_scale,
        surface_background_scale=profile.surface_background_scale * timing_scale * schedule_scale,
        surface_z_bias=profile.surface_z_bias * (1.0 + (timing_scale - 1.0) * 0.45),
        gkp_sigma_scale=profile.gkp_sigma_scale * timing_scale * schedule_scale,
        gkp_jump_scale=profile.gkp_jump_scale * routing_scale,
        gkp_meas_scale=profile.gkp_meas_scale * detector_scale,
    )
    return adjusted, compile_factors


def data_indices_for_gate(
    op: GateOp,
    logical_to_data: list[int],
    adjacency: list[list[int]],
) -> list[tuple[int, float]]:
    idx_target = logical_to_data[op.target]
    weighted: list[tuple[int, float]] = [(idx_target, 1.0)]

    if op.control is not None:
        idx_control = logical_to_data[op.control]
        if idx_control != idx_target:
            weighted.append((idx_control, 0.95))

    for idx, scale in list(weighted):
        local_neighbors = adjacency[idx][:2]
        for nbr in local_neighbors:
            weighted.append((nbr, scale * 0.55))

    # Keep highest scale per index.
    merged: dict[int, float] = {}
    for idx, scale in weighted:
        current = merged.get(idx, 0.0)
        if scale > current:
            merged[idx] = scale
    return list(merged.items())


def gate_pauli_coupling(op: GateOp) -> tuple[float, float]:
    gate = op.gate
    if gate == "x":
        return 1.0, 0.05
    if gate == "z":
        return 0.05, 1.0
    if gate == "y":
        return 0.95, 0.95
    if gate == "h":
        return 0.8, 0.8
    if gate in {"s", "t"}:
        return 0.25, 0.95
    if gate == "rx":
        return 1.0, 0.2
    if gate == "ry":
        return 0.9, 0.9
    if gate == "rz":
        return 0.2, 1.0
    if gate == "measure":
        return 0.2, 1.1
    if gate == "cx":
        return 1.1, 0.8
    if gate == "cz":
        return 0.8, 1.1
    if gate == "ms":
        return 1.0, 1.0
    if gate == "disp":
        return 1.0, 0.45
    if gate == "sq":
        return 0.55, 1.05
    if gate == "phase":
        return 0.2, 1.0
    if gate == "bs":
        return 0.9, 0.9
    if gate == "kerr":
        return 1.15, 1.25
    if gate == "cubic":
        return 0.75, 1.35
    return 0.8, 0.8


def gate_strength(op: GateOp, error_rate: float, sigma: float) -> float:
    base = error_rate * (0.85 + 0.5 * sigma)
    if op.gate in {"cx", "cz", "ms", "bs"}:
        base *= 1.35
    elif op.gate == "measure":
        base *= 1.15
    elif op.gate in {"rx", "ry", "rz", "disp", "sq", "phase"}:
        base *= 1.05
    elif op.gate in {"kerr", "cubic"}:
        base *= 1.26
    if op.gate in {"rx", "ry", "rz", "ms", "disp", "sq", "phase", "bs", "kerr", "cubic"}:
        if op.parameter is not None:
            base *= 1.0 + min(1.0, abs(op.parameter) / math.pi) * 0.25
    return clamp(base, 0.0, 0.8)


def parity_from_support(bits: list[int], support: list[int]) -> int:
    value = 0
    for q in support:
        value ^= bits[q] & 1
    return value


def digitize_periodic(value: float, *, period: float, width: float, bias: float) -> int:
    shifted = value + bias
    wrapped = (shifted + 0.5 * period) % period - 0.5 * period
    return 1 if abs(wrapped) > width else 0


def emit_round_events(
    *,
    sx: list[int],
    sz: list[int],
    prev_sx: list[int],
    prev_sz: list[int],
    round_index: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    t_base = (round_index + 1) * 1000
    for i, bit in enumerate(sx):
        if (bit ^ prev_sx[i]) & 1:
            events.append({"index": i, "time_ns": t_base, "type": "X"})
    for i, bit in enumerate(sz):
        if (bit ^ prev_sz[i]) & 1:
            events.append({"index": i, "time_ns": t_base + 100, "type": "Z"})
    return events


def apply_measurement_noise(bits: list[int], p_meas: float, rng: random.Random) -> None:
    for i in range(len(bits)):
        if rng.random() < p_meas:
            bits[i] ^= 1


def simulate_surface_shot(
    *,
    ops: list[GateOp],
    geom: SurfaceGeometry,
    logical_to_data: list[int],
    adjacency: list[list[int]],
    rounds: int,
    error_rate: float,
    sigma: float,
    profile: HardwareNoiseProfile,
    rng: random.Random,
) -> list[dict[str, Any]]:
    x_bits = [0] * geom.n_data
    z_bits = [0] * geom.n_data
    prev_sx = [0] * geom.n_x
    prev_sz = [0] * geom.n_z
    events: list[dict[str, Any]] = []
    p_background = clamp((error_rate * 0.3 + sigma * 0.04) * profile.surface_background_scale, 0.0, 0.5)
    p_meas = clamp((error_rate * 1.05) * profile.surface_meas_scale, 0.0, 0.6)

    for round_index in range(rounds):
        for i in range(geom.n_data):
            if rng.random() < p_background:
                x_bits[i] ^= 1
            if rng.random() < (p_background * 0.85):
                z_bits[i] ^= 1

        for op in ops:
            p_gate = gate_strength(op, error_rate=error_rate, sigma=sigma)
            cx, cz = gate_pauli_coupling(op)
            p_gate *= profile.surface_gate_scale
            for data_idx, spread in data_indices_for_gate(op, logical_to_data, adjacency):
                p_x = clamp(p_gate * cx * spread, 0.0, 0.95)
                p_z = clamp(p_gate * cz * spread * profile.surface_z_bias, 0.0, 0.95)
                if rng.random() < p_x:
                    x_bits[data_idx] ^= 1
                if rng.random() < p_z:
                    z_bits[data_idx] ^= 1

            if op.control is not None:
                c_idx = logical_to_data[op.control]
                t_idx = logical_to_data[op.target]
                p_corr = clamp(p_gate * 0.3, 0.0, 0.5)
                if rng.random() < p_corr:
                    x_bits[c_idx] ^= 1
                    x_bits[t_idx] ^= 1
                if rng.random() < p_corr:
                    z_bits[c_idx] ^= 1
                    z_bits[t_idx] ^= 1

        sx = [parity_from_support(z_bits, support) for support in geom.x_supports]
        sz = [parity_from_support(x_bits, support) for support in geom.z_supports]
        apply_measurement_noise(sx, p_meas, rng)
        apply_measurement_noise(sz, p_meas, rng)
        events.extend(emit_round_events(sx=sx, sz=sz, prev_sx=prev_sx, prev_sz=prev_sz, round_index=round_index))
        prev_sx = sx
        prev_sz = sz

    return events


def simulate_gkp_shot(
    *,
    ops: list[GateOp],
    geom: SurfaceGeometry,
    logical_to_data: list[int],
    adjacency: list[list[int]],
    rounds: int,
    error_rate: float,
    sigma: float,
    framework: str,
    hardware_target: str,
    profile: HardwareNoiseProfile,
    rng: random.Random,
) -> list[dict[str, Any]]:
    style = framework_style(framework, hardware_target)
    q_shift = [0.0] * geom.n_data
    p_shift = [0.0] * geom.n_data
    prev_sx = [0] * geom.n_x
    prev_sz = [0] * geom.n_z
    events: list[dict[str, Any]] = []
    sqrt_pi = math.sqrt(math.pi)
    sigma_bg = max(1e-5, sigma * (0.45 + 1.1 * error_rate) * profile.gkp_sigma_scale)
    p_meas = clamp(error_rate * 0.95 * profile.gkp_meas_scale, 0.0, 0.6)
    p_jump = clamp(error_rate * 0.28 * profile.gkp_jump_scale, 0.0, 0.5)
    jump_scale = 0.5 * sqrt_pi

    for round_index in range(rounds):
        for i in range(geom.n_data):
            q_shift[i] += rng.gauss(0.0, sigma_bg)
            p_shift[i] += rng.gauss(0.0, sigma_bg)
            if rng.random() < (p_jump * 0.5):
                q_shift[i] += jump_scale if rng.random() < 0.5 else -jump_scale
            if rng.random() < (p_jump * 0.5):
                p_shift[i] += jump_scale if rng.random() < 0.5 else -jump_scale

        for op in ops:
            p_gate = gate_strength(op, error_rate=error_rate, sigma=sigma)
            cx, cz = gate_pauli_coupling(op)
            kick_base = sqrt_pi * (0.08 + 0.65 * p_gate)
            for data_idx, spread in data_indices_for_gate(op, logical_to_data, adjacency):
                q_sigma = kick_base * spread * (0.25 + 0.85 * cz)
                p_sigma = kick_base * spread * (0.25 + 0.85 * cx)
                q_shift[data_idx] += rng.gauss(0.0, q_sigma)
                p_shift[data_idx] += rng.gauss(0.0, p_sigma)
                if rng.random() < (p_jump * spread * 0.55):
                    q_shift[data_idx] += jump_scale if rng.random() < 0.5 else -jump_scale
                if rng.random() < (p_jump * spread * 0.55):
                    p_shift[data_idx] += jump_scale if rng.random() < 0.5 else -jump_scale

            if op.control is not None:
                c_idx = logical_to_data[op.control]
                t_idx = logical_to_data[op.target]
                corr = rng.gauss(0.0, kick_base * 0.32)
                q_shift[c_idx] += corr
                q_shift[t_idx] -= corr * 0.82
                corr = rng.gauss(0.0, kick_base * 0.32)
                p_shift[c_idx] += corr
                p_shift[t_idx] -= corr * 0.82

        threshold = 0.24 * sqrt_pi * style.threshold_scale
        z_bits = [
            digitize_periodic(q_shift[i], period=sqrt_pi, width=threshold, bias=style.q_bias)
            for i in range(geom.n_data)
        ]
        x_bits = [
            digitize_periodic(p_shift[i], period=sqrt_pi, width=threshold, bias=style.p_bias)
            for i in range(geom.n_data)
        ]

        sx = [parity_from_support(z_bits, support) for support in geom.x_supports]
        sz = [parity_from_support(x_bits, support) for support in geom.z_supports]
        apply_measurement_noise(sx, p_meas, rng)
        apply_measurement_noise(sz, p_meas, rng)
        events.extend(emit_round_events(sx=sx, sz=sz, prev_sx=prev_sx, prev_sz=prev_sz, round_index=round_index))
        prev_sx = sx
        prev_sz = sz

    return events


def write_requests(
    *,
    out_dir: Path,
    framework: str,
    shots: int,
    rounds: int,
    geom: SurfaceGeometry,
    code_family: str,
    sigma: float,
    error_rate: float,
    seed: int,
    circuit_qubits: int,
    circuit_name: str,
    circuit_qasm: str,
    circuit_hardware_target: str,
    circuit_detector_model: str | None,
    circuit_noise_config: CircuitNoiseConfig | None,
    circuit_compile_artifact: dict[str, Any] | None,
    circuit_compile_context: CompileArtifactContext | None,
    circuit_calibration_snapshot: VendorCalibrationSnapshot | None,
    ops: list[GateOp],
) -> dict[str, Any]:
    request_path = out_dir / f"decoder_requests_{framework}.ndjson"
    code_id = f"{code_family}_d{geom.distance}"
    rng = random.Random(seed)
    adjacency = build_data_adjacency(geom)
    logical_to_data = map_logical_to_data(circuit_qubits, geom.n_data)
    nonempty = 0
    total_events = 0
    noise_profile, noise_factors = effective_noise_profile(circuit_hardware_target, circuit_noise_config)
    noise_profile, calibration_factors = apply_vendor_calibration_adjustments(
        noise_profile,
        hardware_target=circuit_hardware_target,
        snapshot=circuit_calibration_snapshot,
    )
    noise_profile, compile_factors = apply_compile_artifact_adjustments(
        noise_profile,
        compile_ctx=circuit_compile_context,
        detector_model=circuit_detector_model,
        hardware_target=circuit_hardware_target,
    )
    calibration_snapshot_dict = calibration_snapshot_to_dict(circuit_calibration_snapshot)
    calibration_binding_mode = "calibrated" if circuit_calibration_snapshot is not None else "modeled"
    noise_config_dict = noise_config_to_dict(circuit_noise_config)
    noise_profile_dict = noise_profile_to_dict(noise_profile)
    base_gate_rate = clamp(error_rate * 0.55 * noise_profile.surface_gate_scale, 0.0, 1.0)
    meas_rate = clamp(error_rate * noise_profile.surface_meas_scale, 0.0, 1.0)
    idle_rate = clamp(error_rate * 0.4 * noise_profile.surface_background_scale, 0.0, 1.0)
    backend = ""

    with request_path.open("w", encoding="utf-8") as handle:
        for shot_index in range(shots):
            if code_family == "surface":
                events = simulate_surface_shot(
                    ops=ops,
                    geom=geom,
                    logical_to_data=logical_to_data,
                    adjacency=adjacency,
                    rounds=rounds,
                    error_rate=error_rate,
                    sigma=sigma,
                    profile=noise_profile,
                    rng=rng,
                )
                backend = f"{framework}_custom_surface_{circuit_hardware_target}_two_layer"
            else:
                events = simulate_gkp_shot(
                    ops=ops,
                    geom=geom,
                    logical_to_data=logical_to_data,
                    adjacency=adjacency,
                    rounds=rounds,
                    error_rate=error_rate,
                    sigma=sigma,
                    framework=framework,
                    hardware_target=circuit_hardware_target,
                    profile=noise_profile,
                    rng=rng,
                )
                backend = f"{framework}_custom_gkp_{circuit_hardware_target}_two_layer"
            if circuit_calibration_snapshot is not None:
                backend = f"{backend}_calibrated"

            if events:
                nonempty += 1
            total_events += len(events)
            payload = {
                "code_id": code_id,
                "round_index": shot_index,
                "n_qubits": geom.n_data,
                "events": events,
                "noise": {
                    "sigma": sigma,
                    "gate_error_rate": base_gate_rate,
                    "meas_error_rate": meas_rate,
                    "idle_error_rate": idle_rate,
                    "loss_prob_by_qubit": [],
                },
                "metadata": {
                    "dataset": framework,
                    "source_backend": backend,
                    "seed": str(seed),
                    "distance": str(geom.distance),
                    "rounds": str(rounds),
                    "n_data_qubits": str(geom.n_data),
                    "x_checks": str(geom.n_x),
                    "z_checks": str(geom.n_z),
                    "generator": "frontend_circuit_two_layer_noise",
                    "noise_model": "two_layer_gkp_surface_v1",
                    "noise_binding_mode": calibration_binding_mode,
                    "circuit_name": circuit_name,
                    "circuit_qubits": str(circuit_qubits),
                    "circuit_gate_count": str(len(ops)),
                    "circuit_hardware_target": circuit_hardware_target,
                    "circuit_qasm": circuit_qasm,
                    "circuit_detector_model": circuit_detector_model or "",
                    "circuit_calibration_snapshot": circuit_calibration_snapshot.id
                    if circuit_calibration_snapshot is not None
                    else "",
                    "circuit_calibration_vendor": circuit_calibration_snapshot.vendor
                    if circuit_calibration_snapshot is not None
                    else "",
                    "circuit_noise_config": json.dumps(noise_config_dict, separators=(",", ":")),
                    "circuit_compile_artifact": json.dumps(
                        circuit_compile_artifact or {},
                        separators=(",", ":"),
                    ),
                    "circuit_calibration_snapshot_payload": json.dumps(
                        calibration_snapshot_dict,
                        separators=(",", ":"),
                    ),
                    "effective_noise_profile": json.dumps(noise_profile_dict, separators=(",", ":")),
                    "effective_noise_factors": json.dumps(
                        {key: round(value, 6) for key, value in noise_factors.items()},
                        separators=(",", ":"),
                    ),
                    "calibration_noise_factors": json.dumps(
                        {key: round(value, 6) for key, value in calibration_factors.items()},
                        separators=(",", ":"),
                    ),
                    "compile_noise_factors": json.dumps(
                        {key: round(value, 6) for key, value in compile_factors.items()},
                        separators=(",", ":"),
                    ),
                },
            }
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    return {
        "dataset": framework,
        "request_file": request_path.name,
        "request_lines": shots,
        "avg_request_events": float(total_events) / float(max(shots, 1)),
        "nonempty_request_event_rate": float(nonempty) / float(max(shots, 1)),
        "source_backend": backend,
        "noise_profile": noise_profile_dict,
        "noise_factors": {key: round(value, 6) for key, value in noise_factors.items()},
        "calibration_factors": {key: round(value, 6) for key, value in calibration_factors.items()},
        "compile_factors": {key: round(value, 6) for key, value in compile_factors.items()},
        "noise_config": noise_config_dict,
        "calibration_snapshot": calibration_snapshot_dict,
        "noise_binding_mode": calibration_binding_mode,
        "detector_model": circuit_detector_model or "",
    }


def main() -> int:
    args = parse_args()
    if args.shots <= 0:
        raise SystemExit("Error: --shots must be > 0.")
    if args.rounds <= 0:
        raise SystemExit("Error: --rounds must be > 0.")
    if args.circuit_qubits <= 0:
        raise SystemExit("Error: --circuit-qubits must be > 0.")
    if args.error_rate < 0.0 or args.error_rate > 1.0:
        raise SystemExit("Error: --error-rate must be within [0,1].")
    if args.sigma < 0.0:
        raise SystemExit("Error: --sigma must be >= 0.")
    if args.framework in {"qiskit", "cirq"} and args.circuit_hardware_target != "superconducting":
        raise SystemExit(
            f"Error: framework '{args.framework}' supports only circuit_hardware_target=superconducting."
        )
    detector_model_raw = args.circuit_detector_model.strip().lower() if args.circuit_detector_model else ""
    detector_model = detector_model_raw if detector_model_raw else None
    if detector_model is not None:
        if detector_model not in {"threshold", "pnr_approx"}:
            raise SystemExit("Error: --circuit-detector-model must be threshold or pnr_approx.")
        if args.circuit_hardware_target != "photonic":
            raise SystemExit("Error: --circuit-detector-model is only valid with --circuit-hardware-target=photonic.")

    compile_artifact_raw, compile_artifact_context = parse_compile_artifact(args.circuit_compile_artifact)
    calibration_snapshot = resolve_calibration_snapshot(
        raw_snapshot_id=args.circuit_calibration_snapshot,
        raw_catalog_path=args.circuit_calibration_catalog,
        compile_artifact=compile_artifact_raw,
        framework=args.framework,
        hardware_target=args.circuit_hardware_target,
    )

    allowed_gates = allowed_gates_for_framework_target(args.framework, args.circuit_hardware_target)
    ops = parse_gate_plan(
        args.circuit_gate_plan,
        args.circuit_qubits,
        allowed_gates=allowed_gates,
        hardware_target=args.circuit_hardware_target,
    )
    circuit_noise_config = parse_circuit_noise_config(args.circuit_noise_config, args.circuit_hardware_target)
    geom = build_surface_geometry(args.distance)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    row = write_requests(
        out_dir=out_dir,
        framework=args.framework,
        shots=args.shots,
        rounds=args.rounds,
        geom=geom,
        code_family=args.code_family,
        sigma=args.sigma,
        error_rate=args.error_rate,
        seed=args.seed,
        circuit_qubits=args.circuit_qubits,
        circuit_name=args.circuit_name.strip() or "custom_design",
        circuit_qasm=args.circuit_qasm,
        circuit_hardware_target=args.circuit_hardware_target,
        circuit_detector_model=detector_model,
        circuit_noise_config=circuit_noise_config,
        circuit_compile_artifact=compile_artifact_raw,
        circuit_compile_context=compile_artifact_context,
        circuit_calibration_snapshot=calibration_snapshot,
        ops=ops,
    )

    manifest_path = out_dir / "table_request_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        manifest_fields = [
            "dataset",
            "request_file",
            "request_lines",
            "avg_request_events",
            "nonempty_request_event_rate",
            "source_backend",
        ]
        writer = csv.DictWriter(
            handle,
            fieldnames=manifest_fields,
        )
        writer.writeheader()
        manifest_row = {field: row.get(field) for field in manifest_fields}
        manifest_row["avg_request_events"] = f"{float(row['avg_request_events']):.6f}"
        manifest_row["nonempty_request_event_rate"] = f"{float(row['nonempty_request_event_rate']):.6f}"
        writer.writerow(
            manifest_row
        )

    summary = {
        "shots": args.shots,
        "rounds": args.rounds,
        "distance": geom.distance,
        "code_family": args.code_family,
        "n_qubits": geom.n_data,
        "n_x_checks": geom.n_x,
        "n_z_checks": geom.n_z,
        "circuit_qubits": args.circuit_qubits,
        "error_rate": args.error_rate,
        "sigma": args.sigma,
        "seed": args.seed,
        "framework": args.framework,
        "circuit_hardware_target": args.circuit_hardware_target,
        "circuit_detector_model": row.get("detector_model", ""),
        "circuit_noise_config": row.get("noise_config", {}),
        "circuit_compile_artifact": compile_artifact_raw or {},
        "circuit_calibration_snapshot": row.get("calibration_snapshot", {}),
        "noise_binding_mode": row.get("noise_binding_mode", "modeled"),
        "effective_noise_profile": row.get("noise_profile", {}),
        "effective_noise_factors": row.get("noise_factors", {}),
        "calibration_noise_factors": row.get("calibration_factors", {}),
        "compile_noise_factors": row.get("compile_factors", {}),
        "generator": "frontend_circuit_two_layer_noise",
        "noise_model": "two_layer_gkp_surface_v1",
        "datasets": [row],
    }
    with (out_dir / "summary_generation.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    print(f"[custom-circuit] wrote {row['request_file']} to {out_dir}")
    print(f"[custom-circuit] source_backend={row['source_backend']} noise_model=two_layer_gkp_surface_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
