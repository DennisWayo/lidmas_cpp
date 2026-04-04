#!/usr/bin/env python3
"""Convert Xanadu datasets into LiDMaS+ decoder_io NDJSON."""

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
_SOURCE_FORMATS = (
    "auto",
    "xanadu_job_json",
    "shot_matrix",
    "aurora_switch_dir",
    "count_table_json",
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "NumPy is required for .npy/.npz inputs. Install it with: pip install numpy"
        ) from exc
    return np


def _load_numpy_array(path: Path, array_key: str, mmap_mode: str | None) -> Any:
    np = _require_numpy()
    obj = np.load(path, allow_pickle=False, mmap_mode=mmap_mode)

    if hasattr(obj, "files"):
        files = list(getattr(obj, "files"))
        if not files:
            raise ValueError(f"{path}: .npz file has no arrays.")
        key = array_key or files[0]
        if key not in files:
            raise ValueError(f"{path}: key {key!r} not found in .npz file. Keys: {files}.")
        arr = obj[key]
        obj.close()
        return arr

    return obj


def _extract_samples_from_job_payload(payload: Any) -> list[Any]:
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
            if all(not isinstance(x, (list, dict)) for x in cand):
                return [cand]
            return cand
    raise ValueError(
        "Could not locate sample list in input JSON. Expected one of: "
        "output, samples, result.output, result.samples, data.output, data.samples."
    )


def _extract_samples_from_shot_matrix(payload: Any, array_key: str) -> Any:
    if isinstance(payload, dict):
        candidates: list[Any] = []
        if array_key:
            candidates.append(payload.get(array_key))
        candidates.extend(
            [
                payload.get("samples"),
                payload.get("output"),
                payload.get("shots"),
                payload.get("data"),
            ]
        )
        for cand in candidates:
            if isinstance(cand, list):
                payload = cand
                break
        else:
            raise ValueError(
                "Could not locate shot list in shot-matrix input. "
                "Provide --array-key or one of keys: samples, output, shots, data."
            )

    if isinstance(payload, list):
        if not payload:
            return []
        if all(not isinstance(x, (list, dict)) for x in payload):
            return [payload]
        return payload

    if hasattr(payload, "shape") and hasattr(payload, "ndim"):
        return payload

    raise ValueError(
        f"Shot-matrix payload must be list/object/array; got {type(payload).__name__}."
    )


