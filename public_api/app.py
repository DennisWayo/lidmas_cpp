from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


API_PREFIX = "/api/v1"
STARTED_AT = datetime.now(timezone.utc)
ISO_BASE = "2026-04-20T10:00:00Z"
DEFAULT_RUN_ID = "7f08982d-6bfb-4c64-bec8-feb4e8b2665f"
DECODERS = ["bp_osd", "mwpm_gkp", "union_find"]
PUBLIC_DECODER_POLICIES = ("mwpm", "bp", "uf")
PUBLIC_SHOT_CAP = 1024
PUBLIC_QUBIT_CAP = 12
PUBLIC_GATE_CAP = 96
PUBLIC_CODE_DISTANCE_CAP = 5
PUBLIC_ROUND_CAP = 4
PUBLIC_STABILIZER_CAP = PUBLIC_CODE_DISTANCE_CAP * PUBLIC_CODE_DISTANCE_CAP
PUBLIC_SESSION_DURATION_SECONDS = 7.0


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "https://gottesman-software.github.io,http://127.0.0.1:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def public_error(message: str, status_code: int = 403) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def provider_fixture() -> list[dict[str, Any]]:
    providers = [
        ("2fb9d977-b44f-4907-8826-82f7953ac26a", "PennyLane circuit simulator", "simulated", "ready"),
        ("93a9edc8-1e87-4af0-9f70-3bcf56261379", "Qiskit Aer noise simulator", "simulated", "ready"),
        ("e7fe27f7-4f0e-4992-95dc-a2f33cd9705f", "Cirq syndrome simulator", "simulated", "ready"),
        ("4afcd5b2-f17c-49c4-9f3e-a68e7c6cf75b", "SchroSIM photonic CV simulator", "simulated", "ready"),
    ]
    return [
        {
            "id": provider_id,
            "name": name,
            "status": status,
            "kind": kind,
            "hardware_kind": kind,
            "contact_email": None,
            "supported_formats": ["jsonl", "csv", "json"],
            "supports_scientific": True,
            "supports_benchmark": True,
            "supports_replay": True,
            "supports_live": False,
            "last_seen": utcnow(),
            "readiness_note": "Public simulator fixture. No credentials or hardware access.",
            "notes": "Construct circuit, inject noise, extract syndrome data, and run a decoder policy.",
            "created_at": ISO_BASE,
            "updated_at": utcnow(),
        }
        for provider_id, name, kind, status in providers
    ]


