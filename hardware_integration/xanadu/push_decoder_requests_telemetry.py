#!/usr/bin/env python3
"""Push exact Xanadu replay telemetry from decoder request/response NDJSON."""

from __future__ import annotations

import argparse
import collections
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


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


def _int_or_default(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _float_or_default(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _float_list(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    out: list[float] = []
    for value in values:
        parsed = _float_or_default(value, math.nan)
        if math.isnan(parsed) or math.isinf(parsed):
            continue
        out.append(parsed)
    return out


def _event_index_set(events: Any) -> set[int]:
    if not isinstance(events, list):
        return set()
    out: set[int] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        index = _int_or_default(event.get("index"), -1)
        if index >= 0:
            out.add(index)
    return out


def _flip_index_set(correction: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for key in ("qubit_flips", "qubit_flips_x", "qubit_flips_z"):
        values = correction.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            index = _int_or_default(value, -1)
            if index >= 0:
                out.add(index)
    return out


def _load_response_rows(path: Path, expected_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in responses at row {len(rows) + 1}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise ValueError(
                    f"invalid response payload type at row {len(rows) + 1}: expected object"
                )
            rows.append(payload)
            if len(rows) >= expected_rows:
                break
    if len(rows) != expected_rows:
        raise ValueError(
            f"response frame count mismatch: expected {expected_rows}, got {len(rows)} from {path}"
        )
    return rows


def _response_decoder_name(payload: dict[str, Any]) -> str:
    correction = payload.get("correction")
    if not isinstance(correction, dict):
        return ""
    return str(correction.get("decoder_name", "")).strip()


def _dominant_decoder_name(rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for payload in rows:
        name = _response_decoder_name(payload)
        if not name:
            continue
        key = name.strip().lower()
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _logical_failure(syndrome_count: int, flips: int, diagnostics: dict[str, Any]) -> bool:
    return ("error" in diagnostics) or (syndrome_count > 0 and flips == 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push exact run telemetry from Xanadu decoder request/response NDJSON.",
    )
    parser.add_argument("--input", required=True, help="Decoder request NDJSON path.")
    parser.add_argument("--run-id", required=True, help="Run UUID for telemetry upsert.")
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
    parser.add_argument(
        "--max-frames",
        type=int,
        default=1200,
        help="Maximum request rows to ingest (0 = all).",
    )
    parser.add_argument(
        "--responses",
        action="append",
        required=True,
        help=(
            "Decoder response NDJSON path. Repeat this flag to include shadow-decoder "
            "response files for exact per-decoder metrics."
        ),
    )
    parser.add_argument(
        "--primary-decoder",
        default="mwpm",
        help="Primary correction decoder for interventions/warning stream (default: mwpm).",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_frames < 0:
        raise ValueError("--max-frames must be >= 0.")
    if args.http_timeout <= 0:
        raise ValueError("--http-timeout must be > 0.")

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise ValueError(f"input file not found: {input_path}")
    response_specs = args.responses or []
    response_paths = [Path(spec).expanduser().resolve() for spec in response_specs]
    for response_path in response_paths:
        if not response_path.exists():
            raise ValueError(f"responses file not found: {response_path}")

    telemetry_url = _telemetry_url(args.telemetry_url, args.backend_base_url, args.run_id)
    if not telemetry_url:
        raise ValueError(
            "missing telemetry target: set --telemetry-url or --backend-base-url with --run-id."
        )

    frames: list[dict[str, Any]] = []
    request_count = 0
    max_event_index = -1

    with input_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if args.max_frames > 0 and len(frames) >= args.max_frames:
                break

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in requests at row {len(frames) + 1}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise ValueError(
                    f"invalid request payload type at row {len(frames) + 1}: expected object"
                )

            metadata = payload.get("metadata")
            noise = payload.get("noise")
            events = payload.get("events")
            if not isinstance(metadata, dict):
                metadata = {}
            if not isinstance(noise, dict):
                noise = {}

            repeat_count = max(1, _int_or_default(metadata.get("repeat_count"), 1))
            request_count += repeat_count

            triggered_indices = _event_index_set(events)
            if triggered_indices:
                max_event_index = max(max_event_index, max(triggered_indices))

            sigma = clamp(_float_or_default(noise.get("sigma"), 0.0), 0.0, 5.0)
            gate_error_rate = clamp(_float_or_default(noise.get("gate_error_rate"), 0.0), 0.0, 1.0)

            physical_error_rate_raw = _float_or_default(noise.get("physical_error_rate"), math.nan)
            if math.isnan(physical_error_rate_raw) or math.isinf(physical_error_rate_raw):
                physical_error_rate = gate_error_rate
            else:
                physical_error_rate = clamp(physical_error_rate_raw, 0.0, 1.0)

            photon_loss_rate_raw = _float_or_default(noise.get("photon_loss_rate"), math.nan)
            if math.isnan(photon_loss_rate_raw) or math.isinf(photon_loss_rate_raw):
                photon_loss_rate = clamp(_average(_float_list(noise.get("loss_prob_by_qubit"))) or 0.0, 0.0, 1.0)
            else:
                photon_loss_rate = clamp(photon_loss_rate_raw, 0.0, 1.0)

            frames.append(
                {
                    "repeat_count": repeat_count,
                    "triggered_indices": triggered_indices,
                    "physical_error_rate": physical_error_rate,
                    "photon_loss_rate": photon_loss_rate,
                    "displacement_sigma": sigma,
                    "code_id": str(payload.get("code_id", "")).strip(),
                }
            )

    if not frames:
        raise ValueError("input NDJSON did not contain any request frames.")

    response_sources: list[dict[str, Any]] = []
    seen_decoders: set[str] = set()
    for response_path in response_paths:
        rows = _load_response_rows(response_path, len(frames))
        dominant_decoder = _dominant_decoder_name(rows)
        if dominant_decoder:
            if dominant_decoder in seen_decoders:
                print(
                    f"[xanadu_telemetry] warning: duplicate response source for decoder "
                    f"{dominant_decoder}; skipping {response_path}"
                )
                continue
            seen_decoders.add(dominant_decoder)
        response_sources.append(
            {
                "path": response_path,
                "rows": rows,
                "dominant_decoder": dominant_decoder,
            }
        )

    if not response_sources:
        raise ValueError("no valid response sources were provided")

    primary_decoder = str(args.primary_decoder or "").strip().lower()
    primary_source = response_sources[0]
    if primary_decoder:
        for source in response_sources:
            if source["dominant_decoder"] == primary_decoder:
                primary_source = source
                break

    primary_rows: list[dict[str, Any]] = primary_source["rows"]
    primary_decoder_name = str(primary_source["dominant_decoder"] or primary_decoder or "mwpm").strip() or "mwpm"
    stabilizer_count = max(3, max_event_index + 1)

    noise_samples: list[dict[str, Any]] = []
    syndrome_samples: list[dict[str, Any]] = []
    decoder_interventions: list[dict[str, Any]] = []
    decoder_stats: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"trials": 0, "logical_failures": 0, "encoder_state": ""}
    )
    warning_numer = 0
    warning_denom = 0
    physical_error_events = 0
    residual_syndrome_events = 0

    for round_index, frame in enumerate(frames):
        response = primary_rows[round_index]
        correction = response.get("correction")
        diagnostics = response.get("diagnostics")
        if not isinstance(correction, dict):
            correction = {}
        if not isinstance(diagnostics, dict):
            diagnostics = {}

        round_primary_decoder = str(correction.get("decoder_name", "")).strip() or primary_decoder_name
        flip_indices = _flip_index_set(correction)
        flips = len(flip_indices)
        sx_count = max(0, _int_or_default(diagnostics.get("sx_count"), 0))
        sz_count = max(0, _int_or_default(diagnostics.get("sz_count"), 0))
        syndrome_count = sx_count + sz_count
        logical_failure = _logical_failure(syndrome_count, flips, diagnostics)
        residual_weight = syndrome_count if logical_failure else 0
        repeat_count = int(frame["repeat_count"])
        triggered_indices = frame["triggered_indices"]
        physical_error_events += len(triggered_indices)
        residual_syndrome_events += residual_weight

        decoder_interventions.append(
            {
                "decoder": round_primary_decoder,
                "round": round_index,
                "flips": flips,
                "residual_weight": residual_weight,
            }
        )

        for source in response_sources:
            per_response = source["rows"][round_index]
            per_correction = per_response.get("correction")
            per_diagnostics = per_response.get("diagnostics")
            if not isinstance(per_correction, dict):
                per_correction = {}
            if not isinstance(per_diagnostics, dict):
                per_diagnostics = {}

            decoder = (
                str(per_correction.get("decoder_name", "")).strip()
                or str(source["dominant_decoder"]).strip()
                or "mwpm"
            )
            decoder_flips = len(_flip_index_set(per_correction))
            sx_per = max(0, _int_or_default(per_diagnostics.get("sx_count"), 0))
            sz_per = max(0, _int_or_default(per_diagnostics.get("sz_count"), 0))
            syndrome_per = sx_per + sz_per
            decoder_failed = _logical_failure(syndrome_per, decoder_flips, per_diagnostics)

            stats = decoder_stats[decoder]
            stats["trials"] += repeat_count
            if decoder_failed:
                stats["logical_failures"] += repeat_count

            encoder_state = str(per_diagnostics.get("code_id", "")).strip() or str(frame["code_id"]).strip()
            if encoder_state:
                stats["encoder_state"] = encoder_state

        warning_flag = bool(str(diagnostics.get("warning", "")).strip()) or ("error" in diagnostics)
        warning_numer += repeat_count if warning_flag else 0
        warning_denom += repeat_count

        noise_samples.append(
            {
                "index": round_index,
                "physical_error_rate": round(float(frame["physical_error_rate"]), 7),
                "displacement_sigma": round(float(frame["displacement_sigma"]), 7),
                "photon_loss_rate": round(float(frame["photon_loss_rate"]), 7),
            }
        )

        for stabilizer_index in range(stabilizer_count):
            is_triggered = stabilizer_index in triggered_indices
            syndrome_samples.append(
                {
                    "round": round_index,
                    "stabilizer": f"S{(stabilizer_index + 1):02d}",
                    "value": 1 if is_triggered else 0,
                    "is_triggered": bool(is_triggered),
                }
            )

    decoder_exact_metrics: list[dict[str, Any]] = []
    for decoder, stats in sorted(decoder_stats.items(), key=lambda item: item[0]):
        trials = int(stats.get("trials", 0))
        logical_failures = min(int(stats.get("logical_failures", 0)), trials)
        if trials <= 0:
            continue
        decoder_exact_metrics.append(
            {
                "decoder": decoder,
                "trials": trials,
                "logical_failures": logical_failures,
                "encoder_state": str(stats.get("encoder_state", "")).strip() or "xanadu_gkp_replay",
            }
        )
    if not decoder_exact_metrics:
        raise ValueError("no valid decoder exact metrics could be derived from responses")

    warning_rate = warning_numer / max(1, warning_denom)
    request_line_count = len(frames)
    response_line_count = len(primary_rows)
    response_ratio = (
        response_line_count / request_line_count if request_line_count > 0 else None
    )
    expanded_shot_count = request_count
    syndrome_opportunities = request_line_count * stabilizer_count
    physical_error_opportunities = syndrome_opportunities
    physical_error_rate = (
        physical_error_events / physical_error_opportunities
        if physical_error_opportunities > 0
        else None
    )
    residual_syndrome_rate = (
        residual_syndrome_events / syndrome_opportunities
        if syndrome_opportunities > 0
        else None
    )

    primary_exact = None
    for metric in decoder_exact_metrics:
        metric_decoder = str(metric.get("decoder", "")).strip().lower()
        if metric_decoder == primary_decoder_name.strip().lower():
            primary_exact = metric
            break
    if primary_exact is None and decoder_exact_metrics:
        primary_exact = decoder_exact_metrics[0]

    logical_failures = int(primary_exact.get("logical_failures", 0)) if primary_exact else None
    logical_trials = int(primary_exact.get("trials", 0)) if primary_exact else None
    logical_error_rate = (
        (logical_failures / logical_trials)
        if logical_failures is not None and logical_trials is not None and logical_trials > 0
        else None
    )
    logical_decoder_name = str(primary_exact.get("decoder", "")).strip() if primary_exact else None

    telemetry_payload = {
        "run_id": args.run_id,
        "request_count": expanded_shot_count,
        "request_line_count": request_line_count,
        "response_line_count": response_line_count,
        "response_ratio": round(response_ratio, 9) if response_ratio is not None else None,
        "expanded_shot_count": expanded_shot_count,
        "rounds": len(frames),
        "stabilizer_count": stabilizer_count,
        "syndrome_opportunities": syndrome_opportunities,
        "decoder_name": logical_decoder_name,
        "logical_failures": logical_failures,
        "logical_trials": logical_trials,
        "logical_error_rate": round(logical_error_rate, 12) if logical_error_rate is not None else None,
        "physical_error_events": physical_error_events,
        "physical_error_opportunities": physical_error_opportunities,
        "physical_error_rate": round(physical_error_rate, 12) if physical_error_rate is not None else None,
        "residual_syndrome_events": residual_syndrome_events,
        "residual_syndrome_rate": (
            round(residual_syndrome_rate, 12) if residual_syndrome_rate is not None else None
        ),
        "warning_rate": round(warning_rate, 7),
        "noise_samples": noise_samples,
        "syndrome_samples": syndrome_samples,
        "decoder_exact_metrics": decoder_exact_metrics,
        "decoder_interventions": decoder_interventions,
    }

    status_code, response_text = _post_json(
        telemetry_url,
        telemetry_payload,
        timeout_s=args.http_timeout,
    )
    if status_code >= 300:
        raise RuntimeError(f"telemetry push failed ({status_code}): {response_text}")

    decoders = ",".join(metric["decoder"] for metric in decoder_exact_metrics)
    print(
        (
            f"[xanadu_telemetry] pushed run_id={args.run_id} frames={len(frames)} "
            f"request_lines={request_line_count} response_lines={response_line_count} "
            f"expanded_shots={expanded_shot_count} stabilizers={stabilizer_count} "
            f"exact_metrics_source=responses decoders={decoders} primary={primary_decoder_name}"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