def _normalize_shot(shot: Any, shot_index: int) -> list[int]:
    if isinstance(shot, dict):
        if "output" in shot:
            shot = shot["output"]
        elif "samples" in shot:
            shot = shot["samples"]
        elif "sample" in shot:
            shot = shot["sample"]
        elif "outcome" in shot:
            shot = shot["outcome"]
        else:
            raise ValueError(
                f"Shot {shot_index}: dict shot does not contain output/samples/sample/outcome."
            )

    if hasattr(shot, "tolist") and not isinstance(shot, (list, tuple)):
        shot = shot.tolist()

    if isinstance(shot, tuple):
        shot = list(shot)

    while isinstance(shot, list) and len(shot) == 1 and isinstance(shot[0], (list, tuple)):
        shot = list(shot[0])

    if not isinstance(shot, list):
        raise ValueError(f"Shot {shot_index}: expected list, got {type(shot).__name__}.")

    out: list[int] = []
    for i, v in enumerate(shot):
        while isinstance(v, (list, tuple)) and len(v) == 1:
            v = v[0]
        if hasattr(v, "tolist") and not isinstance(v, (list, tuple, dict)):
            maybe_list = v.tolist()
            if isinstance(maybe_list, (list, tuple, dict)):
                v = maybe_list
        if isinstance(v, (list, tuple, dict)):
            raise ValueError(
                f"Shot {shot_index}, mode {i}: nested element found; expected scalar integer-like values."
            )
        try:
            iv = int(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Shot {shot_index}, mode {i}: value {v!r} is not integer-convertible.") from exc
        if iv < 0:
            raise ValueError(f"Shot {shot_index}, mode {i}: value {iv} is negative.")
        out.append(iv)
    return out


class _IntSequence:
    def __init__(self, raw: Any, name: str):
        self.name = name
        self.raw = raw
        self.kind = ""
        self.length = 0

        if isinstance(raw, tuple):
            raw = list(raw)
            self.raw = raw

        if isinstance(raw, list):
            if not raw:
                self.kind = "list1d"
                self.length = 0
                return
            if all(isinstance(x, (list, tuple)) and len(x) == 1 for x in raw):
                self.kind = "list_n1"
                self.length = len(raw)
                return
            if len(raw) == 1 and isinstance(raw[0], (list, tuple)):
                self.kind = "list_1n"
                self.length = len(raw[0])
                return
            if any(isinstance(x, (list, tuple, dict)) for x in raw):
                raise ValueError(
                    f"{name}: expected 1D numeric sequence, got nested data. "
                    "Provide 1D arrays for Aurora switch settings."
                )
            self.kind = "list1d"
            self.length = len(raw)
            return

        if hasattr(raw, "shape") and hasattr(raw, "ndim"):
            ndim = int(raw.ndim)
            if ndim == 1:
                self.kind = "arr1d"
                self.length = int(raw.shape[0])
                return
            if ndim == 2 and int(raw.shape[1]) == 1:
                self.kind = "arr_n1"
                self.length = int(raw.shape[0])
                return
            if ndim == 2 and int(raw.shape[0]) == 1:
                self.kind = "arr_1n"
                self.length = int(raw.shape[1])
                return
            raise ValueError(
                f"{name}: expected 1D sequence or shape (N,1)/(1,N), got shape {tuple(raw.shape)}."
            )

        raise ValueError(f"{name}: expected array/list, got {type(raw).__name__}.")

    def value(self, i: int) -> int:
        if self.kind == "list1d":
            return int(self.raw[i])
        if self.kind == "list_n1":
            return int(self.raw[i][0])
        if self.kind == "list_1n":
            return int(self.raw[0][i])
        if self.kind == "arr1d":
            return int(self.raw[i])
        if self.kind == "arr_n1":
            return int(self.raw[i, 0])
        if self.kind == "arr_1n":
            return int(self.raw[0, i])
        raise ValueError(f"Unsupported internal sequence kind {self.kind!r}.")


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
        description="Convert Xanadu hardware-style data to LiDMaS+ decoder_io NDJSON."
    )
    p.add_argument("--input", required=True, help="Input path (JSON/NPY/NPZ file or Aurora batch directory).")
    p.add_argument(
        "--source-format",
        choices=_SOURCE_FORMATS,
        default="auto",
        help=(
            "Input interpretation. "
            "auto: infer from path; "
            "xanadu_job_json: job payload with output/samples; "
            "shot_matrix: generic shot matrix (.json/.npy/.npz); "
            "aurora_switch_dir: Aurora decoder_demo batch dir with switch_settings_qpu_*.{npy,json}; "
            "count_table_json: JSON counts table with sample+count entries."
        ),
    )
    p.add_argument("--mapping", required=True, help="Path to syndrome mapping JSON.")
    p.add_argument("--out", required=True, help="Output NDJSON path.")
    p.add_argument(
        "--append-out",
        action="store_true",
        help="Append to output NDJSON instead of overwriting.",
    )
    p.add_argument(
        "--array-key",
        default="",
        help="Optional array key for dict/npz inputs (e.g., 'samples').",
    )
    p.add_argument(
        "--stream",
        action="store_true",
        help="Stream large inputs when possible (recommended for large .npy files).",
    )
    p.add_argument(
        "--shot-start",
        type=int,
        default=0,
        help="Skip the first N expanded shots before conversion.",
    )
    p.add_argument(
        "--aurora-qpu-count",
        type=int,
        default=6,
        help="Number of Aurora qpu switch-setting files to read in aurora_switch_dir mode.",
    )
    p.add_argument(
        "--aurora-binarize",
        action="store_true",
        help="Map non-zero Aurora switch settings to 1 (keep 0 as 0).",
    )
    p.add_argument("--max-shots", type=int, default=0, help="Optional cap on output shots (0 = all).")
    p.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Print progress every N written lines (0 disables).",
    )
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
    p.add_argument(
        "--count-table-no-expand",
        action="store_true",
        help=(
            "In count_table_json mode, emit one request per table row and store "
            "the expanded multiplicity in metadata.repeat_count instead of fully expanding counts."
        ),
    )
    return p


