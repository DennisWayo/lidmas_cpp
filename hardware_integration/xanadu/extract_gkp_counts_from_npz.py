#!/usr/bin/env python3
"""Aggregate Xanadu GKP NPZ files into a count-table JSON."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

_INT_RE = re.compile(r"-?\d+")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root", required=True, help="Root directory containing extracted GKP .npz files.")
    p.add_argument("--out", required=True, help="Output JSON file path with count-table format.")
    p.add_argument(
        "--detectors",
        type=int,
        default=3,
        help="Number of detector values to parse from each outcome key (default: 3).",
    )
    return p.parse_args()


def _unwrap_object_array(value: Any) -> Any:
    if isinstance(value, np.ndarray) and value.dtype == object:
        if value.shape == ():
            return _unwrap_object_array(value.item())
        if value.size == 1:
            return _unwrap_object_array(value.reshape(()).item())
    return value


def _parse_outcome_key(raw: Any, detectors: int) -> tuple[int, ...] | None:
    if isinstance(raw, np.ndarray):
        return _parse_outcome_key(_unwrap_object_array(raw), detectors)

    if isinstance(raw, (tuple, list)):
        vals: list[int] = []
        for x in raw:
            try:
                vals.append(int(x))
            except (TypeError, ValueError):
                return None
        if len(vals) < detectors:
            return None
        return tuple(vals[:detectors])

    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if s.isdigit() and len(s) >= detectors:
            return tuple(int(ch) for ch in s[:detectors])
        nums = _INT_RE.findall(s)
        if len(nums) < detectors:
            return None
        return tuple(int(n) for n in nums[:detectors])

    return None


def _value_count(raw: Any) -> int:
    raw = _unwrap_object_array(raw)
    if isinstance(raw, np.ndarray):
        if raw.ndim == 0:
            return 1
        return int(raw.shape[0])
    if isinstance(raw, (list, tuple)):
        return len(raw)
    return 1


def _extract_s_dict(npz_data: Any) -> dict[Any, Any] | None:
    if "S" not in npz_data.files:
        return None
    raw_s = _unwrap_object_array(npz_data["S"])
    if isinstance(raw_s, dict):
        return raw_s
    if hasattr(raw_s, "item"):
        try:
            maybe = raw_s.item()
            if isinstance(maybe, dict):
                return maybe
        except (TypeError, ValueError):
            return None
    return None


def main() -> int:
    args = parse_args()
    root = Path(args.input_root)
    out = Path(args.out)
    detectors = int(args.detectors)

    if detectors <= 0:
        raise ValueError("--detectors must be > 0")
    if not root.exists():
        raise FileNotFoundError(f"Input root does not exist: {root}")

    npz_files = sorted(root.rglob("*.npz"))
    if not npz_files:
        raise FileNotFoundError(f"No .npz files found under {root}")

    counts: Counter[tuple[int, ...]] = Counter()
    files_used = 0

    for path in npz_files:
        with np.load(path, allow_pickle=True) as data:
            s_dict = _extract_s_dict(data)
            if not s_dict:
                continue
            files_used += 1
            for raw_key, raw_vals in s_dict.items():
                sample = _parse_outcome_key(raw_key, detectors)
                if sample is None:
                    continue
                n = _value_count(raw_vals)
                if n > 0:
                    counts[sample] += n

    if not counts:
        raise RuntimeError(
            "No GKP count entries parsed from NPZ data. "
            "Check that extracted files include an 'S' dictionary with outcome keys."
        )

    rows = [
        {"sample": list(sample), "count": int(count)}
        for sample, count in sorted(counts.items(), key=lambda kv: kv[0])
    ]
    payload = {
        "counts": rows,
        "metadata": {
            "source": "xanadu-gkp-data",
            "input_root": str(root.resolve()),
            "detectors": detectors,
            "npz_files_seen": len(npz_files),
            "npz_files_used": files_used,
            "unique_outcomes": len(rows),
            "total_expanded_shots": int(sum(counts.values())),
        },
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"[gkp-counts] wrote {out}")
    print(f"[gkp-counts] npz_files_seen={len(npz_files)} npz_files_used={files_used}")
    print(f"[gkp-counts] unique_outcomes={len(rows)} total_expanded_shots={sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
