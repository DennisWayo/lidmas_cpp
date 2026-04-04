#!/usr/bin/env python3
"""Generate non-photonic synthetic requests matched to reference syndrome sparsity."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--reference",
        required=True,
        help="Reference request NDJSON file used for sparsity matching.",
    )
    p.add_argument("--dataset-label", required=True, help="Synthetic dataset label.")
    p.add_argument("--out-train", required=True, help="Output synthetic train NDJSON.")
    p.add_argument("--out-heldout", required=True, help="Output synthetic heldout NDJSON.")
    p.add_argument("--out-summary", required=True, help="Output JSON summary path.")
    p.add_argument("--distance", type=int, default=5, help="Surface-code distance.")
    p.add_argument("--n-train", type=int, default=1000, help="Train request count.")
    p.add_argument("--n-heldout", type=int, default=500, help="Heldout request count.")
    p.add_argument("--seed", type=int, default=12345, help="PRNG seed.")
    return p.parse_args()


def _safe_int(v: Any, default: int = 0) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _h_index(x: int, y: int, d: int) -> int:
    return y * (d - 1) + x


def _v_index(x: int, y: int, d: int) -> int:
    h_count = d * (d - 1)
    return h_count + y * d + x


def _build_hz_supports(d: int) -> list[list[int]]:
    # Z checks (plaquettes) detect X errors.
    supports: list[list[int]] = []
    for y in range(d - 1):
        for x in range(d - 1):
            supports.append(
                [
                    _h_index(x, y, d),
                    _h_index(x, y + 1, d),
                    _v_index(x, y, d),
                    _v_index(x + 1, y, d),
                ]
            )
    return supports


def _multiply_supports(supports: list[list[int]], vec: list[int]) -> list[int]:
    out: list[int] = []
    for row in supports:
        parity = 0
        for q in row:
            if 0 <= q < len(vec):
                parity ^= (vec[q] & 1)
        out.append(parity)
    return out


def _line_obj(line: str) -> dict[str, Any] | None:
    s = line.strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _reference_stats(path: Path, d: int) -> tuple[int, float, float]:
    mz = (d - 1) * (d - 1)
    request_lines = 0
    nonempty = 0
    event_sum = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            obj = _line_obj(raw)
            if obj is None:
                continue
            request_lines += 1
            sz = [0] * mz
            events = obj.get("events", [])
            if isinstance(events, list):
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    if str(ev.get("type", "")).upper() != "Z":
                        continue
                    idx = _safe_int(ev.get("index"), default=-1)
                    if 0 <= idx < mz:
                        sz[idx] ^= 1
            c = sum(sz)
            event_sum += c
            if c > 0:
                nonempty += 1

    if request_lines <= 0:
        return 0, 0.0, 0.0
    return (
        request_lines,
        float(event_sum) / float(request_lines),
        float(nonempty) / float(request_lines),
    )


def _simulate_stats(
    p_ex: float,
    p_meas: float,
    n_trials: int,
    n_data: int,
    hz_supports: list[list[int]],
    rng: random.Random,
) -> tuple[float, float]:
    event_sum = 0
    nonempty = 0
    for _ in range(n_trials):
        ex = [1 if rng.random() < p_ex else 0 for _ in range(n_data)]
        sz = _multiply_supports(hz_supports, ex)
        if p_meas > 0.0:
            for i in range(len(sz)):
                if rng.random() < p_meas:
                    sz[i] ^= 1
        c = sum(sz)
        event_sum += c
        if c > 0:
            nonempty += 1
    return (
        float(event_sum) / float(n_trials),
        float(nonempty) / float(n_trials),
    )


def _fit_params(
    target_avg_events: float,
    target_nonempty_rate: float,
    n_data: int,
    hz_supports: list[list[int]],
    seed: int,
) -> tuple[float, float]:
    # Grid search on (p_ex, p_meas) for robust deterministic matching.
    best_p = 0.0
    best_p_meas = 0.0
    best_err = 1e18
    for i in range(1, 61):
        p = i / 1000.0  # 0.001 .. 0.060
        for j in range(0, 101):
            p_meas = j / 1000.0  # 0.000 .. 0.100
            rng = random.Random(seed + 991 * i + 37 * j)
            avg_events, nonempty_rate = _simulate_stats(
                p_ex=p,
                p_meas=p_meas,
                n_trials=900,
                n_data=n_data,
                hz_supports=hz_supports,
                rng=rng,
            )
            err = abs(avg_events - target_avg_events) + abs(nonempty_rate - target_nonempty_rate)
            if err < best_err:
                best_err = err
                best_p = p
                best_p_meas = p_meas
    return best_p, best_p_meas


def _indices_from_bitmask(mask: list[int]) -> list[int]:
    return [i for i, b in enumerate(mask) if (b & 1) != 0]


def _request_obj(
    *,
    d: int,
    dataset_label: str,
    split: str,
    shot_index: int,
    ex: list[int],
    sz: list[int],
    p_ex: float,
    p_meas: float,
    target_avg_events: float,
    target_nonempty_rate: float,
) -> dict[str, Any]:
    events = [{"index": i, "time_ns": (shot_index + 1) * 1000, "type": "Z"} for i, b in enumerate(sz) if b]
    return {
        "code_id": f"gkp_surface_d{d}",
        "round_index": shot_index,
        "n_qubits": 2 * d * (d - 1),
        "events": events,
        "noise": {
            "sigma": 0.0,
            "gate_error_rate": p_ex,
            "meas_error_rate": p_meas,
            "idle_error_rate": 0.0,
            "loss_prob_by_qubit": [],
        },
        "metadata": {
            "hardware": "synthetic_non_photonic",
            "dataset": dataset_label,
            "split": split,
            "matched_to_mode": "real_public_reference",
            "target_avg_request_events": f"{target_avg_events:.6f}",
            "target_nonempty_request_event_rate": f"{target_nonempty_rate:.6f}",
            "synthetic_p_ex": f"{p_ex:.6f}",
            "synthetic_p_meas": f"{p_meas:.6f}",
            "true_ex_indices": _indices_from_bitmask(ex),
            "true_ez_indices": [],
        },
    }


def _write_requests(
    path: Path,
    *,
    d: int,
    dataset_label: str,
    split: str,
    n_shots: int,
    p_ex: float,
    p_meas: float,
    hz_supports: list[list[int]],
    target_avg_events: float,
    target_nonempty_rate: float,
    rng: random.Random,
) -> tuple[float, float]:
    n_data = 2 * d * (d - 1)
    event_sum = 0
    nonempty = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for shot in range(n_shots):
            ex = [1 if rng.random() < p_ex else 0 for _ in range(n_data)]
            sz = _multiply_supports(hz_supports, ex)
            if p_meas > 0.0:
                for i in range(len(sz)):
                    if rng.random() < p_meas:
                        sz[i] ^= 1
            c = sum(sz)
            event_sum += c
            if c > 0:
                nonempty += 1
            obj = _request_obj(
                d=d,
                dataset_label=dataset_label,
                split=split,
                shot_index=shot,
                ex=ex,
                sz=sz,
                p_ex=p_ex,
                p_meas=p_meas,
                target_avg_events=target_avg_events,
                target_nonempty_rate=target_nonempty_rate,
            )
            f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return (
        float(event_sum) / float(max(1, n_shots)),
        float(nonempty) / float(max(1, n_shots)),
    )


def main() -> int:
    args = parse_args()
    ref_path = Path(args.reference)
    out_train = Path(args.out_train)
    out_heldout = Path(args.out_heldout)
    out_summary = Path(args.out_summary)
    d = args.distance

    n_data = 2 * d * (d - 1)
    hz_supports = _build_hz_supports(d)
    ref_lines, target_avg_events, target_nonempty_rate = _reference_stats(ref_path, d)
    if ref_lines <= 0:
        raise SystemExit(f"Reference file has no valid request lines: {ref_path}")

    p_ex, p_meas = _fit_params(
        target_avg_events=target_avg_events,
        target_nonempty_rate=target_nonempty_rate,
        n_data=n_data,
        hz_supports=hz_supports,
        seed=args.seed,
    )

    rng_train = random.Random(args.seed + 17)
    rng_heldout = random.Random(args.seed + 29)
    train_avg, train_nonempty = _write_requests(
        out_train,
        d=d,
        dataset_label=args.dataset_label,
        split="train",
        n_shots=args.n_train,
        p_ex=p_ex,
        p_meas=p_meas,
        hz_supports=hz_supports,
        target_avg_events=target_avg_events,
        target_nonempty_rate=target_nonempty_rate,
        rng=rng_train,
    )
    heldout_avg, heldout_nonempty = _write_requests(
        out_heldout,
        d=d,
        dataset_label=args.dataset_label,
        split="heldout",
        n_shots=args.n_heldout,
        p_ex=p_ex,
        p_meas=p_meas,
        hz_supports=hz_supports,
        target_avg_events=target_avg_events,
        target_nonempty_rate=target_nonempty_rate,
        rng=rng_heldout,
    )

    summary = {
        "dataset": args.dataset_label,
        "reference_file": str(ref_path),
        "reference_lines": ref_lines,
        "reference_avg_request_events": target_avg_events,
        "reference_nonempty_request_event_rate": target_nonempty_rate,
        "distance": d,
        "n_data_qubits": n_data,
        "fitted_p_ex": p_ex,
        "fitted_p_meas": p_meas,
        "train_file": str(out_train),
        "heldout_file": str(out_heldout),
        "train_lines": args.n_train,
        "train_avg_request_events": train_avg,
        "train_nonempty_request_event_rate": train_nonempty,
        "heldout_lines": args.n_heldout,
        "heldout_avg_request_events": heldout_avg,
        "heldout_nonempty_request_event_rate": heldout_nonempty,
    }
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
