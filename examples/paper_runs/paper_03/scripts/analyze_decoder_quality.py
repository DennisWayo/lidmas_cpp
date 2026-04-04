#!/usr/bin/env python3
"""Analyze replay quality: residual syndrome and logical-failure metrics."""

from __future__ import annotations

import argparse
import csv
import json
from itertools import zip_longest
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests-dir", required=True, help="Directory with decoder_requests*.ndjson.")
    p.add_argument("--responses-dir", required=True, help="Directory with decoder_responses_*_*.ndjson.")
    p.add_argument("--decoders", required=True, help="Comma-separated decoder list.")
    p.add_argument("--distance", type=int, default=5, help="Surface-code distance.")
    p.add_argument(
        "--request-glob",
        default="decoder_requests*.ndjson",
        help="Glob pattern for request files inside --requests-dir.",
    )
    p.add_argument("--out-csv", required=True, help="Output CSV path.")
    p.add_argument("--out-md", required=True, help="Output Markdown table path.")
    return p.parse_args()


def dataset_label_from_request(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("decoder_requests"):
        return stem
    suffix = stem[len("decoder_requests") :]
    if not suffix:
        return "job"
    return suffix.lstrip("_")


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


def _rate(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return float(n) / float(d)


def _h_index(x: int, y: int, d: int) -> int:
    return y * (d - 1) + x


def _v_index(x: int, y: int, d: int) -> int:
    h_count = d * (d - 1)
    return h_count + y * d + x


def _build_hx_supports(d: int) -> list[list[int]]:
    # X checks (stars) on vertices.
    supports: list[list[int]] = []
    for y in range(d):
        for x in range(d):
            row: list[int] = []
            if x > 0:
                row.append(_h_index(x - 1, y, d))
            if x < d - 1:
                row.append(_h_index(x, y, d))
            if y > 0:
                row.append(_v_index(x, y - 1, d))
            if y < d - 1:
                row.append(_v_index(x, y, d))
            supports.append(row)
    return supports


def _build_hz_supports(d: int) -> list[list[int]]:
    # Z checks (plaquettes) on faces.
    supports: list[list[int]] = []
    for y in range(d - 1):
        for x in range(d - 1):
            supports.append(
                [
                    _h_index(x, y, d),  # bottom
                    _h_index(x, y + 1, d),  # top
                    _v_index(x, y, d),  # left
                    _v_index(x + 1, y, d),  # right
                ]
            )
    return supports


def _build_logical_x_support(d: int) -> list[int]:
    n = 2 * d * (d - 1)
    support = [0] * n
    mid = d // 2
    for x in range(d):
        support[_v_index(x, mid, d)] = 1
    return support


def _build_logical_z_support(d: int) -> list[int]:
    n = 2 * d * (d - 1)
    support = [0] * n
    mid = d // 2
    for y in range(d - 1):
        support[_v_index(mid, y, d)] = 1
    return support


def _multiply_supports(supports: list[list[int]], vec: list[int]) -> list[int]:
    out: list[int] = []
    for row in supports:
        parity = 0
        for q in row:
            if 0 <= q < len(vec):
                parity ^= (vec[q] & 1)
        out.append(parity)
    return out


def _xor_binary(a: list[int], b: list[int]) -> list[int]:
    n = max(len(a), len(b))
    out = [0] * n
    for i in range(n):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        out[i] = (av ^ bv) & 1
    return out


def _dot_mod2(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    acc = 0
    for i in range(n):
        acc ^= ((a[i] & 1) & (b[i] & 1))
    return acc & 1


def _parse_json_line(line: str) -> dict[str, Any] | None:
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


def _parse_syndrome(
    request_obj: dict[str, Any], d: int
) -> tuple[list[int], list[int], bool, bool]:
    mx = d * d
    mz = (d - 1) * (d - 1)
    sx = [0] * mx
    sz = [0] * mz
    seen_x = False
    seen_z = False

    # Dense syndrome blocks.
    dense = request_obj.get("dense", [])
    if isinstance(dense, list):
        for item in dense:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type", "")).upper()
            n_bits = _safe_int(item.get("n_bits"), default=0)
            bits = item.get("bits", [])
            dest: list[int] | None
            if typ == "X":
                dest = sx
                seen_x = True
            elif typ == "Z":
                dest = sz
                seen_z = True
            else:
                dest = None
            if dest is None:
                continue

            # Bits can be [0/1] or "0101..." string.
            unpacked: list[int] = []
            if isinstance(bits, list):
                unpacked = [(_safe_int(v) & 1) for v in bits]
            elif isinstance(bits, str):
                for c in bits:
                    if c == "0":
                        unpacked.append(0)
                    elif c == "1":
                        unpacked.append(1)
            if n_bits > 0 and len(unpacked) < n_bits:
                unpacked.extend([0] * (n_bits - len(unpacked)))
            for i, bit in enumerate(unpacked):
                if i >= len(dest):
                    break
                dest[i] ^= (bit & 1)

    events = request_obj.get("events", [])
    if isinstance(events, list):
        for ev in events:
            if not isinstance(ev, dict):
                continue
            idx = _safe_int(ev.get("index"), default=-1)
            typ = str(ev.get("type", "")).upper()
            if typ == "X":
                if 0 <= idx < len(sx):
                    sx[idx] ^= 1
                    seen_x = True
            elif typ == "Z":
                if 0 <= idx < len(sz):
                    sz[idx] ^= 1
                    seen_z = True

    return sx, sz, seen_x, seen_z


def _bitmask_from_indices(indices: list[int], n: int) -> list[int]:
    out = [0] * n
    for idx in indices:
        if 0 <= idx < n:
            out[idx] ^= 1
    return out


def _extract_flips(response_obj: dict[str, Any]) -> tuple[list[int], list[int]]:
    correction = response_obj.get("correction", {})
    if not isinstance(correction, dict):
        return [], []

    def _extract(name: str) -> list[int]:
        raw = correction.get(name, [])
        if not isinstance(raw, list):
            return []
        return [_safe_int(v, default=-1) for v in raw if _safe_int(v, default=-1) >= 0]

    flips_x = _extract("qubit_flips_x")
    flips_z = _extract("qubit_flips_z")

    # Backward compatibility if only "qubit_flips" is present.
    if not flips_x and not flips_z:
        common = _extract("qubit_flips")
        flips_x = common

    return flips_x, flips_z


def _parse_indices_from_metadata(raw: Any, n: int) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [i for i in (_safe_int(v, default=-1) for v in raw) if 0 <= i < n]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [i for i in (_safe_int(v, default=-1) for v in parsed) if 0 <= i < n]
        except json.JSONDecodeError:
            pass
        vals: list[int] = []
        for tok in s.replace(";", ",").split(","):
            tok = tok.strip()
            if not tok:
                continue
            idx = _safe_int(tok, default=-1)
            if 0 <= idx < n:
                vals.append(idx)
        return vals
    return []


def _extract_ground_truth(
    request_obj: dict[str, Any], n_data: int
) -> tuple[list[int] | None, list[int] | None]:
    meta = request_obj.get("metadata", {})
    if not isinstance(meta, dict):
        return None, None

    # Preferred fields for synthetic datasets.
    has_ex_idx = "true_ex_indices" in meta
    has_ez_idx = "true_ez_indices" in meta
    ex_idx = _parse_indices_from_metadata(meta.get("true_ex_indices"), n_data)
    ez_idx = _parse_indices_from_metadata(meta.get("true_ez_indices"), n_data)
    if has_ex_idx or has_ez_idx:
        return _bitmask_from_indices(ex_idx, n_data), _bitmask_from_indices(ez_idx, n_data)

    # Optional explicit bit vectors.
    ex_bits = meta.get("true_ex_bits")
    ez_bits = meta.get("true_ez_bits")
    if isinstance(ex_bits, str) and isinstance(ez_bits, str):
        ex = [1 if c == "1" else 0 for c in ex_bits.strip() if c in {"0", "1"}]
        ez = [1 if c == "1" else 0 for c in ez_bits.strip() if c in {"0", "1"}]
        if len(ex) < n_data:
            ex.extend([0] * (n_data - len(ex)))
        if len(ez) < n_data:
            ez.extend([0] * (n_data - len(ez)))
        return ex[:n_data], ez[:n_data]

    return None, None


def _load_line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def analyze_pair(
    request_path: Path,
    response_path: Path,
    decoder: str,
    d: int,
) -> dict[str, Any]:
    n_data = 2 * d * (d - 1)
    hx_supports = _build_hx_supports(d)
    hz_supports = _build_hz_supports(d)
    logical_x = _build_logical_x_support(d)
    logical_z = _build_logical_z_support(d)

    request_lines = _load_line_count(request_path)
    response_lines = _load_line_count(response_path) if response_path.exists() else 0
    response_ratio = _rate(response_lines, request_lines)

    if not response_path.exists():
        return {
            "status": "missing_response",
            "request_lines": request_lines,
            "response_lines": response_lines,
            "response_ratio": response_ratio,
            "syndrome_eval_lines": 0,
            "syndrome_satisfied_count": 0,
            "syndrome_satisfied_rate": 0.0,
            "residual_nonzero_count": 0,
            "residual_nonzero_rate": 0.0,
            "avg_residual_sx_count": 0.0,
            "avg_residual_sz_count": 0.0,
            "logical_eval_lines": 0,
            "logical_x_fail_count": 0,
            "logical_z_fail_count": 0,
            "logical_fail_count": 0,
            "logical_x_fail_rate": 0.0,
            "logical_z_fail_rate": 0.0,
            "logical_fail_rate": 0.0,
        }

    syndrome_eval_lines = 0
    syndrome_satisfied_count = 0
    residual_nonzero_count = 0
    residual_sx_sum = 0
    residual_sz_sum = 0

    logical_eval_lines = 0
    logical_x_fail_count = 0
    logical_z_fail_count = 0
    logical_fail_count = 0

    request_parse_errors = 0
    response_parse_errors = 0

    with request_path.open("r", encoding="utf-8") as req_f, response_path.open(
        "r", encoding="utf-8"
    ) as resp_f:
        for req_line, resp_line in zip_longest(req_f, resp_f, fillvalue=""):
            req_obj = _parse_json_line(req_line)
            resp_obj = _parse_json_line(resp_line)
            if req_obj is None:
                if req_line.strip():
                    request_parse_errors += 1
                continue
            if resp_obj is None:
                if resp_line.strip():
                    response_parse_errors += 1
                continue

            sx, sz, seen_x, seen_z = _parse_syndrome(req_obj, d)
            flips_x_idx, flips_z_idx = _extract_flips(resp_obj)
            corr_x = _bitmask_from_indices(flips_x_idx, n_data)
            corr_z = _bitmask_from_indices(flips_z_idx, n_data)

            # Residual check syndromes after applying correction.
            # sx detects Z-type data errors => corrected by corr_z.
            # sz detects X-type data errors => corrected by corr_x.
            residual_sx = sx
            residual_sz = sz
            if seen_x:
                residual_sx = _xor_binary(sx, _multiply_supports(hx_supports, corr_z))
            if seen_z:
                residual_sz = _xor_binary(sz, _multiply_supports(hz_supports, corr_x))

            residual_sx_count = sum(residual_sx)
            residual_sz_count = sum(residual_sz)
            residual_total = residual_sx_count + residual_sz_count

            syndrome_eval_lines += 1
            residual_sx_sum += residual_sx_count
            residual_sz_sum += residual_sz_count
            if residual_total == 0:
                syndrome_satisfied_count += 1
            else:
                residual_nonzero_count += 1

            true_ex, true_ez = _extract_ground_truth(req_obj, n_data)
            if true_ex is not None and true_ez is not None:
                logical_eval_lines += 1
                residual_ex = _xor_binary(true_ex, corr_x)
                residual_ez = _xor_binary(true_ez, corr_z)
                logical_x_fail = (_dot_mod2(residual_ex, logical_x) != 0)
                logical_z_fail = (_dot_mod2(residual_ez, logical_z) != 0)
                if logical_x_fail:
                    logical_x_fail_count += 1
                if logical_z_fail:
                    logical_z_fail_count += 1
                if logical_x_fail or logical_z_fail:
                    logical_fail_count += 1

    status = "ok"
    if request_parse_errors > 0:
        status = "request_parse_errors"
    elif response_parse_errors > 0:
        status = "response_parse_errors"

    return {
        "status": status,
        "request_lines": request_lines,
        "response_lines": response_lines,
        "response_ratio": response_ratio,
        "syndrome_eval_lines": syndrome_eval_lines,
        "syndrome_satisfied_count": syndrome_satisfied_count,
        "syndrome_satisfied_rate": _rate(syndrome_satisfied_count, syndrome_eval_lines),
        "residual_nonzero_count": residual_nonzero_count,
        "residual_nonzero_rate": _rate(residual_nonzero_count, syndrome_eval_lines),
        "avg_residual_sx_count": _rate(residual_sx_sum, syndrome_eval_lines),
        "avg_residual_sz_count": _rate(residual_sz_sum, syndrome_eval_lines),
        "logical_eval_lines": logical_eval_lines,
        "logical_x_fail_count": logical_x_fail_count,
        "logical_z_fail_count": logical_z_fail_count,
        "logical_fail_count": logical_fail_count,
        "logical_x_fail_rate": _rate(logical_x_fail_count, logical_eval_lines),
        "logical_z_fail_rate": _rate(logical_z_fail_count, logical_eval_lines),
        "logical_fail_rate": _rate(logical_fail_count, logical_eval_lines),
    }


def _fmt_float(v: Any) -> str:
    return f"{float(v):.6f}"


def write_markdown(rows: list[dict[str, Any]], out_path: Path) -> None:
    headers = [
        "dataset",
        "decoder",
        "status",
        "response_ratio",
        "syndrome_satisfied_rate",
        "residual_nonzero_rate",
        "avg_residual_sx_count",
        "avg_residual_sz_count",
        "logical_eval_lines",
        "logical_fail_rate",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals: list[str] = []
            for h in headers:
                val = row.get(h, "")
                if h in {
                    "response_ratio",
                    "syndrome_satisfied_rate",
                    "residual_nonzero_rate",
                    "avg_residual_sx_count",
                    "avg_residual_sz_count",
                    "logical_fail_rate",
                }:
                    vals.append(_fmt_float(val))
                else:
                    vals.append(str(val))
            f.write("| " + " | ".join(vals) + " |\n")


def main() -> int:
    args = parse_args()
    decoders = [d.strip() for d in args.decoders.split(",") if d.strip()]
    requests_dir = Path(args.requests_dir)
    responses_dir = Path(args.responses_dir)

    rows: list[dict[str, Any]] = []
    for req_path in sorted(requests_dir.glob(args.request_glob)):
        dataset = dataset_label_from_request(req_path)
        for decoder in decoders:
            resp_path = responses_dir / f"decoder_responses_{dataset}_{decoder}.ndjson"
            stats = analyze_pair(req_path, resp_path, decoder, args.distance)
            row: dict[str, Any] = {
                "dataset": dataset,
                "decoder": decoder,
                "request_file": req_path.name,
                "response_file": resp_path.name,
            }
            row.update(stats)
            rows.append(row)

    fieldnames = [
        "dataset",
        "decoder",
        "status",
        "request_lines",
        "response_lines",
        "response_ratio",
        "syndrome_eval_lines",
        "syndrome_satisfied_count",
        "syndrome_satisfied_rate",
        "residual_nonzero_count",
        "residual_nonzero_rate",
        "avg_residual_sx_count",
        "avg_residual_sz_count",
        "logical_eval_lines",
        "logical_x_fail_count",
        "logical_x_fail_rate",
        "logical_z_fail_count",
        "logical_z_fail_rate",
        "logical_fail_count",
        "logical_fail_rate",
        "request_file",
        "response_file",
    ]

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_out = dict(row)
            for key in {
                "response_ratio",
                "syndrome_satisfied_rate",
                "residual_nonzero_rate",
                "avg_residual_sx_count",
                "avg_residual_sz_count",
                "logical_x_fail_rate",
                "logical_z_fail_rate",
                "logical_fail_rate",
            }:
                row_out[key] = _fmt_float(row_out.get(key, 0.0))
            writer.writerow(row_out)

    write_markdown(rows, Path(args.out_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