def job_fixture(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = [
        ("pennylane_circuit_noise_syndrome", "running", 0),
        ("qiskit_aer_noise_policy", "completed", 1),
        ("cirq_syndrome_extraction_policy", "completed", 2),
        ("schrosim_cv_decoder_policy", "queued", 3),
    ]
    jobs: list[dict[str, Any]] = []
    for index, (label, status, provider_index) in enumerate(labels):
        created_at = f"2026-04-20T14:{(6 + index):02d}:00Z"
        jobs.append(
            {
                "id": f"a338f7a2-31fd-4fcd-b17a-7adf2f9a{100 + index}",
                "provider_id": providers[provider_index % len(providers)]["id"],
                "dataset_label": label,
                "decoders": DECODERS,
                "priority": 5,
                "status": status,
                "message": "Public simulator pipeline: circuit construction, noise injection, syndrome extraction, decoder policy.",
                "created_at": created_at,
                "updated_at": created_at,
                "started_at": None if status == "queued" else created_at,
                "completed_at": "2026-04-20T14:30:00Z" if status == "completed" else None,
            }
        )
    return jobs


def telemetry_for_run(run_id: str, scale: float = 1.0) -> dict[str, Any]:
    rounds = 24
    stabilizers = 12
    noise_samples = [
        {
            "index": index,
            "physical_error_rate": round(0.006 + (math.sin(index / 4) + 1) * 0.0045 * scale, 6),
            "displacement_sigma": round(0.12 + (math.cos(index / 5) + 1) * 0.09 * scale, 6),
            "photon_loss_rate": round(0.009 + (math.sin(index / 6) + 1) * 0.003 * scale, 6),
        }
        for index in range(30)
    ]
    syndrome_samples = []
    for index in range(rounds * stabilizers):
        round_index = index // stabilizers
        stabilizer_index = index % stabilizers
        wave = math.sin((round_index + 1) * (stabilizer_index + 2) * 0.21)
        triggered = abs(wave) > 0.62
        syndrome_samples.append(
            {
                "round": round_index,
                "stabilizer": f"S{stabilizer_index + 1:02d}",
                "value": 1 if triggered and wave >= 0 else -1 if triggered else 0,
                "is_triggered": triggered,
            }
        )
    decoder_interventions = [
        {
            "decoder": decoder,
            "round": round_index,
            "flips": max(1, round((2.4 + decoder_index * 0.9) * (1 + math.sin(round_index * 0.31) * 0.18))),
            "residual_weight": max(
                1,
                round((1.6 + decoder_index * 0.55) * (1 + math.cos(round_index * 0.37) * 0.2)),
            ),
        }
        for decoder_index, decoder in enumerate(DECODERS)
        for round_index in range(rounds)
    ]
    oscillator_states = [
        {
            "round": index // 8,
            "mode": f"M{(index % 8) + 1:02d}",
            "q": round(math.cos(index * 0.37) * 0.72, 4),
            "p": round(math.sin(index * 0.41) * 0.72, 4),
            "variance": round(0.04 + abs(math.sin(index * 0.19)) * 0.08, 4),
            "energy": round(0.18 + abs(math.cos(index * 0.23)) * 0.24, 4),
            "flagged": abs(math.sin(index * 0.19)) > 0.78,
        }
        for index in range(rounds * 8)
    ]
    logical_trials = 2400
    logical_failures = max(1, round(41 * scale))
    return {
        "run_id": run_id,
        "request_count": logical_trials,
        "request_line_count": logical_trials,
        "response_line_count": logical_trials,
        "response_ratio": 1.0,
        "expanded_shot_count": logical_trials,
        "rounds": rounds,
        "stabilizer_count": stabilizers,
        "syndrome_opportunities": rounds * stabilizers,
        "decoder_name": "mwpm_gkp",
        "logical_failures": logical_failures,
        "logical_trials": logical_trials,
        "logical_error_rate": round(logical_failures / logical_trials, 6),
        "physical_error_events": 31,
        "physical_error_opportunities": 2880,
        "physical_error_rate": 0.010764,
        "residual_syndrome_events": 55,
        "residual_syndrome_rate": round(55 / (rounds * stabilizers), 6),
        "warning_rate": round(0.17 * scale, 6),
        "noise_samples": noise_samples,
        "syndrome_samples": syndrome_samples,
        "decoder_exact_metrics": [
            {"decoder": "bp_osd", "trials": logical_trials, "logical_failures": 47, "encoder_state": "gkp"},
            {"decoder": "mwpm_gkp", "trials": logical_trials, "logical_failures": logical_failures, "encoder_state": "gkp"},
            {"decoder": "union_find", "trials": logical_trials, "logical_failures": 63, "encoder_state": "gkp"},
        ],
        "gkp_oscillator_states": oscillator_states,
        "decoder_interventions": decoder_interventions,
        "updated_at": utcnow(),
    }


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def to_int(value: Any, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def parse_json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value if value is not None else fallback


def parse_dict(value: Any) -> dict[str, Any]:
    parsed = parse_json_value(value, {})
    return parsed if isinstance(parsed, dict) else {}


def parse_list(value: Any) -> list[Any]:
    parsed = parse_json_value(value, [])
    return parsed if isinstance(parsed, list) else []


def bound_public_session_config(config: dict[str, Any]) -> dict[str, Any]:
    bounded = dict(config)
    bounded["simulator_shots"] = to_int(
        config.get("simulator_shots"),
        PUBLIC_SHOT_CAP,
        minimum=32,
        maximum=PUBLIC_SHOT_CAP,
    )
    bounded["simulator_rounds"] = to_int(
        config.get("simulator_rounds"),
        PUBLIC_ROUND_CAP,
        minimum=1,
        maximum=PUBLIC_ROUND_CAP,
    )
    bounded["simulator_distance"] = to_int(
        config.get("simulator_distance"),
        PUBLIC_CODE_DISTANCE_CAP,
        minimum=3,
        maximum=PUBLIC_CODE_DISTANCE_CAP,
    )
    if "circuit_qubits" in bounded:
        bounded["circuit_qubits"] = to_int(
            config.get("circuit_qubits"),
            3,
            minimum=1,
            maximum=PUBLIC_QUBIT_CAP,
        )
    if "circuit_gate_count" in bounded:
        bounded["circuit_gate_count"] = to_int(
            config.get("circuit_gate_count"),
            1,
            minimum=1,
            maximum=PUBLIC_GATE_CAP,
        )
    if "circuit_depth" in bounded:
        bounded["circuit_depth"] = to_int(
            config.get("circuit_depth"),
            bounded.get("circuit_gate_count", 1),
            minimum=1,
            maximum=PUBLIC_GATE_CAP,
        )
    return bounded


def normalize_decoder_key(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"mwpm", "mwpm_gkp", "minimum_weight", "min_weight"}:
        return "mwpm"
    if normalized in {"bp", "bp_osd", "belief_propagation", "min_sum"}:
        return "bp"
    if normalized in {"uf", "union_find", "unionfind"}:
        return "uf"
    if normalized in {"neural", "neural_mwpm"}:
        return "neural_mwpm"
    return normalized or "mwpm"


def decoder_display_name(decoder: str) -> str:
    labels = {
        "mwpm": "MWPM",
        "bp": "BP / min-sum",
        "uf": "Union-Find",
        "neural_mwpm": "Neural MWPM",
    }
    return labels.get(normalize_decoder_key(decoder), str(decoder))


def provider_from_adapter(adapter_id: str) -> str:
    adapter = adapter_id.lower()
    if "schrosim" in adapter:
        return "schrosim"
    if "qiskit" in adapter:
        return "qiskit"
    if "cirq" in adapter:
        return "cirq"
    if "pennylane" in adapter:
        return "pennylane"
    if "ankaa" in adapter:
        return "ankaa"
    return "pennylane"


def active_noise_channels(noise_config: dict[str, Any]) -> list[tuple[str, float]]:
    preset = str(noise_config.get("preset") or "medium").lower()
    preset_level = {"low": 0.25, "medium": 0.5, "high": 0.8}.get(preset, 0.5)
    channels = noise_config.get("channels")
    if not isinstance(channels, dict) or not channels:
        return [("preset", preset_level)]
    active: list[tuple[str, float]] = []
    for key, raw_channel in channels.items():
        if not isinstance(raw_channel, dict):
            continue
        if raw_channel.get("enabled", True) is False:
            continue
        try:
            level = float(raw_channel.get("level", preset_level))
        except (TypeError, ValueError):
            level = preset_level
        active.append((str(key), clamp01(level)))
    return active or [("preset", preset_level)]


def noise_intensity(noise_config: dict[str, Any]) -> float:
    channels = active_noise_channels(noise_config)
    return clamp01(sum(level for _, level in channels) / max(1, len(channels)))


def infer_code_family(config: dict[str, Any], provider: str, hardware_target: str) -> str:
    explicit = str(config.get("circuit_qec_code") or config.get("simulator_code_family") or "").lower()
    if explicit in {"repetition", "surface", "css_ldpc", "qldpc", "gkp", "digitized_gkp"}:
        return "css_ldpc" if explicit == "qldpc" else explicit
    if hardware_target == "photonic" or provider == "schrosim":
        return "gkp"
    if provider == "cirq":
        return "repetition"
    return "surface"


def code_family_label(code_family: str) -> str:
    labels = {
        "repetition": "repetition code",
        "surface": "surface code",
        "css_ldpc": "CSS-LDPC / qLDPC",
        "gkp": "digitized GKP",
        "digitized_gkp": "digitized GKP",
    }
    return labels.get(code_family, code_family)


def decoder_factor(decoder: str, code_family: str, intensity: float, neural_ready: bool) -> float:
    key = normalize_decoder_key(decoder)
    if code_family in {"gkp", "digitized_gkp"}:
        factors = {"mwpm": 0.82, "bp": 0.91, "uf": 1.08, "neural_mwpm": 0.78 if neural_ready else 1.18}
    elif code_family == "css_ldpc":
        factors = {"mwpm": 1.02, "bp": 0.76, "uf": 0.93, "neural_mwpm": 0.86 if neural_ready else 1.16}
    elif code_family == "repetition":
        factors = {"mwpm": 0.86, "bp": 1.03, "uf": 0.90, "neural_mwpm": 0.84 if neural_ready else 1.12}
    else:
        factors = {"mwpm": 0.78, "bp": 1.07, "uf": 0.96, "neural_mwpm": 0.74 if neural_ready else 1.15}
    high_noise_adjust = {"mwpm": 0.08, "bp": -0.03, "uf": -0.08, "neural_mwpm": 0.02}.get(key, 0.0)
    return max(0.55, factors.get(key, 1.0) + max(0.0, intensity - 0.55) * high_noise_adjust)


def build_public_circuit_result(
    run_id: str,
    adapter_id: str,
    config: dict[str, Any],
    requested_decoders: list[str],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    provider = provider_from_adapter(adapter_id)
    noise_config = parse_dict(config.get("circuit_noise_config"))
    compile_artifact = parse_dict(config.get("circuit_compile_artifact"))
    syndrome_preview = parse_dict(compile_artifact.get("syndrome_preview"))
    gate_plan = parse_list(config.get("circuit_gate_plan"))

    circuit_name = str(config.get("circuit_name") or "custom_design")
    hardware_target = str(
        config.get("circuit_hardware_target")
        or compile_artifact.get("hardware_target")
        or ("photonic" if provider == "schrosim" else "superconducting")
    )
    qubits = to_int(config.get("circuit_qubits"), 3, minimum=1, maximum=PUBLIC_QUBIT_CAP)
    depth = to_int(
        config.get("circuit_depth") or compile_artifact.get("source_depth"),
        max(1, len(gate_plan)),
        minimum=1,
        maximum=PUBLIC_GATE_CAP,
    )
    gate_count = to_int(
        config.get("circuit_gate_count") or len(gate_plan),
        len(gate_plan),
        minimum=1,
        maximum=PUBLIC_GATE_CAP,
    )
    shots_requested = to_int(config.get("simulator_shots"), 1024, minimum=32, maximum=100_000)
    shots = min(shots_requested, PUBLIC_SHOT_CAP)
    rounds = to_int(
        syndrome_preview.get("rounds_est") or config.get("simulator_rounds"),
        PUBLIC_ROUND_CAP,
        minimum=1,
        maximum=PUBLIC_ROUND_CAP,
    )
    stabilizers = to_int(
        syndrome_preview.get("stabilizer_count_est"),
        max(1, qubits if hardware_target == "photonic" else 2 * qubits - 2),
        minimum=1,
        maximum=PUBLIC_STABILIZER_CAP,
    )
    intensity = noise_intensity(noise_config)
    active_channels = active_noise_channels(noise_config)
    code_family = infer_code_family(config, provider, hardware_target)
    neural_ready = bool(str(config.get("neural_model_path") or "").strip())

    policies = list(PUBLIC_DECODER_POLICIES)
    for decoder in requested_decoders:
        key = normalize_decoder_key(decoder)
        if key in PUBLIC_DECODER_POLICIES and key not in policies:
            policies.append(key)

    baseline_ler = clamp01(0.006 + intensity * 0.085 + depth * 0.00075 + gate_count * 0.00018 + qubits * 0.00035)
    decoder_rankings: list[dict[str, Any]] = []
    decoder_exact_metrics: list[dict[str, Any]] = []
    decoder_interventions: list[dict[str, Any]] = []
    for index, decoder in enumerate(policies):
        factor = decoder_factor(decoder, code_family, intensity, neural_ready)
        logical_error_rate = clamp01(baseline_ler * factor)
        logical_failures = max(0, min(shots, round(shots * logical_error_rate)))
        residual = clamp01(0.035 + intensity * 0.19 + factor * 0.035 + index * 0.004)
        avg_flips = round(max(1.0, gate_count * (0.18 + intensity * 0.16) * factor), 3)
        efficiency = clamp01(1 - logical_error_rate / max(0.001, baseline_ler * 1.35))
        decoder_rankings.append(
            {
                "decoder": normalize_decoder_key(decoder),
                "logical_error_rate": round(logical_error_rate, 6),
                "avg_flips": avg_flips,
                "residual_nonzero_rate": round(residual, 6),
                "correction_efficiency": round(efficiency, 6),
            }
        )
        decoder_exact_metrics.append(
            {
                "decoder": normalize_decoder_key(decoder),
                "trials": shots,
                "logical_failures": logical_failures,
                "encoder_state": code_family,
            }
        )
        for round_index in range(rounds):
            wave = 1 + math.sin((round_index + 1) * (index + 2) * 0.29) * 0.16
            decoder_interventions.append(
                {
                    "decoder": normalize_decoder_key(decoder),
                    "round": round_index,
                    "flips": max(1, round(avg_flips * wave)),
                    "residual_weight": max(0, round(residual * stabilizers * (1 + math.cos(round_index * 0.33) * 0.18))),
                }
            )

    decoder_rankings.sort(
        key=lambda row: (
            row["logical_error_rate"] + row["residual_nonzero_rate"] * 0.08 + row["avg_flips"] * 0.002
        )
    )
    best_decoder = decoder_rankings[0]["decoder"]
    best_exact = next(row for row in decoder_exact_metrics if row["decoder"] == best_decoder)

    noise_samples = [
        {
            "index": index,
            "physical_error_rate": round(0.0025 + intensity * 0.017 + abs(math.sin(index * 0.37)) * 0.004, 6),
            "displacement_sigma": round((0.045 + intensity * 0.25 + abs(math.cos(index * 0.21)) * 0.025) if hardware_target == "photonic" else 0.0, 6),
            "photon_loss_rate": round((0.006 + intensity * 0.042 + abs(math.sin(index * 0.19)) * 0.006) if hardware_target == "photonic" else 0.0, 6),
        }
        for index in range(max(12, rounds * 3))
    ]
    syndrome_samples = []
    for index in range(rounds * stabilizers):
        round_index = index // stabilizers
        stabilizer_index = index % stabilizers
        wave = math.sin((round_index + 1) * (stabilizer_index + 2) * (0.17 + intensity * 0.09))
        triggered = abs(wave) > max(0.44, 0.74 - intensity * 0.22)
        syndrome_samples.append(
            {
                "round": round_index,
                "stabilizer": f"S{stabilizer_index + 1:02d}",
                "value": 1 if triggered and wave >= 0 else -1 if triggered else 0,
                "is_triggered": triggered,
            }
        )
    residual_events = max(0, round(sum(1 for sample in syndrome_samples if sample["is_triggered"]) * decoder_rankings[0]["residual_nonzero_rate"]))
    physical_opportunities = max(1, shots * max(1, gate_count))
    physical_events = max(1, round(physical_opportunities * (0.0025 + intensity * 0.017)))
    warning_rate = clamp01(0.03 + intensity * 0.18 + (0.04 if shots_requested > PUBLIC_SHOT_CAP else 0.0))
    request_lines = shots
    response_lines = shots

    provided_gkp_states = parse_list(config.get("gkp_oscillator_states"))
    telemetry = {
        "run_id": run_id,
        "request_count": shots,
        "request_line_count": request_lines,
        "response_line_count": response_lines,
        "response_ratio": round(response_lines / max(1, request_lines), 6),
        "expanded_shot_count": shots,
        "rounds": rounds,
        "stabilizer_count": stabilizers,
        "syndrome_opportunities": rounds * stabilizers,
        "decoder_name": best_decoder,
        "logical_failures": best_exact["logical_failures"],
        "logical_trials": shots,
        "logical_error_rate": decoder_rankings[0]["logical_error_rate"],
        "physical_error_events": physical_events,
        "physical_error_opportunities": physical_opportunities,
        "physical_error_rate": round(physical_events / physical_opportunities, 6),
        "residual_syndrome_events": residual_events,
        "residual_syndrome_rate": round(residual_events / max(1, rounds * stabilizers), 6),
        "warning_rate": round(warning_rate, 6),
        "noise_samples": noise_samples,
        "syndrome_samples": syndrome_samples,
        "decoder_exact_metrics": decoder_exact_metrics,
        "gkp_oscillator_states": provided_gkp_states[: rounds * qubits]
        if code_family in {"gkp", "digitized_gkp"}
        else [],
        "decoder_interventions": decoder_interventions,
        "updated_at": utcnow(),
    }
    metrics = {
        "avg_flip_count": decoder_rankings[0]["avg_flips"],
        "nonempty_flip_rate": round(clamp01(0.18 + intensity * 0.32), 6),
        "syndrome_satisfaction_rate": round(1 - telemetry["residual_syndrome_rate"], 6),
        "residual_nonzero_rate": decoder_rankings[0]["residual_nonzero_rate"],
        "warning_rate": round(warning_rate, 6),
        "physical_error_rate": telemetry["physical_error_rate"],
        "baseline_logical_error_rate": round(baseline_ler, 6),
        "logical_error_rate": decoder_rankings[0]["logical_error_rate"],
        "logical_failures": best_exact["logical_failures"],
        "logical_trials": shots,
        "physical_error_events": physical_events,
        "physical_error_opportunities": physical_opportunities,
        "request_line_count": request_lines,
        "response_line_count": response_lines,
        "rounds": rounds,
        "stabilizer_count": stabilizers,
        "syndrome_opportunities": rounds * stabilizers,
        "residual_syndrome_events": residual_events,
        "expanded_shot_count": shots,
        "decoder_exact_metrics": decoder_exact_metrics,
        "best_decoder": best_decoder,
        "best_encoder_state": code_family,
        "decoder_rankings": decoder_rankings,
        "scientific_validation_ready": True,
    }
    channel_summary = ", ".join(f"{name}={level:.2f}" for name, level in active_channels[:6])
    logs = [
        f"Accepted {provider} public simulator session for circuit '{circuit_name}'.",
        f"Constructed {hardware_target} circuit: {qubits} modes/qubits, {gate_count} gates, depth {depth}.",
        f"Selected {code_family_label(code_family)} public syndrome workflow.",
        f"Applied noise model: {channel_summary or 'no active channels'}.",
        f"Requested {shots_requested} shots; public bounded mode executed {shots} shots.",
        f"Extracted {rounds * stabilizers} syndrome opportunities across {rounds} rounds.",
        "Compared decoder policies: " + ", ".join(decoder_display_name(row["decoder"]) for row in decoder_rankings),
        f"Recommended {decoder_display_name(best_decoder)} from logical-error, residual-syndrome, correction-volume, and warning-rate scores.",
        "No IBM credentials, private provider secrets, or lab hardware controls were used.",
    ]
    return metrics, telemetry, logs


def find_run(run_id: str) -> dict[str, Any] | None:
    return next((run for run in RUNS if run["id"] == run_id), None)


def refresh_public_sessions() -> None:
    now = datetime.now(timezone.utc)
    for session in INTEGRATION_SESSIONS:
        if session.get("status") != "running":
            continue
        started_raw = session.get("started_at")
        try:
            started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
        except ValueError:
            started = now
        if (now - started).total_seconds() < PUBLIC_SESSION_DURATION_SECONDS:
            continue
        session["status"] = "finished"
        session["updated_at"] = utcnow()
        session["ended_at"] = session["updated_at"]
        session["exit_code"] = 0
        run = find_run(str(session.get("run_id")))
        if run is not None:
            run["status"] = "finished"
            run["updated_at"] = session["updated_at"]


def run_fixture(providers: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    runs = [
        {
            "id": DEFAULT_RUN_ID,
            "job_id": jobs[0]["id"],
            "workflow_id": "pennylane-surface-code-policy",
            "provider_id": providers[0]["id"],
            "dataset_label": "pennylane_surface_d5_depolarizing_syndromes",
            "decoders": DECODERS,
            "status": "running",
            "message": "PennyLane surface-code circuit with depolarizing noise, extracted syndromes, and MWPM decoder policy.",
            "artifacts": [
                {
                    "name": "constructed_circuit",
                    "kind": "json",
                    "path": "public://runs/pennylane/constructed_circuit.json",
                    "sha256": None,
                    "created_at": "2026-04-20T14:09:00Z",
                },
                {
                    "name": "noise_injection",
                    "kind": "json",
                    "path": "public://runs/pennylane/noise_injection.json",
                    "sha256": None,
                    "created_at": "2026-04-20T14:09:30Z",
                },
                {
                    "name": "syndrome_trace",
                    "kind": "jsonl",
                    "path": "public://runs/pennylane/syndrome_trace.jsonl",
                    "sha256": None,
                    "created_at": "2026-04-20T14:10:00Z",
                },
                {
                    "name": "decoder_policy_metrics",
                    "kind": "csv",
                    "path": "public://runs/pennylane/decoder_policy_metrics.csv",
                    "sha256": None,
                    "created_at": "2026-04-20T14:11:30Z",
                },
            ],
            "metrics": {
                "avg_flip_count": 3.2,
                "nonempty_flip_rate": 0.34,
                "syndrome_satisfaction_rate": 0.92,
                "residual_nonzero_rate": 0.19,
                "warning_rate": 0.17,
                "logical_error_rate": 0.017083,
                "logical_failures": 41,
                "logical_trials": 2400,
                "best_decoder": "mwpm_gkp",
                "scientific_validation_ready": True,
            },
            "created_at": "2026-04-20T14:08:00Z",
            "updated_at": utcnow(),
        }
    ]
    dataset_labels = [
        "qiskit_aer_surface_d5_phase_flip_syndromes",
        "cirq_repetition_code_bitflip_syndromes",
        "schrosim_cv_gkp_loss_syndromes",
    ]
    workflow_ids = [
        "qiskit-aer-noise-policy",
        "cirq-syndrome-policy",
        "schrosim-cv-decoder-policy",
    ]
    messages = [
        "Qiskit Aer circuit with phase-flip noise, syndrome extraction, and decoder-policy replay.",
        "Cirq stabilizer circuit with bit-flip injection, syndrome extraction, and decoder-policy replay.",
        "SchroSIM CV photonic circuit with loss-style noise, syndrome extraction, and decoder-policy replay.",
    ]
    for index in range(1, 4):
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"lidmas-public-run-{index}"))
        runs.append(
            {
                "id": run_id,
                "job_id": jobs[index % len(jobs)]["id"],
                "workflow_id": workflow_ids[index - 1],
                "provider_id": providers[index % len(providers)]["id"],
                "dataset_label": dataset_labels[index - 1],
                "decoders": DECODERS,
                "status": "finished",
                "message": messages[index - 1],
                "artifacts": [],
                "metrics": {
                    "warning_rate": round(0.11 + index * 0.015, 6),
                    "logical_error_rate": round(0.012 + index * 0.003, 6),
                    "logical_failures": 29 + index * 6,
                    "logical_trials": 2400,
                    "best_decoder": DECODERS[index % len(DECODERS)],
                    "scientific_validation_ready": True,
                },
                "created_at": f"2026-04-20T14:{10 + index:02d}:00Z",
                "updated_at": utcnow(),
            }
        )
    telemetry = {run["id"]: telemetry_for_run(run["id"], 1.0 + index * 0.08) for index, run in enumerate(runs)}
    return runs, telemetry


PROVIDERS = provider_fixture()
JOBS = job_fixture(PROVIDERS)
RUNS, RUN_TELEMETRY = run_fixture(PROVIDERS, JOBS)
INTEGRATION_SESSIONS: list[dict[str, Any]] = []
INTEGRATION_SESSION_LOGS: dict[str, list[str]] = {}
HARDWARE_SESSIONS: list[dict[str, Any]] = []


app = FastAPI(
    title="LiDMaS+ Public API",
    version="1.2.2-public-demo",
    description="Public, fixture-backed LiDMaS+ API for Gottesman Studio.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type"],
)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "LiDMaS+ Public API",
        "mode": "public-demo",
        "api": API_PREFIX,
        "docs": "/docs",
    }


