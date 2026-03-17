#!/usr/bin/env python3
"""Convert Xanadu-style job JSON into LiDMaS+ decoder_io NDJSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_SYNDROME_TYPE_MAP = {
    "x": "X",
    "z": "Z",
    "unknown": "UNKNOWN",
}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_samples(payload: Any) -> list[Any]:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.extend(
            [
                payload.get("output"),
                payload.get("samples"),
                payload.get("result", {}).get("output") if isinstance(payload.get("result"), dict) else None,
                payload.get("result", {}).get("samples") if isinstance(payload.get("result"), dict) else None,
                payload.get("data", {}).get("output") if isinstance(payload.get("data"), dict) else None,
                payload.get("data", {}).get("samples") if isinstance(payload.get("data"), dict) else None,
            ]
        )
    else:
        candidates.append(payload)

    for cand in candidates:
        if cand is None:
            continue
        if isinstance(cand, list):
            if not cand:
                return []
            # If this is a single shot vector, wrap to one-shot list.
            if all(not isinstance(x, (list, dict)) for x in cand):
                return [cand]
            return cand
    raise ValueError(
        "Could not locate sample list in input JSON. Expected one of: "
        "output, samples, result.output, result.samples, data.output, data.samples."
    )


def _normalize_shot(shot: Any, shot_index: int) -> list[int]:
    if isinstance(shot, dict):
        if "output" in shot:
            shot = shot["output"]
        elif "samples" in shot:
            shot = shot["samples"]
        else:
            raise ValueError(f"Shot {shot_index}: dict shot does not contain 'output' or 'samples'.")
    if not isinstance(shot, list):
        raise ValueError(f"Shot {shot_index}: expected list, got {type(shot).__name__}.")
    out: list[int] = []
    for i, v in enumerate(shot):
        try:
            iv = int(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Shot {shot_index}, mode {i}: value {v!r} is not integer-convertible.") from exc
        if iv < 0:
            raise ValueError(f"Shot {shot_index}, mode {i}: value {iv} is negative.")
        out.append(iv)
    return out


def _parse_type(raw: Any, stab_index: int) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"Stabilizer {stab_index}: 'type' must be string.")
    key = raw.strip().lower()
    if key not in _SYNDROME_TYPE_MAP:
        raise ValueError(f"Stabilizer {stab_index}: unsupported type {raw!r}. Use X, Z, or UNKNOWN.")
    return _SYNDROME_TYPE_MAP[key]


def _parse_modes(raw: Any, stab_index: int) -> list[int]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Stabilizer {stab_index}: 'modes' must be a non-empty list.")
    modes: list[int] = []
    for m in raw:
        if not isinstance(m, int) or m < 0:
            raise ValueError(f"Stabilizer {stab_index}: mode index {m!r} must be non-negative integer.")
        modes.append(m)
    return modes


def _parse_meta_pairs(items: list[str]) -> dict[str, str]:
    meta: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --meta '{item}'. Use key=value.")
        k, v = item.split("=", 1)
        k = k.strip()
        if not k:
            raise ValueError(f"Invalid --meta '{item}': key is empty.")
        meta[k] = v
    return meta


def _parse_loss_list(raw: str) -> list[float]:
    s = raw.strip()
    if not s:
        return []
    vals: list[float] = []
    for chunk in s.split(","):
        val = float(chunk.strip())
        if val < 0.0:
            raise ValueError("Loss probabilities must be non-negative.")
        vals.append(val)
    return vals


def _job_identifier(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("job_id", "id", "jobId"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert Xanadu-style job output JSON to LiDMaS+ decoder_io NDJSON."
    )
    p.add_argument("--input", required=True, help="Path to Xanadu job JSON.")
    p.add_argument("--mapping", required=True, help="Path to syndrome mapping JSON.")
    p.add_argument("--out", required=True, help="Output NDJSON path.")
    p.add_argument("--max-shots", type=int, default=0, help="Optional cap on number of shots (0 = all).")
    p.add_argument("--code-id", default="", help="Override code_id from mapping.")
    p.add_argument("--n-qubits", type=int, default=0, help="Override n_qubits from mapping.")
    p.add_argument("--round-start", type=int, default=None, help="Override mapping round_start.")
    p.add_argument("--round-stride", type=int, default=None, help="Override mapping round_stride.")
    p.add_argument("--time-ns-start", type=int, default=None, help="Override mapping time_ns_start.")
    p.add_argument("--time-ns-stride", type=int, default=None, help="Override mapping time_ns_stride.")
    p.add_argument("--sigma", type=float, default=0.0, help="Noise sigma in emitted requests.")
    p.add_argument("--gate-error-rate", type=float, default=0.0, help="Noise gate_error_rate.")
    p.add_argument("--meas-error-rate", type=float, default=0.0, help="Noise meas_error_rate.")
    p.add_argument("--idle-error-rate", type=float, default=0.0, help="Noise idle_error_rate.")
    p.add_argument(
        "--loss-prob-by-qubit",
        default="",
        help="Comma-separated per-qubit loss probabilities (optional).",
    )
    p.add_argument(
        "--meta",
        action="append",
        default=[],
        help="Extra metadata key=value (repeatable).",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()

    in_path = Path(args.input)
    map_path = Path(args.mapping)
    out_path = Path(args.out)

    payload = _load_json(in_path)
    mapping = _load_json(map_path)

    if not isinstance(mapping, dict):
        raise ValueError("Mapping JSON must be an object.")
    if "stabilizers" not in mapping or not isinstance(mapping["stabilizers"], list):
        raise ValueError("Mapping JSON must contain list field 'stabilizers'.")

    code_id = args.code_id or str(mapping.get("code_id", "")).strip()
    if not code_id:
        raise ValueError("code_id missing. Provide in mapping or via --code-id.")

    n_qubits = args.n_qubits if args.n_qubits > 0 else int(mapping.get("n_qubits", 0))
    if n_qubits <= 0:
        raise ValueError("n_qubits missing/invalid. Provide in mapping or via --n-qubits.")

    round_start = int(mapping.get("round_start", 0)) if args.round_start is None else args.round_start
    round_stride = int(mapping.get("round_stride", 1)) if args.round_stride is None else args.round_stride
    time_ns_start = int(mapping.get("time_ns_start", 0)) if args.time_ns_start is None else args.time_ns_start
    time_ns_stride = int(mapping.get("time_ns_stride", 1000)) if args.time_ns_stride is None else args.time_ns_stride
    if round_stride == 0:
        raise ValueError("round_stride cannot be zero.")
    if time_ns_stride < 0:
        raise ValueError("time_ns_stride must be >= 0.")

    base_meta: dict[str, str] = {}
    mapping_meta = mapping.get("metadata", {})
    if isinstance(mapping_meta, dict):
        for k, v in mapping_meta.items():
            base_meta[str(k)] = str(v)
    base_meta.update(_parse_meta_pairs(args.meta))

    jid = _job_identifier(payload)
    if jid and "job_id" not in base_meta:
        base_meta["job_id"] = jid

    shots_raw = _extract_samples(payload)
    if args.max_shots > 0:
        shots_raw = shots_raw[: args.max_shots]

    loss_list = _parse_loss_list(args.loss_prob_by_qubit)

    requests: list[dict[str, Any]] = []
    stabilizers = mapping["stabilizers"]

    for i, shot_raw in enumerate(shots_raw):
        shot = _normalize_shot(shot_raw, i)
        events: list[dict[str, Any]] = []
        shot_time = time_ns_start + i * time_ns_stride

        for s_i, stab in enumerate(stabilizers):
            if not isinstance(stab, dict):
                raise ValueError(f"Stabilizer {s_i}: expected object.")
            stab_index = int(stab.get("index", s_i))
            stab_type = _parse_type(stab.get("type", "UNKNOWN"), s_i)
            modes = _parse_modes(stab.get("modes", []), s_i)
            mod = int(stab.get("mod", 2))
            trigger_on = int(stab.get("trigger_on", 1))
            time_offset_ns = int(stab.get("time_offset_ns", 0))
            if mod <= 0:
                raise ValueError(f"Stabilizer {s_i}: mod must be > 0.")
            if trigger_on < 0 or trigger_on >= mod:
                raise ValueError(f"Stabilizer {s_i}: trigger_on must be in [0, mod).")

            parity_sum = 0
            for m in modes:
                if m >= len(shot):
                    raise ValueError(
                        f"Shot {i}: mode index {m} out of range for shot width {len(shot)}."
                    )
                parity_sum += shot[m]
            bit = parity_sum % mod
            if bit == trigger_on:
                events.append(
                    {
                        "index": stab_index,
                        "time_ns": shot_time + time_offset_ns,
                        "type": stab_type,
                    }
                )

        req: dict[str, Any] = {
            "code_id": code_id,
            "round_index": round_start + i * round_stride,
            "n_qubits": n_qubits,
            "events": events,
            "noise": {
                "sigma": args.sigma,
                "gate_error_rate": args.gate_error_rate,
                "meas_error_rate": args.meas_error_rate,
                "idle_error_rate": args.idle_error_rate,
                "loss_prob_by_qubit": loss_list,
            },
            "metadata": dict(base_meta),
        }
        req["metadata"]["shot_index"] = str(i)
        requests.append(req)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, separators=(",", ":")) + "\n")

    print(f"Wrote {len(requests)} DecodeRequest lines to {out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
