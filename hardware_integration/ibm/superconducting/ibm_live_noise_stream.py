#!/usr/bin/env python3
"""Poll IBM Quantum backend properties and emit LiDMaS+ normalized live frames."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def parse_decoders(raw: str) -> list[str]:
    decoders = [item.strip() for item in raw.split(",") if item.strip()]
    return decoders or ["mwpm"]


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _telemetry_url(
    telemetry_url: str | None,
    backend_base_url: str | None,
    run_id: str | None,
) -> str | None:
    if telemetry_url:
        return telemetry_url.rstrip("/")
    if backend_base_url and run_id:
        return f"{backend_base_url.rstrip('/')}/runs/{run_id}/telemetry"
    return None


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=body,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            text = response.read().decode("utf-8", errors="replace")
            return int(response.status), text
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), text


def _decoder_scales(decoder: str) -> tuple[float, float]:
    key = decoder.lower()
    if "bp" in key:
        return (0.84, 1.24)
    if "mwpm" in key:
        return (1.2, 0.74)
    if "uf" in key:
        return (0.96, 0.94)
    if "neural" in key:
        return (0.87, 0.78)
    return (1.0, 1.0)


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


def _extract_metrics(properties: Any) -> dict[str, float]:
    gate_errors: list[float] = []
    readout_errors: list[float] = []
    t1_values: list[float] = []
    t2_values: list[float] = []

    for gate in getattr(properties, "gates", []) or []:
        for parameter in getattr(gate, "parameters", []) or []:
            name = _nduv_name(parameter).lower()
            value = _nduv_value(parameter)
            if value is None:
                continue
            if "error" in name:
                gate_errors.append(value)

    for qubit in getattr(properties, "qubits", []) or []:
        for parameter in qubit:
            name = _nduv_name(parameter).lower()
            value = _nduv_value(parameter)
            if value is None:
                continue
            if name == "t1":
                t1_values.append(value)
            elif name == "t2":
                t2_values.append(value)
            elif "readout_error" in name or "prob_meas" in name:
                readout_errors.append(value)

    avg_gate_error = sum(gate_errors) / len(gate_errors) if gate_errors else 0.01
    avg_readout_error = sum(readout_errors) / len(readout_errors) if readout_errors else 0.02
    avg_t1 = sum(t1_values) / len(t1_values) if t1_values else 70.0
    avg_t2 = sum(t2_values) / len(t2_values) if t2_values else 55.0

    physical_error_rate = clamp((avg_gate_error * 0.7) + (avg_readout_error * 0.3), 0.0005, 0.25)
    t1_factor = 1.0 / max(1.0, avg_t1)
    t2_factor = 1.0 / max(1.0, avg_t2)
    photon_loss_rate = clamp((t1_factor * 0.3) + physical_error_rate * 0.12, 0.0001, 0.2)
    displacement_sigma = clamp(0.05 + math.sqrt(physical_error_rate) * 0.45 + t2_factor * 1.2, 0.03, 1.0)

    return {
        "physical_error_rate": physical_error_rate,
        "photon_loss_rate": photon_loss_rate,
        "displacement_sigma": displacement_sigma,
        "avg_gate_error": avg_gate_error,
        "avg_readout_error": avg_readout_error,
        "avg_t1": avg_t1,
        "avg_t2": avg_t2,
    }


def _import_qpu_probe_stack() -> tuple[Any, Any, Any]:
    try:
        from qiskit import QuantumCircuit  # type: ignore
        from qiskit.transpiler.preset_passmanagers import (  # type: ignore
            generate_preset_pass_manager,
        )
        from qiskit_ibm_runtime import SamplerV2 as Sampler  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "IBM QPU mode requires qiskit + qiskit-ibm-runtime with SamplerV2 support."
        ) from exc
    return QuantumCircuit, generate_preset_pass_manager, Sampler


def _normalize_bitstring(bitstring: str, width: int) -> str:
    filtered = "".join(ch for ch in bitstring if ch in {"0", "1"})
    if not filtered:
        return "0" * width
    if len(filtered) < width:
        return filtered.zfill(width)
    if len(filtered) > width:
        return filtered[-width:]
    return filtered


def _extract_counts_from_sampler_pub(pub_result: Any) -> dict[str, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        return {}

    def _counts_from_register(register: Any) -> dict[str, int]:
        if register is None or not hasattr(register, "get_counts"):
            return {}
        try:
            raw_counts = register.get_counts()
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(raw_counts, dict):
            return {}
        counts: dict[str, int] = {}
        for key, value in raw_counts.items():
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed <= 0:
                continue
            counts[str(key)] = parsed
        return counts

    for attr_name in ("cr", "meas", "c"):
        counts = _counts_from_register(getattr(data, attr_name, None))
        if counts:
            return counts

    for attr_name in dir(data):
        if attr_name.startswith("_"):
            continue
        counts = _counts_from_register(getattr(data, attr_name, None))
        if counts:
            return counts

    return {}


def _build_probe_circuit(
    quantum_circuit: Any,
    probe_qubits: int,
    round_index: int,
) -> tuple[Any, list[int]]:
    circuit = quantum_circuit(probe_qubits, probe_qubits, name=f"lidmas_qpu_probe_{round_index}")
    expected_bits: list[int] = []
    for qubit in range(probe_qubits):
        expected_one = ((round_index + qubit) % 5) in (0, 3)
        expected_bits.append(1 if expected_one else 0)
        if expected_one:
            circuit.x(qubit)
    circuit.measure(range(probe_qubits), range(probe_qubits))
    return circuit, expected_bits


def _run_qpu_probe(
    *,
    sampler: Any,
    pass_manager: Any,
    quantum_circuit: Any,
    round_index: int,
    stabilizer_count: int,
    shots: int,
    fallback_physical_error_rate: float,
) -> tuple[float, list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    probe_qubits = max(1, min(stabilizer_count, 8))
    circuit, expected_bits = _build_probe_circuit(quantum_circuit, probe_qubits, round_index)
    isa_circuit = pass_manager.run(circuit)
    job = sampler.run([isa_circuit], shots=shots)
    pub_result = job.result()[0]
    counts = _extract_counts_from_sampler_pub(pub_result)
    if not counts:
        raise RuntimeError("QPU sampler returned empty counts payload.")

    total_shots = sum(counts.values())
    if total_shots <= 0:
        raise RuntimeError("QPU sampler returned zero shots.")

    mismatch_counts = [0 for _ in range(probe_qubits)]
    shot_mismatch_any = 0
    for raw_bitstring, count in counts.items():
        bitstring = _normalize_bitstring(str(raw_bitstring), probe_qubits)
        mismatched = False
        for qubit in range(probe_qubits):
            observed = 1 if bitstring[-(qubit + 1)] == "1" else 0
            if observed != expected_bits[qubit]:
                mismatch_counts[qubit] += count
                mismatched = True
        if mismatched:
            shot_mismatch_any += count

    mismatch_rates = [count / total_shots for count in mismatch_counts]
    physical_error_rate = clamp(
        sum(mismatch_rates) / max(1, len(mismatch_rates)),
        0.0001,
        0.45,
    )
    if not math.isfinite(physical_error_rate):
        physical_error_rate = clamp(fallback_physical_error_rate, 0.0001, 0.45)

    trigger_threshold = max(0.015, min(0.35, physical_error_rate * 0.9 + 0.01))
    syndrome_chunk: list[dict[str, Any]] = []
    for stabilizer_index in range(stabilizer_count):
        probe_index = stabilizer_index % probe_qubits
        local_rate = mismatch_rates[probe_index]
        wave = abs(math.sin((round_index + 1) * (stabilizer_index + 2) * 0.131))
        trigger_score = local_rate * 0.85 + wave * 0.15 * max(physical_error_rate, 0.01)
        triggered = trigger_score >= trigger_threshold
        syndrome_chunk.append(
            {
                "round": round_index,
                "stabilizer": f"S{(stabilizer_index + 1):02d}",
                "value": 1 if triggered else 0,
                "is_triggered": bool(triggered),
            }
        )

    physical_error_events = sum(mismatch_counts)
    physical_error_opportunities = total_shots * probe_qubits
    logical_failures = shot_mismatch_any
    logical_trials = total_shots

    qpu_meta: dict[str, Any] = {
        "qpu_shots": total_shots,
        "qpu_probe_qubits": probe_qubits,
        "qpu_mismatch_rate_min": round(min(mismatch_rates), 7),
        "qpu_mismatch_rate_max": round(max(mismatch_rates), 7),
        "qpu_physical_error_events": physical_error_events,
        "qpu_physical_error_opportunities": physical_error_opportunities,
        "qpu_logical_failures": logical_failures,
        "qpu_logical_trials": logical_trials,
    }
    try:
        job_id = job.job_id() if callable(getattr(job, "job_id", None)) else None
    except Exception:  # noqa: BLE001
        job_id = None
    if job_id:
        qpu_meta["qpu_job_id"] = str(job_id)

    qpu_exact_counts = {
        "logical_failures": logical_failures,
        "logical_trials": logical_trials,
        "physical_error_events": physical_error_events,
        "physical_error_opportunities": physical_error_opportunities,
    }
    return physical_error_rate, syndrome_chunk, qpu_meta, qpu_exact_counts


def _build_telemetry_payload(
    run_id: str,
    warning_rate: float,
    noise_samples: list[dict[str, Any]],
    syndrome_samples: list[dict[str, Any]],
    decoder_interventions: list[dict[str, Any]],
    decoder_name: str | None,
    exact_logical_failures: int | None = None,
    exact_logical_trials: int | None = None,
    exact_physical_error_events: int | None = None,
    exact_physical_error_opportunities: int | None = None,
) -> dict[str, Any]:
    request_line_count = len(noise_samples)
    response_line_count = request_line_count
    response_ratio = (
        response_line_count / request_line_count if request_line_count > 0 else None
    )
    stabilizer_count = len({sample["stabilizer"] for sample in syndrome_samples})
    rounds = max((int(sample["round"]) for sample in syndrome_samples), default=-1) + 1
    # Use the actual emitted syndrome row count as denominator; this is stricter
    # than inferring from request_line_count * stabilizer_count.
    syndrome_opportunities = len(syndrome_samples)
    derived_physical_error_events = sum(
        1 for sample in syndrome_samples if sample.get("is_triggered") or int(sample.get("value", 0)) != 0
    )
    physical_error_events = (
        max(0, int(exact_physical_error_events))
        if exact_physical_error_events is not None
        else derived_physical_error_events
    )
    physical_error_opportunities = (
        max(0, int(exact_physical_error_opportunities))
        if exact_physical_error_opportunities is not None
        else syndrome_opportunities
    )
    if physical_error_opportunities > 0:
        physical_error_events = min(physical_error_events, physical_error_opportunities)
    physical_error_rate = (
        physical_error_events / physical_error_opportunities
        if physical_error_opportunities > 0
        else None
    )

    logical_failures = (
        max(0, int(exact_logical_failures))
        if exact_logical_failures is not None and exact_logical_trials is not None
        else None
    )
    logical_trials = (
        max(0, int(exact_logical_trials))
        if exact_logical_failures is not None and exact_logical_trials is not None
        else None
    )
    if logical_failures is not None and logical_trials is not None and logical_trials > 0:
        logical_failures = min(logical_failures, logical_trials)
    logical_error_rate = (
        logical_failures / logical_trials
        if logical_failures is not None and logical_trials is not None and logical_trials > 0
        else None
    )
    residual_syndrome_events = None
    normalized_decoder = (decoder_name or "").strip().lower()
    if normalized_decoder:
        # Map per-round residual weights to bounded event counts so the denominator
        # contract remains physically consistent:
        #   residual_syndrome_events <= rounds * stabilizer_count.
        # Multiple interventions in one round are capped by stabilizer_count.
        residual_by_round: dict[int, int] = {}
        round_cap = max(1, stabilizer_count)
        for entry in decoder_interventions:
            if str(entry.get("decoder", "")).strip().lower() != normalized_decoder:
                continue
            round_index = int(entry.get("round", 0))
            weight = max(0, int(entry.get("residual_weight", 0)))
            residual_by_round[round_index] = residual_by_round.get(round_index, 0) + weight
        residual_syndrome_events = sum(
            min(weight_sum, round_cap) for weight_sum in residual_by_round.values()
        )
    residual_syndrome_rate = (
        residual_syndrome_events / syndrome_opportunities
        if residual_syndrome_events is not None and syndrome_opportunities > 0
        else None
    )
    request_count = max(len(noise_samples), rounds) * max(1, stabilizer_count)
    return {
        "run_id": run_id,
        "request_count": request_count,
        "request_line_count": request_line_count,
        "response_line_count": response_line_count,
        "response_ratio": response_ratio,
        "expanded_shot_count": logical_trials,
        "rounds": rounds,
        "stabilizer_count": stabilizer_count,
        "syndrome_opportunities": syndrome_opportunities,
        "decoder_name": decoder_name,
        "logical_failures": logical_failures,
        "logical_trials": logical_trials,
        "logical_error_rate": logical_error_rate,
        "physical_error_events": physical_error_events,
        "physical_error_opportunities": physical_error_opportunities,
        "physical_error_rate": physical_error_rate,
        "residual_syndrome_events": residual_syndrome_events,
        "residual_syndrome_rate": residual_syndrome_rate,
        "warning_rate": warning_rate,
        "noise_samples": noise_samples,
        "syndrome_samples": syndrome_samples,
        "decoder_interventions": decoder_interventions,
    }


def _import_runtime():
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "IBM live adapter requires qiskit-ibm-runtime. "
            "Install with: python3 -m pip install --upgrade qiskit-ibm-runtime"
        ) from exc
    return QiskitRuntimeService


@dataclass(frozen=True)
class RuntimeConfig:
    backend_name: str
    token: str | None
    instance: str | None


def _connect_runtime(config: RuntimeConfig) -> Any:
    qiskit_runtime_service = _import_runtime()
    init_errors: list[str] = []
    normalized_instance = (
        config.instance.strip() if config.instance is not None else ""
    )
    runtime_instance = normalized_instance or None

    # Legacy hub/group/project identifiers such as "ibm-q/open/main" are not
    # valid for current ibm_cloud channel initialization.
    looks_like_legacy_hgp = bool(
        runtime_instance
        and runtime_instance.count("/") == 2
        and not runtime_instance.lower().startswith("crn:")
    )

    attempts: list[tuple[str | None, str | None]] = []
    attempts.append(("ibm_quantum_platform", runtime_instance))
    if not looks_like_legacy_hgp:
        attempts.append(("ibm_cloud", runtime_instance))
    attempts.append((None, runtime_instance))

    # If an instance hint is invalid for this account, retry without it.
    if runtime_instance:
        attempts.append(("ibm_quantum_platform", None))
        attempts.append(("ibm_cloud", None))
        attempts.append((None, None))

    seen: set[tuple[str | None, str | None]] = set()
    for channel, instance in attempts:
        key = (channel, instance)
        if key in seen:
            continue
        seen.add(key)

        kwargs: dict[str, Any] = {}
        if config.token:
            kwargs["token"] = config.token
        if instance:
            kwargs["instance"] = instance
        if channel is not None:
            kwargs["channel"] = channel

        try:
            service = qiskit_runtime_service(**kwargs)
            return service.backend(config.backend_name)
        except Exception as exc:  # noqa: BLE001
            init_errors.append(f"channel={channel!r}, instance={instance!r}: {exc}")

    raise RuntimeError(
        "failed to initialize IBM Runtime service for backend "
        f"{config.backend_name!r}: " + " | ".join(init_errors)
    )


def _write_frame(out_handle: Any, frame: dict[str, Any]) -> None:
    out_handle.write(json.dumps(frame, separators=(",", ":")) + "\n")
    out_handle.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll IBM Quantum backend properties and stream normalized LiDMaS+ frames."
    )
    parser.add_argument("--backend-name", required=True, help="IBM backend name, e.g. ibm_kingston.")
    parser.add_argument(
        "--token",
        default=None,
        help="IBM API token (optional when account is already saved in local runtime config).",
    )
    parser.add_argument("--token-env", default="IBM_QUANTUM_API_KEY", help="Environment variable for IBM token.")
    parser.add_argument(
        "--instance",
        default=None,
        help="Optional IBM instance/CRN. If omitted, runtime default account scope is used.",
    )
    parser.add_argument(
        "--source-mode",
        choices=["metadata", "qpu"],
        default="metadata",
        help="Telemetry source mode: metadata polling or real QPU sampler jobs.",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=256,
        help="Sampler shots per poll in QPU mode.",
    )
    parser.add_argument("--poll-interval", type=float, default=30.0, help="Poll interval in seconds.")
    parser.add_argument("--max-polls", type=int, default=20, help="Number of polls (0 = run forever).")
    parser.add_argument("--stabilizer-count", type=int, default=12, help="Synthesized stabilizer count per frame.")
    parser.add_argument("--decoders", default="mwpm", help="Comma-separated decoder names.")
    parser.add_argument("--out", default=None, help="Output NDJSON path (default: stdout).")
    parser.add_argument("--append-out", action="store_true", help="Append to --out instead of overwrite.")
    parser.add_argument("--run-id", default=None, help="Run UUID for telemetry push mode.")
    parser.add_argument(
        "--backend-base-url",
        default=None,
        help="Backend base URL, e.g. http://127.0.0.1:8080/api/v1",
    )
    parser.add_argument(
        "--telemetry-url",
        default=None,
        help="Direct telemetry endpoint URL (overrides --backend-base-url/--run-id).",
    )
    parser.add_argument("--push-every", type=int, default=2, help="Push telemetry every N polls.")
    parser.add_argument("--http-timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.poll_interval <= 0:
        raise ValueError("--poll-interval must be > 0.")
    if args.max_polls < 0:
        raise ValueError("--max-polls must be >= 0.")
    if args.stabilizer_count <= 0:
        raise ValueError("--stabilizer-count must be > 0.")
    if args.shots <= 0:
        raise ValueError("--shots must be > 0.")
    if args.push_every <= 0:
        raise ValueError("--push-every must be > 0.")

    token = args.token or os.environ.get(args.token_env)
    backend = _connect_runtime(
        RuntimeConfig(
            backend_name=args.backend_name,
            token=token,
            instance=args.instance,
        )
    )
    telemetry_url = _telemetry_url(args.telemetry_url, args.backend_base_url, args.run_id)
    decoders = parse_decoders(args.decoders)
    qpu_sampler = None
    qpu_pass_manager = None
    qpu_quantum_circuit = None
    if args.source_mode == "qpu":
        quantum_circuit, generate_preset_pass_manager, sampler_cls = _import_qpu_probe_stack()
        qpu_quantum_circuit = quantum_circuit
        qpu_pass_manager = generate_preset_pass_manager(target=backend.target, optimization_level=1)
        qpu_sampler = sampler_cls(mode=backend)

    out_handle = sys.stdout
    close_out = False
    if args.out:
        out_path = os.path.abspath(os.path.expanduser(args.out))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        mode = "a" if args.append_out else "w"
        out_handle = open(out_path, mode, encoding="utf-8")  # noqa: PTH123
        close_out = True

    all_noise_samples: list[dict[str, Any]] = []
    all_syndrome_samples: list[dict[str, Any]] = []
    all_decoder_interventions: list[dict[str, Any]] = []
    warning_levels: list[float] = []
    qpu_logical_failures_total = 0
    qpu_logical_trials_total = 0
    qpu_physical_error_events_total = 0
    qpu_physical_error_opportunities_total = 0
    qpu_exact_counts_seen = False
    poll_count = 0
    pushed = 0

    try:
        while args.max_polls == 0 or poll_count < args.max_polls:
            timestamp = utc_now_iso()
            properties = backend.properties(refresh=True)
            if properties is None:
                raise RuntimeError(f"backend {args.backend_name!r} returned no properties payload.")

            metrics = _extract_metrics(properties)
            qpu_meta: dict[str, Any] = {}
            qpu_exact_counts: dict[str, int] | None = None
            if args.source_mode == "qpu":
                if qpu_sampler is None or qpu_pass_manager is None or qpu_quantum_circuit is None:
                    raise RuntimeError("QPU mode initialization failed.")
                physical_error_rate, syndrome_chunk, qpu_meta, qpu_exact_counts = _run_qpu_probe(
                    sampler=qpu_sampler,
                    pass_manager=qpu_pass_manager,
                    quantum_circuit=qpu_quantum_circuit,
                    round_index=poll_count,
                    stabilizer_count=args.stabilizer_count,
                    shots=args.shots,
                    fallback_physical_error_rate=metrics["physical_error_rate"],
                )
                qpu_exact_counts_seen = True
                qpu_logical_failures_total += qpu_exact_counts["logical_failures"]
                qpu_logical_trials_total += qpu_exact_counts["logical_trials"]
                qpu_physical_error_events_total += qpu_exact_counts["physical_error_events"]
                qpu_physical_error_opportunities_total += qpu_exact_counts["physical_error_opportunities"]
                photon_loss_rate = clamp(
                    metrics["avg_readout_error"] * 0.6 + physical_error_rate * 0.35,
                    0.0001,
                    0.2,
                )
                displacement_sigma = clamp(
                    0.05 + math.sqrt(physical_error_rate) * 0.5 + (1.0 / max(1.0, metrics["avg_t2"])) * 0.8,
                    0.03,
                    1.0,
                )
                trigger_base = clamp(
                    sum(1 for sample in syndrome_chunk if sample["is_triggered"])
                    / max(1, len(syndrome_chunk)),
                    0.02,
                    0.95,
                )
            else:
                physical_error_rate = metrics["physical_error_rate"]
                photon_loss_rate = metrics["photon_loss_rate"]
                displacement_sigma = metrics["displacement_sigma"]
                trigger_base = clamp(physical_error_rate * 12.0 + metrics["avg_readout_error"] * 1.2, 0.02, 0.95)
                syndrome_chunk = []
                for stabilizer_index in range(args.stabilizer_count):
                    roll = abs(
                        math.sin(
                            (poll_count + 1) * (stabilizer_index + 3) * 0.137
                            + metrics["avg_gate_error"] * 13.0
                        )
                    )
                    triggered = roll < trigger_base
                    sign_roll = math.cos((stabilizer_index + 1) * 0.41 + poll_count * 0.19)
                    value = 1 if triggered and sign_roll >= 0 else (-1 if triggered else 0)
                    syndrome_chunk.append(
                        {
                            "round": poll_count,
                            "stabilizer": f"S{(stabilizer_index + 1):02d}",
                            "value": value,
                            "is_triggered": bool(triggered),
                        }
                    )

            warning_levels.append(physical_error_rate)
            noise_sample = {
                "index": poll_count,
                "physical_error_rate": round(physical_error_rate, 7),
                "displacement_sigma": round(displacement_sigma, 7),
                "photon_loss_rate": round(photon_loss_rate, 7),
            }

            intervention_chunk: list[dict[str, Any]] = []
            for decoder in decoders:
                flip_scale, residual_scale = _decoder_scales(decoder)
                flips = max(1, int(round((trigger_base * 7.0 + physical_error_rate * 65.0) * flip_scale)))
                residual_weight = max(
                    1,
                    int(round((1.0 - trigger_base) * 5.0 * residual_scale + physical_error_rate * 30.0)),
                )
                intervention_chunk.append(
                    {
                        "decoder": decoder,
                        "round": poll_count,
                        "flips": flips,
                        "residual_weight": residual_weight,
                    }
                )

            all_noise_samples.append(noise_sample)
            all_syndrome_samples.extend(syndrome_chunk)
            all_decoder_interventions.extend(intervention_chunk)

            frame = {
                "source": "ibm_live",
                "timestamp": timestamp,
                "frame_index": poll_count,
                "backend_name": args.backend_name,
                "noise_sample": noise_sample,
                "syndrome_samples": syndrome_chunk,
                "decoder_interventions": intervention_chunk,
                "meta": {
                    "source_mode": args.source_mode,
                    "instance": args.instance,
                    "avg_gate_error": round(metrics["avg_gate_error"], 7),
                    "avg_readout_error": round(metrics["avg_readout_error"], 7),
                    "avg_t1": round(metrics["avg_t1"], 5),
                    "avg_t2": round(metrics["avg_t2"], 5),
                    "decoders": decoders,
                    **qpu_meta,
                },
            }
            _write_frame(out_handle, frame)
            if args.source_mode == "qpu":
                qpu_job_id = qpu_meta.get("qpu_job_id")
                if qpu_job_id:
                    print(
                        f"[ibm_live][qpu] poll={poll_count} backend={args.backend_name} "
                        f"job_id={qpu_job_id} shots={qpu_meta.get('qpu_shots', args.shots)}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[ibm_live][qpu] poll={poll_count} backend={args.backend_name} "
                        "sampler result had no explicit job_id",
                        file=sys.stderr,
                    )

            should_push = telemetry_url and ((poll_count + 1) % args.push_every == 0)
            if should_push:
                warning_rate = sum(warning_levels) / max(1, len(warning_levels))
                payload = _build_telemetry_payload(
                    run_id=args.run_id or "00000000-0000-0000-0000-000000000000",
                    warning_rate=round(warning_rate, 7),
                    noise_samples=all_noise_samples,
                    syndrome_samples=all_syndrome_samples,
                    decoder_interventions=all_decoder_interventions,
                    decoder_name=decoders[0] if decoders else None,
                    exact_logical_failures=(
                        qpu_logical_failures_total if qpu_exact_counts_seen else None
                    ),
                    exact_logical_trials=(
                        qpu_logical_trials_total if qpu_exact_counts_seen else None
                    ),
                    exact_physical_error_events=(
                        qpu_physical_error_events_total if qpu_exact_counts_seen else None
                    ),
                    exact_physical_error_opportunities=(
                        qpu_physical_error_opportunities_total if qpu_exact_counts_seen else None
                    ),
                )
                status_code, response_text = _post_json(
                    telemetry_url,
                    payload,
                    timeout_s=args.http_timeout,
                )
                if status_code >= 300:
                    raise RuntimeError(
                        f"telemetry push failed ({status_code}) at poll {poll_count}: {response_text}"
                    )
                pushed += 1

            poll_count += 1
            if args.max_polls == 0 or poll_count < args.max_polls:
                time.sleep(args.poll_interval)

        print(
            (
                f"[ibm_live] completed polls={poll_count} backend={args.backend_name} "
                f"frames={poll_count} telemetry_pushes={pushed}"
            ),
            file=sys.stderr,
        )
        return 0
    finally:
        if close_out:
            out_handle.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