def _resolve_source_format(source_format: str, input_path: Path, payload: Any) -> str:
    if source_format != "auto":
        return source_format

    if input_path.is_dir():
        return "aurora_switch_dir"

    suffix = input_path.suffix.lower()
    if suffix in (".npy", ".npz"):
        return "shot_matrix"

    if suffix == ".json":
        if isinstance(payload, dict):
            if any(k in payload for k in ("counts", "histogram", "entries")):
                return "count_table_json"
            if "shots" in payload and "output" not in payload and "samples" not in payload:
                return "shot_matrix"
            return "xanadu_job_json"
        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                keys = set(payload[0].keys())
                if any(k in keys for k in ("count", "n", "freq")) and any(
                    k in keys for k in ("sample", "outcome", "shot", "modes")
                ):
                    return "count_table_json"
            return "shot_matrix"

    return "shot_matrix"


def _get_source_payload(input_path: Path, source_format: str, array_key: str, stream: bool) -> Any:
    suffix = input_path.suffix.lower()

    if source_format == "xanadu_job_json":
        return _load_json(input_path)

    if source_format == "count_table_json":
        return _load_json(input_path)

    if source_format == "shot_matrix":
        if suffix == ".json":
            return _load_json(input_path)
        if suffix in (".npy", ".npz"):
            mmap_mode = "r" if (stream and suffix == ".npy") else None
            return _load_numpy_array(input_path, array_key, mmap_mode=mmap_mode)
        raise ValueError(
            f"Unsupported shot-matrix input extension {suffix!r}. Use .json, .npy, or .npz."
        )

    return {}


def _iter_job_shots(payload: Any, shot_start: int, max_shots: int):
    shots = _extract_samples_from_job_payload(payload)
    total = len(shots)
    start = min(shot_start, total)
    end = total if max_shots <= 0 else min(total, start + max_shots)
    for idx in range(start, end):
        yield idx, shots[idx], 1


def _iter_shot_matrix(payload: Any, array_key: str, shot_start: int, max_shots: int):
    data = _extract_samples_from_shot_matrix(payload, array_key)

    if isinstance(data, list):
        total = len(data)
        start = min(shot_start, total)
        end = total if max_shots <= 0 else min(total, start + max_shots)
        for idx in range(start, end):
            yield idx, data[idx], 1
        return

    if hasattr(data, "ndim") and hasattr(data, "shape"):
        ndim = int(data.ndim)
        if ndim == 0:
            raise ValueError("shot_matrix array must have at least 1 dimension.")
        total = 1 if ndim == 1 else int(data.shape[0])
        start = min(shot_start, total)
        end = total if max_shots <= 0 else min(total, start + max_shots)
        for idx in range(start, end):
            if ndim == 1:
                yield idx, data, 1
            else:
                yield idx, data[idx], 1
        return

    raise ValueError(f"Unsupported shot_matrix container type: {type(data).__name__}")