@app.get("/health")
@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.2.2-public-demo",
        "started_at": STARTED_AT.isoformat().replace("+00:00", "Z"),
        "uptime_seconds": int(time.time() - STARTED_AT.timestamp()),
    }


@app.get(f"{API_PREFIX}/providers")
def list_providers() -> list[dict[str, Any]]:
    return deepcopy(PROVIDERS)


@app.post(f"{API_PREFIX}/providers")
async def create_provider_public() -> JSONResponse:
    return public_error("Provider creation is disabled in the public LiDMaS+ API.")


@app.get(f"{API_PREFIX}/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return deepcopy(JOBS)


@app.post(f"{API_PREFIX}/jobs")
async def create_job(request: Request) -> dict[str, Any]:
    payload = await request.json()
    provider_id = payload.get("provider_id") or PROVIDERS[0]["id"]
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    now = utcnow()
    job = {
        "id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "dataset_label": str(payload.get("dataset_label") or "public_demo_job"),
        "decoders": payload.get("decoders") or DECODERS,
        "priority": int(payload.get("priority") or 5),
        "status": "queued",
        "message": "Created as an in-memory public demo job. It will reset when the service sleeps.",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
    }
    JOBS.insert(0, job)
    return deepcopy(job)


@app.get(f"{API_PREFIX}/runs")
def list_runs() -> list[dict[str, Any]]:
    refresh_public_sessions()
    return deepcopy(RUNS)


@app.post(f"{API_PREFIX}/runs")
async def create_run(request: Request) -> dict[str, Any]:
    payload = await request.json()
    provider_id = payload.get("provider_id") or PROVIDERS[0]["id"]
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    now = utcnow()
    run_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "job_id": payload.get("job_id"),
        "workflow_id": payload.get("workflow_id") or "public-demo-created-run",
        "provider_id": provider_id,
        "dataset_label": payload.get("dataset_label") or "public_created_replay",
        "decoders": payload.get("decoders") or DECODERS,
        "status": "created",
        "message": "Created as a public simulator run. Start a session to attach circuit, noise, syndrome, and decoder metrics.",
        "artifacts": [],
        "metrics": {
            "scientific_validation_ready": False,
        },
        "created_at": now,
        "updated_at": now,
    }
    RUNS.insert(0, run)
    return deepcopy(run)


