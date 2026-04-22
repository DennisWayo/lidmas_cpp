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


def _build_telemetry_payload(
    run_id: str,
    warning_rate: float,
    noise_samples: list[dict[str, Any]],
    syndrome_samples: list[dict[str, Any]],
    decoder_interventions: list[dict[str, Any]],
) -> dict[str, Any]:
    stabilizer_count = len({sample["stabilizer"] for sample in syndrome_samples})
    rounds = max((int(sample["round"]) for sample in syndrome_samples), default=-1) + 1
    request_count = max(len(noise_samples), rounds) * max(1, stabilizer_count)
    return {
        "run_id": run_id,
        "request_count": request_count,
        "rounds": rounds,
        "stabilizer_count": stabilizer_count,
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

    channels = ["ibm_quantum", "ibm_cloud", None]
    for channel in channels:
        kwargs: dict[str, Any] = {}
        if config.token:
            kwargs["token"] = config.token
        if config.instance:
            kwargs["instance"] = config.instance
        if channel is not None:
            kwargs["channel"] = channel

        try:
            service = qiskit_runtime_service(**kwargs)
            return service.backend(config.backend_name)
        except Exception as exc:  # noqa: BLE001
            init_errors.append(f"channel={channel!r}: {exc}")

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
    parser.add_argument("--instance", default="ibm-q/open/main", help="IBM instance or CRN.")
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
    poll_count = 0
    pushed = 0

    try:
        while args.max_polls == 0 or poll_count < args.max_polls:
            timestamp = utc_now_iso()
            properties = backend.properties(refresh=True)
            if properties is None:
                raise RuntimeError(f"backend {args.backend_name!r} returned no properties payload.")

            metrics = _extract_metrics(properties)
            physical_error_rate = metrics["physical_error_rate"]
            photon_loss_rate = metrics["photon_loss_rate"]
            displacement_sigma = metrics["displacement_sigma"]

            warning_levels.append(physical_error_rate)
            noise_sample = {
                "index": poll_count,
                "physical_error_rate": round(physical_error_rate, 7),
                "displacement_sigma": round(displacement_sigma, 7),
                "photon_loss_rate": round(photon_loss_rate, 7),
            }

            trigger_base = clamp(physical_error_rate * 12.0 + metrics["avg_readout_error"] * 1.2, 0.02, 0.95)
            syndrome_chunk: list[dict[str, Any]] = []
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
                    "instance": args.instance,
                    "avg_gate_error": round(metrics["avg_gate_error"], 7),
                    "avg_readout_error": round(metrics["avg_readout_error"], 7),
                    "avg_t1": round(metrics["avg_t1"], 5),
                    "avg_t2": round(metrics["avg_t2"], 5),
                    "decoders": decoders,
                },
            }
            _write_frame(out_handle, frame)

            should_push = telemetry_url and ((poll_count + 1) % args.push_every == 0)
            if should_push:
                warning_rate = sum(warning_levels) / max(1, len(warning_levels))
                payload = _build_telemetry_payload(
                    run_id=args.run_id or "00000000-0000-0000-0000-000000000000",
                    warning_rate=round(warning_rate, 7),
                    noise_samples=all_noise_samples,
                    syndrome_samples=all_syndrome_samples,
                    decoder_interventions=all_decoder_interventions,
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
