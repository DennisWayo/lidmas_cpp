#!/usr/bin/env python3
"""Replay Ankaa-style QEC data into LiDMaS+ normalized stream frames.

Input modes:
- HDF5 file with `hard_measurements` groups (Ankaa-style layout).
- JSON fixture with shape:
  {
    "group": "name",
    "hard_measurements": {
      "S01": [[0, 1, ...], ...],
      "S02": [[...], ...]
    }
  }

Output:
- NDJSON stream frames (stdout or --out).
- Optional rolling telemetry push to LiDMaS+ backend.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def parse_decoders(raw: str) -> list[str]:
    decoders = [item.strip() for item in raw.split(",") if item.strip()]
    return decoders or ["mwpm"]


@dataclass(frozen=True)
class ReplayData:
    source_file: str
    group_name: str
    hard_measurements: dict[str, list[list[int]]]
    shots: int
    rounds: int


def _normalize_matrix(
    raw: Any,
    *,
    max_shots: int,
    max_rounds: int,
) -> list[list[int]]:
    if hasattr(raw, "tolist"):
        raw = raw.tolist()

    if not isinstance(raw, list):
        raise ValueError(f"measurement matrix must be a list-like value, got {type(raw).__name__}.")

    if raw and not isinstance(raw[0], list):
        raw = [raw]

    rows: list[list[int]] = []
    for row in raw[:max_shots]:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, list):
            raise ValueError("measurement row must be list-like.")

        normalized_row: list[int] = []
        for value in row[:max_rounds]:
            try:
                as_int = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"measurement value {value!r} is not integer-convertible.") from exc
            normalized_row.append(1 if as_int != 0 else 0)
        rows.append(normalized_row)

    rows = [row for row in rows if row]
    if not rows:
        raise ValueError("measurement matrix is empty after slicing.")

    min_rounds = min(len(row) for row in rows)
    if min_rounds <= 0:
        raise ValueError("measurement matrix has no rounds.")

    return [row[:min_rounds] for row in rows]


def _load_json_replay(
    input_path: Path,
    *,
    max_shots: int,
    max_rounds: int,
) -> ReplayData:
    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("JSON replay input must be an object.")

    group_name = str(payload.get("group") or "json_fixture")
    hard = payload.get("hard_measurements")
    if not isinstance(hard, dict) or not hard:
        raise ValueError("JSON replay input must contain non-empty 'hard_measurements' object.")

    normalized: dict[str, list[list[int]]] = {}
    for name, matrix in hard.items():
        label = str(name).strip() or "unknown"
        normalized[label] = _normalize_matrix(matrix, max_shots=max_shots, max_rounds=max_rounds)

    return _align_replay_data(
        ReplayData(
            source_file=str(input_path),
            group_name=group_name,
            hard_measurements=normalized,
            shots=0,
            rounds=0,
        )
    )


def _import_h5py():
    try:
        import h5py  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "HDF5 replay requires h5py. Install with: python3 -m pip install --upgrade h5py"
        ) from exc
    return h5py


def _discover_hdf5_group(h5: Any, explicit_group: str | None) -> str:
    if explicit_group:
        if explicit_group in h5:
            return explicit_group
        if explicit_group.startswith("/") and explicit_group[1:] in h5:
            return explicit_group[1:]
        raise ValueError(f"group {explicit_group!r} not found in HDF5 file.")

    if "hard_measurements" in h5:
        return "/"

    candidates: list[str] = []

    def visitor(name: str, obj: Any) -> None:
        if hasattr(obj, "keys") and "hard_measurements" in obj:
            candidates.append(name)

    h5.visititems(visitor)
    if not candidates:
        raise ValueError("no HDF5 group containing 'hard_measurements' was found.")
    candidates.sort()
    return candidates[0]


def _load_hdf5_replay(
    input_path: Path,
    *,
    group_name: str | None,
    max_shots: int,
    max_rounds: int,
) -> ReplayData:
    h5py = _import_h5py()
    with h5py.File(input_path, "r") as h5:
        group_key = _discover_hdf5_group(h5, group_name)
        root = h5 if group_key == "/" else h5[group_key]

        if "hard_measurements" not in root:
            raise ValueError(f"group {group_key!r} does not contain 'hard_measurements'.")
        hard = root["hard_measurements"]

        normalized: dict[str, list[list[int]]] = {}
        for dataset_name in sorted(hard.keys()):
            matrix = hard[dataset_name][()]
            normalized[dataset_name] = _normalize_matrix(
                matrix,
                max_shots=max_shots,
                max_rounds=max_rounds,
            )

        data = ReplayData(
            source_file=str(input_path),
            group_name=group_key,
            hard_measurements=normalized,
            shots=0,
            rounds=0,
        )
        return _align_replay_data(data)


def _align_replay_data(data: ReplayData) -> ReplayData:
    if not data.hard_measurements:
        raise ValueError("no stabilizer measurement datasets found.")

    min_shots = min(len(matrix) for matrix in data.hard_measurements.values())
    if min_shots <= 0:
        raise ValueError("no shots found in measurement datasets.")

    min_rounds = min(len(row) for matrix in data.hard_measurements.values() for row in matrix[:min_shots])
    if min_rounds <= 0:
        raise ValueError("no rounds found in measurement datasets.")

    aligned: dict[str, list[list[int]]] = {}
    for name, matrix in data.hard_measurements.items():
        clipped_rows = [row[:min_rounds] for row in matrix[:min_shots]]
        aligned[name] = clipped_rows

    return ReplayData(
        source_file=data.source_file,
        group_name=data.group_name,
        hard_measurements=aligned,
        shots=min_shots,
        rounds=min_rounds,
    )


def _decoder_scales(decoder: str) -> tuple[float, float]:
    key = decoder.lower()
    if "bp" in key:
        return (0.82, 1.28)
    if "mwpm" in key:
        return (1.22, 0.72)
    if "uf" in key:
        return (0.98, 0.93)
    if "neural" in key:
        return (0.88, 0.78)
    return (1.0, 1.0)


def _build_telemetry_payload(
    run_id: str,
    warning_rate: float,
    noise_samples: list[dict[str, Any]],
    syndrome_samples: list[dict[str, Any]],
    decoder_exact_metrics: list[dict[str, Any]],
    decoder_interventions: list[dict[str, Any]],
    decoder_name: str | None,
    expanded_shot_count: int | None,
) -> dict[str, Any]:
    request_line_count = len(noise_samples)
    response_line_count = request_line_count
    response_ratio = (
        response_line_count / request_line_count if request_line_count > 0 else None
    )
    stabilizer_count = len({sample["stabilizer"] for sample in syndrome_samples})
    rounds = max((int(sample["round"]) for sample in syndrome_samples), default=-1) + 1
    syndrome_opportunities = request_line_count * max(1, stabilizer_count)
    physical_error_events = sum(
        1 for sample in syndrome_samples if sample.get("is_triggered") or int(sample.get("value", 0)) != 0
    )
    physical_error_opportunities = syndrome_opportunities
    physical_error_rate = (
        physical_error_events / physical_error_opportunities
        if physical_error_opportunities > 0
        else None
    )

    primary_exact = None
    normalized_decoder = (decoder_name or "").strip().lower()
    for metric in decoder_exact_metrics:
        metric_decoder = str(metric.get("decoder", "")).strip().lower()
        if normalized_decoder and metric_decoder == normalized_decoder:
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

    residual_syndrome_events = None
    if decoder_name:
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

    legacy_request_count = (
        int(expanded_shot_count)
        if expanded_shot_count is not None
        else max(len(noise_samples), rounds) * max(1, stabilizer_count)
    )
    return {
        "run_id": run_id,
        "request_count": legacy_request_count,
        "request_line_count": request_line_count,
        "response_line_count": response_line_count,
        "response_ratio": response_ratio,
        "expanded_shot_count": expanded_shot_count,
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
        "decoder_exact_metrics": decoder_exact_metrics,
        "decoder_interventions": decoder_interventions,
    }


def _is_logical_failure(flips: int, residual_weight: int) -> bool:
    return residual_weight > max(0, flips)


def _normalize_encoder_state(group_name: str) -> str:
    lowered = group_name.strip().lower()
    safe = "".join(ch if ch.isalnum() else "_" for ch in lowered).strip("_")
    if not safe:
        safe = "replay"
    return f"ankaa_{safe}"


def _build_decoder_exact_metrics(
    decoder_outcomes: dict[str, dict[str, int]],
    encoder_state: str,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for decoder, stats in sorted(decoder_outcomes.items(), key=lambda item: item[0]):
        trials = int(stats.get("trials", 0))
        logical_failures = int(stats.get("logical_failures", 0))
        if trials <= 0:
            continue
        logical_failures = min(logical_failures, trials)
        entries.append(
            {
                "decoder": decoder,
                "trials": trials,
                "logical_failures": logical_failures,
                "encoder_state": encoder_state,
            }
        )
    return entries


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


def _write_frame(out_handle: Any, frame: dict[str, Any]) -> None:
    out_handle.write(json.dumps(frame, separators=(",", ":")) + "\n")
    out_handle.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay Ankaa-style QEC measurements as normalized LiDMaS+ stream frames."
    )
    parser.add_argument("--input", required=True, help="Input file (.h5/.hdf5 or fixture .json).")
    parser.add_argument("--group", default=None, help="HDF5 group containing hard_measurements.")
    parser.add_argument("--max-shots", type=int, default=256, help="Maximum shots to load.")
    parser.add_argument("--max-rounds", type=int, default=128, help="Maximum rounds to load.")
    parser.add_argument("--max-stabilizers", type=int, default=64, help="Maximum stabilizers to stream.")
    parser.add_argument("--decoders", default="mwpm", help="Comma-separated decoder names.")
    parser.add_argument("--frame-cadence", type=float, default=0.0, help="Seconds to sleep between frames.")
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
    parser.add_argument("--push-every", type=int, default=4, help="Push telemetry every N frames.")
    parser.add_argument("--http-timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.max_shots <= 0:
        raise ValueError("--max-shots must be > 0.")
    if args.max_rounds <= 0:
        raise ValueError("--max-rounds must be > 0.")
    if args.max_stabilizers <= 0:
        raise ValueError("--max-stabilizers must be > 0.")
    if args.push_every <= 0:
        raise ValueError("--push-every must be > 0.")

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise ValueError(f"input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".json":
        replay_data = _load_json_replay(
            input_path,
            max_shots=args.max_shots,
            max_rounds=args.max_rounds,
        )
    else:
        replay_data = _load_hdf5_replay(
            input_path,
            group_name=args.group,
            max_shots=args.max_shots,
            max_rounds=args.max_rounds,
        )

    stabilizer_names = sorted(replay_data.hard_measurements.keys())[: args.max_stabilizers]
    if not stabilizer_names:
        raise ValueError("no stabilizers available after --max-stabilizers filter.")

    decoders = parse_decoders(args.decoders)
    telemetry_url = _telemetry_url(args.telemetry_url, args.backend_base_url, args.run_id)

    out_handle = sys.stdout
    close_out = False
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if args.append_out else "w"
        out_handle = out_path.open(mode, encoding="utf-8")
        close_out = True

    all_noise_samples: list[dict[str, Any]] = []
    all_syndrome_samples: list[dict[str, Any]] = []
    all_decoder_interventions: list[dict[str, Any]] = []
    decoder_outcomes: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"trials": 0, "logical_failures": 0}
    )
    warning_levels: list[float] = []
    pushed = 0
    encoder_state = _normalize_encoder_state(replay_data.group_name)

    try:
        for round_index in range(replay_data.rounds):
            syndrome_chunk: list[dict[str, Any]] = []
            trigger_accumulator = 0.0

            for stabilizer_name in stabilizer_names:
                matrix = replay_data.hard_measurements[stabilizer_name]
                ones = sum(matrix[shot_index][round_index] for shot_index in range(replay_data.shots))
                probability = ones / replay_data.shots
                trigger_accumulator += probability
                triggered = probability >= 0.5
                syndrome_chunk.append(
                    {
                        "round": round_index,
                        "stabilizer": stabilizer_name,
                        "value": 1 if triggered else 0,
                        "is_triggered": bool(triggered),
                    }
                )

            trigger_rate = trigger_accumulator / len(stabilizer_names)
            physical_error_rate = clamp(0.001 + trigger_rate * 0.18, 0.0005, 0.25)
            photon_loss_rate = clamp(0.0005 + physical_error_rate * 0.42, 0.0001, 0.2)
            displacement_sigma = clamp(0.06 + math.sqrt(physical_error_rate) * 0.55, 0.04, 1.0)

            noise_sample = {
                "index": round_index,
                "physical_error_rate": round(physical_error_rate, 7),
                "displacement_sigma": round(displacement_sigma, 7),
                "photon_loss_rate": round(photon_loss_rate, 7),
            }
            warning_levels.append(physical_error_rate)

            intervention_chunk: list[dict[str, Any]] = []
            for decoder in decoders:
                flip_scale, residual_scale = _decoder_scales(decoder)
                flips = max(
                    1,
                    int(round((trigger_rate * 8.0 + physical_error_rate * 90.0) * flip_scale)),
                )
                residual_weight = max(
                    0,
                    int(round((1.0 - trigger_rate) * 4.0 * residual_scale + physical_error_rate * 35.0)),
                )
                intervention_chunk.append(
                    {
                        "decoder": decoder,
                        "round": round_index,
                        "flips": flips,
                        "residual_weight": residual_weight,
                    }
                )
                outcome = decoder_outcomes[decoder]
                outcome["trials"] += 1
                if _is_logical_failure(flips, residual_weight):
                    outcome["logical_failures"] += 1

            all_noise_samples.append(noise_sample)
            all_syndrome_samples.extend(syndrome_chunk)
            all_decoder_interventions.extend(intervention_chunk)

            frame = {
                "source": "ankaa_replay",
                "timestamp": utc_now_iso(),
                "frame_index": round_index,
                "group": replay_data.group_name,
                "round": round_index,
                "noise_sample": noise_sample,
                "syndrome_samples": syndrome_chunk,
                "decoder_interventions": intervention_chunk,
                "meta": {
                    "input_file": replay_data.source_file,
                    "shots_used": replay_data.shots,
                    "stabilizers_used": len(stabilizer_names),
                    "decoders": decoders,
                },
            }
            _write_frame(out_handle, frame)

            should_push = telemetry_url and ((round_index + 1) % args.push_every == 0 or round_index + 1 == replay_data.rounds)
            if should_push:
                warning_rate = sum(warning_levels) / max(1, len(warning_levels))
                payload = _build_telemetry_payload(
                    run_id=args.run_id or "00000000-0000-0000-0000-000000000000",
                    warning_rate=round(warning_rate, 7),
                    noise_samples=all_noise_samples,
                    syndrome_samples=all_syndrome_samples,
                    decoder_exact_metrics=_build_decoder_exact_metrics(decoder_outcomes, encoder_state),
                    decoder_interventions=all_decoder_interventions,
                    decoder_name=decoders[0] if decoders else None,
                    expanded_shot_count=replay_data.shots * replay_data.rounds,
                )
                status_code, response_text = _post_json(
                    telemetry_url,
                    payload,
                    timeout_s=args.http_timeout,
                )
                if status_code >= 300:
                    raise RuntimeError(
                        f"telemetry push failed ({status_code}) at round {round_index}: {response_text}"
                    )
                pushed += 1

            if args.frame_cadence > 0.0:
                time.sleep(args.frame_cadence)

        print(
            (
                f"[ankaa_replay] completed rounds={replay_data.rounds} "
                f"stabilizers={len(stabilizer_names)} shots={replay_data.shots} "
                f"frames={replay_data.rounds} telemetry_pushes={pushed}"
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