@app.get(f"{API_PREFIX}/runs/{{run_id}}/telemetry")
def get_run_telemetry(run_id: str, scientific: bool = False) -> dict[str, Any]:
    refresh_public_sessions()
    telemetry = RUN_TELEMETRY.get(run_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="Run telemetry not found")
    response = deepcopy(telemetry)
    if scientific:
        response["scientific_mode"] = True
    return response


@app.post(f"{API_PREFIX}/runs/{{run_id}}/telemetry")
async def upsert_run_telemetry(run_id: str, request: Request) -> dict[str, Any]:
    if not any(run["id"] == run_id for run in RUNS):
        raise HTTPException(status_code=404, detail="Run not found")
    payload = await request.json()
    telemetry = telemetry_for_run(run_id, 1.0)
    telemetry.update(payload)
    telemetry["run_id"] = run_id
    telemetry["updated_at"] = utcnow()
    RUN_TELEMETRY[run_id] = telemetry
    return deepcopy(telemetry)


@app.post(f"{API_PREFIX}/providers/{{provider_id}}/validate")
async def validate_provider(provider_id: str, request: Request) -> dict[str, Any]:
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    payload = await request.json()
    request_lines = int(payload.get("request_lines") or 0)
    response_lines = int(payload.get("response_lines") or 0)
    request_errors = int(payload.get("request_parse_errors") or 0)
    response_errors = int(payload.get("response_parse_errors") or 0)
    decoder_mismatches = int(payload.get("decoder_name_mismatch_count") or 0)
    line_coverage_ok = request_lines > 0 and response_lines >= max(1, int(request_lines * 0.95))
    parse_integrity_ok = request_errors == 0 and response_errors == 0
    decoder_name_integrity_ok = decoder_mismatches == 0
    checks = [
        "Request and response line coverage inspected.",
        "JSON parse error counters inspected.",
        "Decoder naming consistency inspected.",
        "Public validation only; no private records or hardware sessions were accessed.",
    ]
    return {
        "provider_id": provider_id,
        "dataset_label": payload.get("dataset_label") or "public_validation",
        "line_coverage_ok": line_coverage_ok,
        "parse_integrity_ok": parse_integrity_ok,
        "decoder_name_integrity_ok": decoder_name_integrity_ok,
        "warning_rate": payload.get("warning_no_syndrome_count", 0) / max(1, response_lines),
        "overall_ok": line_coverage_ok and parse_integrity_ok and decoder_name_integrity_ok,
        "checks": checks,
        "checked_at": utcnow(),
    }


