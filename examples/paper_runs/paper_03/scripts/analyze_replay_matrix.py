#!/usr/bin/env python3
"""Analyze decoder_io replay request/response matrices and emit summary tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests-dir", required=True, help="Directory with decoder_requests*.ndjson.")
    parser.add_argument("--responses-dir", required=True, help="Directory with decoder_responses_*_*.ndjson.")
    parser.add_argument("--decoders", required=True, help="Comma-separated decoder list.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--out-md", required=True, help="Output Markdown table path.")
    return parser.parse_args()


def dataset_label_from_request(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("decoder_requests"):
        return stem
    suffix = stem[len("decoder_requests") :]
    if not suffix:
        return "job"
    return suffix.lstrip("_")


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def request_stats(path: Path) -> dict[str, Any]:
    line_count = 0
    parse_errors = 0
    event_sum = 0
    nonempty_events = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            line_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            events = obj.get("events", [])
            if isinstance(events, list):
                event_count = len(events)
            else:
                event_count = 0
            event_sum += event_count
            if event_count > 0:
                nonempty_events += 1

    return {
        "request_lines": line_count,
        "request_parse_errors": parse_errors,
        "avg_request_events": _rate(event_sum, line_count),
        "nonempty_request_event_rate": _rate(nonempty_events, line_count),
    }


def response_stats(path: Path, expected_decoder: str) -> dict[str, Any]:
    line_count = 0
    parse_errors = 0
    warning_no_syndrome = 0
    error_count = 0
    sx_sum = 0
    sz_sum = 0
    flip_sum = 0
    nonempty_flips = 0
    unique_flip_qubits: set[int] = set()
    decoder_name_mismatch = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            line_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            diagnostics = obj.get("diagnostics", {})
            if isinstance(diagnostics, dict):
                if diagnostics.get("warning") == "no_syndrome_bits":
                    warning_no_syndrome += 1
                if "error" in diagnostics:
                    error_count += 1
                sx_sum += _safe_int(diagnostics.get("sx_count"), default=0)
                sz_sum += _safe_int(diagnostics.get("sz_count"), default=0)

            correction = obj.get("correction", {})
            if not isinstance(correction, dict):
                correction = {}

            decoder_name = str(correction.get("decoder_name", "")).strip()
            if decoder_name and decoder_name != expected_decoder:
                decoder_name_mismatch += 1

            flips = correction.get("qubit_flips", [])
            if not isinstance(flips, list):
                flips = []
            flip_count = len(flips)
            flip_sum += flip_count
            if flip_count > 0:
                nonempty_flips += 1
            for qubit in flips:
                unique_flip_qubits.add(_safe_int(qubit))

    return {
        "response_lines": line_count,
        "response_parse_errors": parse_errors,
        "warning_no_syndrome_count": warning_no_syndrome,
        "warning_no_syndrome_rate": _rate(warning_no_syndrome, line_count),
        "error_count": error_count,
        "avg_sx_count": _rate(sx_sum, line_count),
        "avg_sz_count": _rate(sz_sum, line_count),
        "avg_flip_count": _rate(flip_sum, line_count),
        "nonempty_flip_rate": _rate(nonempty_flips, line_count),
        "unique_flip_qubits": len(unique_flip_qubits),
        "decoder_name_mismatch_count": decoder_name_mismatch,
    }


def fmt_float(value: Any) -> str:
    return f"{float(value):.6f}"


def write_markdown(rows: list[dict[str, Any]], out_path: Path) -> None:
    headers = [
        "dataset",
        "decoder",
        "status",
        "request_lines",
        "response_lines",
        "response_ratio",
        "warning_no_syndrome_rate",
        "avg_flip_count",
        "nonempty_flip_rate",
        "error_count",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            values: list[str] = []
            for key in headers:
                val = row.get(key, "")
                if key in {
                    "response_ratio",
                    "warning_no_syndrome_rate",
                    "avg_flip_count",
                    "nonempty_flip_rate",
                } and val != "":
                    values.append(fmt_float(val))
                else:
                    values.append(str(val))
            f.write("| " + " | ".join(values) + " |\n")


def main() -> int:
    args = parse_args()
    requests_dir = Path(args.requests_dir)
    responses_dir = Path(args.responses_dir)
    decoders = [d.strip() for d in args.decoders.split(",") if d.strip()]

    rows: list[dict[str, Any]] = []
    request_files = sorted(requests_dir.glob("decoder_requests*.ndjson"))

    for req_path in request_files:
        dataset = dataset_label_from_request(req_path)
        req_stats = request_stats(req_path)

        for decoder in decoders:
            row: dict[str, Any] = {
                "dataset": dataset,
                "decoder": decoder,
                "status": "ok",
                **req_stats,
                "request_file": req_path.name,
            }

            resp_path = responses_dir / f"decoder_responses_{dataset}_{decoder}.ndjson"
            row["response_file"] = resp_path.name
            if not resp_path.exists():
                row.update(
                    {
                        "status": "missing_response",
                        "response_lines": 0,
                        "response_parse_errors": 0,
                        "response_ratio": 0.0,
                        "warning_no_syndrome_count": 0,
                        "warning_no_syndrome_rate": 0.0,
                        "error_count": 0,
                        "avg_sx_count": 0.0,
                        "avg_sz_count": 0.0,
                        "avg_flip_count": 0.0,
                        "nonempty_flip_rate": 0.0,
                        "unique_flip_qubits": 0,
                        "decoder_name_mismatch_count": 0,
                    }
                )
                rows.append(row)
                continue

            resp_stats = response_stats(resp_path, expected_decoder=decoder)
            row.update(resp_stats)
            row["response_ratio"] = _rate(row["response_lines"], row["request_lines"])
            if row["response_parse_errors"] > 0:
                row["status"] = "response_parse_errors"
            rows.append(row)

    fieldnames = [
        "dataset",
        "decoder",
        "status",
        "request_lines",
        "request_parse_errors",
        "response_lines",
        "response_parse_errors",
        "response_ratio",
        "avg_request_events",
        "nonempty_request_event_rate",
        "warning_no_syndrome_count",
        "warning_no_syndrome_rate",
        "error_count",
        "avg_sx_count",
        "avg_sz_count",
        "avg_flip_count",
        "nonempty_flip_rate",
        "unique_flip_qubits",
        "decoder_name_mismatch_count",
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
                "avg_request_events",
                "nonempty_request_event_rate",
                "warning_no_syndrome_rate",
                "avg_sx_count",
                "avg_sz_count",
                "avg_flip_count",
                "nonempty_flip_rate",
            }:
                row_out[key] = fmt_float(row_out.get(key, 0.0))
            writer.writerow(row_out)

    write_markdown(rows, Path(args.out_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