def _iter_count_table(payload: Any, shot_start: int, max_shots: int, expand_counts: bool):
    table = payload
    if isinstance(payload, dict):
        table = payload.get("counts", payload.get("histogram", payload.get("entries")))
    if not isinstance(table, list):
        raise ValueError(
            "Count-table input must be a list or an object with one of keys: counts, histogram, entries."
        )

    target_end = None if max_shots <= 0 else shot_start + max_shots
    expanded_cursor = 0

    for i, entry in enumerate(table):
        if not isinstance(entry, dict):
            raise ValueError(f"Count-table entry {i}: expected object.")

        shot_raw = entry.get("sample", entry.get("outcome", entry.get("shot", entry.get("modes"))))
        if shot_raw is None:
            raise ValueError(
                f"Count-table entry {i}: missing sample vector. Expected key sample/outcome/shot/modes."
            )

        count_raw = entry.get("count", entry.get("n", entry.get("freq", 1)))
        try:
            count = int(count_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Count-table entry {i}: invalid count {count_raw!r}.") from exc
        if count <= 0:
            continue

        block_start = expanded_cursor
        block_end = expanded_cursor + count
        expanded_cursor = block_end

        take_start = max(block_start, shot_start)
        take_end = block_end
        if target_end is not None:
            take_end = min(take_end, target_end)

        if take_start >= take_end:
            continue

        shot_norm = _normalize_shot(shot_raw, i)
        if expand_counts:
            for global_idx in range(take_start, take_end):
                yield global_idx, shot_norm, 1
        else:
            repeat_count = take_end - take_start
            if repeat_count > 0:
                # Preserve expanded index semantics by using the first expanded index.
                yield take_start, shot_norm, repeat_count

        if target_end is not None and expanded_cursor >= target_end:
            return


def _iter_aurora_switch_dir(
    batch_dir: Path,
    qpu_count: int,
    array_key: str,
    stream: bool,
    binarize: bool,
    shot_start: int,
    max_shots: int,
):
    if not batch_dir.is_dir():
        raise ValueError(
            "Aurora switch mode expects --input to be a directory containing "
            "switch_settings_qpu_{0..N}.npy or .json files."
        )
    if qpu_count <= 0:
        raise ValueError("aurora_qpu_count must be > 0.")

    columns: list[_IntSequence] = []
    for qpu in range(qpu_count):
        npy_path = batch_dir / f"switch_settings_qpu_{qpu}.npy"
        json_path = batch_dir / f"switch_settings_qpu_{qpu}.json"
        if npy_path.exists():
            raw = _load_numpy_array(npy_path, array_key, mmap_mode="r" if stream else None)
        elif json_path.exists():
            raw = _load_json(json_path)
        else:
            raise ValueError(
                f"Missing Aurora switch file for qpu {qpu}: "
                f"expected {npy_path.name} or {json_path.name} in {batch_dir}."
            )
        columns.append(_IntSequence(raw, str(npy_path if npy_path.exists() else json_path)))

    n_bins = columns[0].length
    for qpu, seq in enumerate(columns):
        if seq.length != n_bins:
            raise ValueError(
                f"Aurora switch length mismatch: qpu0 has {n_bins}, qpu{qpu} has {seq.length}."
            )

    start = min(shot_start, n_bins)
    end = n_bins if max_shots <= 0 else min(n_bins, start + max_shots)

    for idx in range(start, end):
        shot: list[int] = []
        for col in columns:
            v = col.value(idx)
            shot.append(0 if (binarize and v == 0) else (1 if binarize else v))
        yield idx, shot, 1


def _compile_stabilizers(stabilizers: Any) -> list[tuple[int, str, list[int], int, int, int]]:
    if not isinstance(stabilizers, list):
        raise ValueError("Mapping JSON must contain list field 'stabilizers'.")
    compiled: list[tuple[int, str, list[int], int, int, int]] = []
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
        compiled.append((stab_index, stab_type, modes, mod, trigger_on, time_offset_ns))
    return compiled


def _iter_source_shots(args: argparse.Namespace, input_path: Path, source_format: str, payload: Any):
    shot_start = max(0, int(args.shot_start))
    max_shots = int(args.max_shots)

    if source_format == "xanadu_job_json":
        yield from _iter_job_shots(payload, shot_start=shot_start, max_shots=max_shots)
        return

    if source_format == "shot_matrix":
        yield from _iter_shot_matrix(payload, array_key=args.array_key, shot_start=shot_start, max_shots=max_shots)
        return

    if source_format == "aurora_switch_dir":
        yield from _iter_aurora_switch_dir(
            input_path,
            qpu_count=args.aurora_qpu_count,
            array_key=args.array_key,
            stream=args.stream,
            binarize=args.aurora_binarize,
            shot_start=shot_start,
            max_shots=max_shots,
        )
        return

    if source_format == "count_table_json":
        yield from _iter_count_table(
            payload,
            shot_start=shot_start,
            max_shots=max_shots,
            expand_counts=not args.count_table_no_expand,
        )
        return

    raise ValueError(f"Unsupported source format: {source_format}")


def main() -> int:
    args = _build_parser().parse_args()

    if args.shot_start < 0:
        raise ValueError("--shot-start must be >= 0.")
    if args.max_shots < 0:
        raise ValueError("--max-shots must be >= 0.")
    if args.progress_every < 0:
        raise ValueError("--progress-every must be >= 0.")

    in_path = Path(args.input)
    map_path = Path(args.mapping)
    out_path = Path(args.out)

    payload_for_detect: Any = None
    if not in_path.is_dir() and in_path.suffix.lower() == ".json":
        payload_for_detect = _load_json(in_path)

    source_format = _resolve_source_format(args.source_format, in_path, payload_for_detect)
    payload = _get_source_payload(in_path, source_format, args.array_key, args.stream)

    mapping = _load_json(map_path)
    if not isinstance(mapping, dict):
        raise ValueError("Mapping JSON must be an object.")

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

    stabilizers_compiled = _compile_stabilizers(mapping.get("stabilizers"))

    base_meta: dict[str, str] = {}
    mapping_meta = mapping.get("metadata", {})
    if isinstance(mapping_meta, dict):
        for k, v in mapping_meta.items():
            base_meta[str(k)] = str(v)
    base_meta.update(_parse_meta_pairs(args.meta))
    if "source_format" not in base_meta:
        base_meta["source_format"] = source_format
    if args.shot_start > 0 and "shot_start" not in base_meta:
        base_meta["shot_start"] = str(args.shot_start)
    if args.stream and "stream" not in base_meta:
        base_meta["stream"] = "1"

    jid = _job_identifier(payload)
    if jid and "job_id" not in base_meta:
        base_meta["job_id"] = jid

    loss_list = _parse_loss_list(args.loss_prob_by_qubit)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_mode = "a" if args.append_out else "w"

    wrote = 0
    expanded_wrote = 0
    next_progress = args.progress_every if args.progress_every > 0 else 0
    with out_path.open(out_mode, encoding="utf-8") as f:
        for global_idx, shot_raw, repeat_count in _iter_source_shots(args, in_path, source_format, payload):
            shot = _normalize_shot(shot_raw, global_idx)
            events: list[dict[str, Any]] = []
            shot_time = time_ns_start + global_idx * time_ns_stride

            for stab_index, stab_type, modes, mod, trigger_on, time_offset_ns in stabilizers_compiled:
                parity_sum = 0
                for m in modes:
                    if m >= len(shot):
                        raise ValueError(
                            f"Shot {global_idx}: mode index {m} out of range for shot width {len(shot)}."
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
                "round_index": round_start + global_idx * round_stride,
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
            req["metadata"]["shot_index"] = str(global_idx)
            if repeat_count > 1:
                req["metadata"]["repeat_count"] = str(repeat_count)
            f.write(json.dumps(req, separators=(",", ":")) + "\n")
            wrote += 1
            expanded_wrote += repeat_count

            if args.progress_every > 0 and expanded_wrote >= next_progress:
                while next_progress <= expanded_wrote:
                    next_progress += args.progress_every
                print(f"progress: wrote={expanded_wrote} latest_shot_index={global_idx}", file=sys.stderr)

    if wrote == expanded_wrote:
        print(f"Wrote {wrote} DecodeRequest lines to {out_path}")
    else:
        print(
            f"Wrote {wrote} DecodeRequest lines to {out_path} "
            f"(expanded_shots={expanded_wrote})"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