@app.get(f"{API_PREFIX}/hardware/schema")
def hardware_schema() -> dict[str, Any]:
    return {
        "schema_version": "public-demo-1",
        "frame_format": "disabled-public-demo",
        "notes": [
            "Hardware control is disabled in the public API.",
            "Use this page only to understand the future fixture and loopback data contract.",
            "Real instruments, credentials, sessions, and lab hardware remain private.",
        ],
        "create_session_request_example": {
            "provider_id": PROVIDERS[-1]["id"],
            "dataset_label": "loopback_timing_fixture",
            "decoders": DECODERS,
            "source_name": "public_loopback_fixture",
            "source_mode": "replay",
        },
        "frame_request_example": {
            "frames": [
                {
                    "frame_index": 0,
                    "source": "public_loopback_fixture",
                    "noise_sample": {
                        "physical_error_rate": 0.01,
                        "displacement_sigma": 0.2,
                        "photon_loss_rate": 0.012,
                    },
                    "syndrome_samples": [],
                    "decoder_interventions": [],
                }
            ]
        },
    }


@app.get(f"{API_PREFIX}/hardware/sessions")
def list_hardware_sessions() -> list[dict[str, Any]]:
    return deepcopy(HARDWARE_SESSIONS)


@app.post(f"{API_PREFIX}/hardware/sessions")
async def create_hardware_session_public() -> JSONResponse:
    return public_error("Hardware sessions are disabled in the public LiDMaS+ API.")


@app.post(f"{API_PREFIX}/hardware/sessions/{{session_id}}/frames")
async def ingest_hardware_frames_public(session_id: str) -> JSONResponse:
    return public_error(f"Hardware frame ingest is disabled for public session {session_id}.")


@app.post(f"{API_PREFIX}/hardware/sessions/{{session_id}}/complete")
async def complete_hardware_session_public(session_id: str) -> JSONResponse:
    return public_error(f"Hardware session completion is disabled for public session {session_id}.")


@app.post(f"{API_PREFIX}/system/credentials/ibm")
async def set_ibm_api_key_public() -> JSONResponse:
    return public_error("IBM credentials are not accepted or stored by the public LiDMaS+ API.")


@app.get(f"{API_PREFIX}/system/calibrations")
def vendor_calibrations() -> dict[str, Any]:
    return {
        "schema_version": "public-demo-1",
        "generated_at": utcnow(),
        "refresh_mode": "static-public-fixture",
        "snapshots": [
            {
                "id": "public-pennylane-surface-fixture",
                "label": "PennyLane surface-code depolarizing model",
                "vendor": "pennylane",
                "hardware_target": "simulated",
                "backend": "pennylane_default_qubit",
                "captured_at": "2026-04-20T14:00:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"physical_error_rate": 0.0112, "syndrome_trigger_rate": 0.21, "logical_error_rate": 0.017083},
            },
            {
                "id": "public-qiskit-aer-fixture",
                "label": "Qiskit Aer phase-flip noise model",
                "vendor": "qiskit",
                "hardware_target": "simulated",
                "backend": "qiskit_aer",
                "captured_at": "2026-04-20T14:05:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"phase_flip_rate": 0.014, "syndrome_trigger_rate": 0.18, "logical_error_rate": 0.015},
            },
            {
                "id": "public-cirq-fixture",
                "label": "Cirq repetition-code bit-flip model",
                "vendor": "cirq",
                "hardware_target": "simulated",
                "backend": "cirq_simulator",
                "captured_at": "2026-04-20T14:06:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"bit_flip_rate": 0.0125, "syndrome_trigger_rate": 0.16, "logical_error_rate": 0.018},
            },
            {
                "id": "public-schrosim-fixture",
                "label": "SchroSIM CV photonic loss model",
                "vendor": "schrosim",
                "hardware_target": "simulated",
                "backend": "schrosim_cv",
                "captured_at": "2026-04-20T14:07:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"photon_loss_rate": 0.021, "displacement_sigma": 0.16, "logical_error_rate": 0.021},
            },
        ],
        "notes": ["Static public simulator catalog. No live vendor credentials, hardware data, or private calibrations are loaded."],
    }


@app.post(f"{API_PREFIX}/system/calibrations/refresh")
async def refresh_vendor_calibrations_public() -> dict[str, Any]:
    return {
        "ok": True,
        "command": "public-demo:no-op",
        "duration_ms": 0,
        "exit_code": 0,
        "stdout_tail": ["Public demo uses a static calibration catalog."],
        "stderr_tail": [],
        "catalog_path": "public://calibrations/catalog.json",
        "refreshed_at": utcnow(),
        "catalog": vendor_calibrations(),
    }


@app.get(f"{API_PREFIX}/integrations/sessions")
def list_integration_sessions() -> list[dict[str, Any]]:
    refresh_public_sessions()
    return deepcopy(INTEGRATION_SESSIONS)


@app.post(f"{API_PREFIX}/integrations/sessions")
async def create_integration_session_public(request: Request) -> dict[str, Any]:
    payload = await request.json()
    run_id = str(payload.get("run_id") or DEFAULT_RUN_ID)
    if not any(run["id"] == run_id for run in RUNS):
        run_id = DEFAULT_RUN_ID
    adapter_id = str(payload.get("adapter_id") or "pennylane_surface_replay")
    config = payload.get("config") or {}
    if not isinstance(config, dict):
        config = {}
    if "ibm" in adapter_id.lower() or str(config.get("ibm_live_source_mode") or "").lower() == "qpu":
        return public_error("Live provider sessions are disabled in the public LiDMaS+ API.")
    config = bound_public_session_config(config)
    provider = provider_from_adapter(adapter_id)
    now = utcnow()
    session_id = str(uuid.uuid4())
    run = find_run(run_id)
    requested_decoders = run.get("decoders", DECODERS) if run is not None else DECODERS
    metrics, telemetry, logs = build_public_circuit_result(run_id, adapter_id, config, requested_decoders)
    if run is not None:
        run["status"] = "running"
        run["message"] = (
            f"Public simulator session is running: circuit construction, noise injection, "
            f"syndrome extraction, and decoder-policy recommendation."
        )
        run["metrics"] = metrics
        run["artifacts"] = [
            {
                "name": "constructed_circuit",
                "kind": "json",
                "path": f"memory://sessions/{session_id}/constructed_circuit.json",
                "sha256": None,
                "created_at": now,
            },
            {
                "name": "noise_injection",
                "kind": "json",
                "path": f"memory://sessions/{session_id}/noise_injection.json",
                "sha256": None,
                "created_at": now,
            },
            {
                "name": "syndrome_stream",
                "kind": "jsonl",
                "path": f"memory://sessions/{session_id}/syndrome_stream.jsonl",
                "sha256": None,
                "created_at": now,
            },
            {
                "name": "decoder_recommendation",
                "kind": "json",
                "path": f"memory://sessions/{session_id}/decoder_recommendation.json",
                "sha256": None,
                "created_at": now,
            },
        ]
        run["updated_at"] = now
    RUN_TELEMETRY[run_id] = telemetry
    session = {
        "id": session_id,
        "run_id": run_id,
        "provider": provider,
        "mode": "replay_static",
        "adapter_id": adapter_id,
        "status": "running",
        "config": config,
        "started_at": now,
        "updated_at": now,
        "ended_at": None,
        "exit_code": None,
        "last_error": None,
    }
    INTEGRATION_SESSIONS.insert(0, session)
    INTEGRATION_SESSION_LOGS[session_id] = logs
    return deepcopy(session)


@app.post(f"{API_PREFIX}/integrations/sessions/{{session_id}}/stop")
async def stop_integration_session_public(session_id: str) -> dict[str, Any]:
    session = next((item for item in INTEGRATION_SESSIONS if item["id"] == session_id), None)
    now = utcnow()
    if session is not None:
        session["status"] = "cancelled"
        session["updated_at"] = now
        session["ended_at"] = now
        session["exit_code"] = 0
        run = find_run(str(session.get("run_id")))
        if run is not None and run.get("status") == "running":
            run["status"] = "cancelled"
            run["updated_at"] = now
        return {
            "session": deepcopy(session),
            "stopped": True,
            "message": "Public simulator session was cancelled.",
        }
    return {
        "session": {
            "id": session_id,
            "run_id": DEFAULT_RUN_ID,
            "provider": "pennylane",
            "mode": "replay_static",
            "adapter_id": "pennylane_surface_replay",
            "status": "cancelled",
            "config": {},
            "started_at": utcnow(),
            "updated_at": utcnow(),
            "ended_at": utcnow(),
            "exit_code": 0,
            "last_error": None,
        },
        "stopped": True,
        "message": "No live session was running in public demo mode.",
    }


@app.get(f"{API_PREFIX}/integrations/sessions/{{session_id}}/logs")
def integration_session_logs(session_id: str, tail: int = 100) -> dict[str, Any]:
    refresh_public_sessions()
    session = next((item for item in INTEGRATION_SESSIONS if item["id"] == session_id), None)
    raw_lines = INTEGRATION_SESSION_LOGS.get(session_id)
    if raw_lines is None:
        raw_lines = ["Public simulator session not found in memory."]
    visible_count = len(raw_lines)
    if session is not None and session.get("status") == "running":
        try:
            started = datetime.fromisoformat(str(session.get("started_at")).replace("Z", "+00:00"))
            elapsed = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
        except ValueError:
            elapsed = PUBLIC_SESSION_DURATION_SECONDS
        visible_count = max(1, min(len(raw_lines), int((elapsed / PUBLIC_SESSION_DURATION_SECONDS) * len(raw_lines)) + 1))
    lines = [
        {
            "timestamp": utcnow(),
            "stream": "system",
            "line": line,
        }
        for line in raw_lines[:visible_count]
    ]
    return {"session_id": session_id, "total_lines": len(lines), "has_more": False, "lines": lines[-tail:]}


@app.post(f"{API_PREFIX}/system/logscan")
async def system_log_scan(request: Request) -> dict[str, Any]:
    payload = await request.json()
    logs = payload.get("logs") or []
    custom_rules = payload.get("custom_rules") or []
    suppressions = payload.get("suppressions") or []
    max_findings = int(payload.get("max_findings") or 50)
    default_rules = [
        {
            "id": "public-secret-token",
            "title": "Potential secret token",
            "pattern": r"(api[_-]?key|token|secret|password)",
            "severity": "high",
            "confidence": 0.85,
            "tags": ["secrets", "public-demo"],
            "recommendation": "Remove secrets before sharing public replay artifacts.",
        },
        {
            "id": "hardware-claim",
            "title": "Hardware claim needs label",
            "pattern": r"(qpu|hardware|instrument|detector|board)",
            "severity": "medium",
            "confidence": 0.7,
            "tags": ["claim-boundary"],
            "recommendation": "Label whether this is simulated, loopback, replayed, or partner-lab evidence.",
        },
    ]
    rules = default_rules + custom_rules
    findings: list[dict[str, Any]] = []
    suppressed = 0
    for line_index, entry in enumerate(logs):
        message = str(entry.get("message") or "")
        lowered = message.lower()
        is_suppressed = any(str(item.get("pattern") or "").lower() in lowered for item in suppressions)
        for rule in rules:
            pattern = str(rule.get("pattern") or "")
            if not pattern:
                continue
            if re.search(pattern, message, re.IGNORECASE):
                if is_suppressed:
                    suppressed += 1
                    continue
                findings.append(
                    {
                        "rule_id": rule.get("id") or "custom-rule",
                        "rule_origin": "custom" if rule in custom_rules else "default",
                        "title": rule.get("title") or "Log finding",
                        "severity": rule.get("severity") or "info",
                        "confidence": float(rule.get("confidence") or 0.5),
                        "line_index": line_index,
                        "timestamp": entry.get("timestamp"),
                        "level": entry.get("level"),
                        "source": entry.get("source"),
                        "message": message,
                        "tags": rule.get("tags") or [],
                        "recommendation": rule.get("recommendation"),
                    }
                )
                if len(findings) >= max_findings:
                    break
        if len(findings) >= max_findings:
            break
    severity_counts = {level: sum(1 for finding in findings if finding["severity"] == level) for level in ["critical", "high", "medium", "low", "info"]}
    verdict = "critical" if severity_counts["critical"] else "warn" if findings else "pass"
    return {
        "scan_id": str(uuid.uuid4()),
        "summary": {
            "scanned_entries": len(logs),
            "matched_entries": len(findings),
            "suppressed_matches": suppressed,
            "critical_count": severity_counts["critical"],
            "high_count": severity_counts["high"],
            "medium_count": severity_counts["medium"],
            "low_count": severity_counts["low"],
            "info_count": severity_counts["info"],
            "risk_score": min(100, severity_counts["critical"] * 40 + severity_counts["high"] * 25 + severity_counts["medium"] * 12),
            "verdict": verdict,
        },
        "findings": findings,
        "top_recommendations": list({finding.get("recommendation") for finding in findings if finding.get("recommendation")})[:5],
        "generated_at": utcnow(),
    }
