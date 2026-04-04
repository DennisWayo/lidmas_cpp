#!/usr/bin/env python3
"""Input loading utilities for paper_03 extended analysis."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ReplaySource:
    scope: str
    manifest_path: Path


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


def _read_nonempty_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                out.append(line)
    return out


def _request_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, line in enumerate(_read_nonempty_lines(path)):
        rec: dict[str, Any] = {
            "line_index": idx,
            "request_parse_ok": False,
            "request_event_count": 0,
            "request_nonempty_event": 0,
        }
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            records.append(rec)
            continue
        if not isinstance(obj, dict):
            records.append(rec)
            continue
        events = obj.get("events", [])
        event_count = len(events) if isinstance(events, list) else 0
        rec["request_parse_ok"] = True
        rec["request_event_count"] = event_count
        rec["request_nonempty_event"] = int(event_count > 0)
        records.append(rec)
    return records


def _response_records(path: Path, expected_decoder: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, line in enumerate(_read_nonempty_lines(path)):
        rec: dict[str, Any] = {
            "line_index": idx,
            "response_parse_ok": False,
            "warning_no_syndrome": 0,
            "error_present": 0,
            "sx_count": 0,
            "sz_count": 0,
            "flip_count": 0,
            "nonempty_flip": 0,
            "decoder_name_mismatch": 0,
            "unique_flip_qubits": [],
        }
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            records.append(rec)
            continue
        if not isinstance(obj, dict):
            records.append(rec)
            continue

        rec["response_parse_ok"] = True
        diagnostics = obj.get("diagnostics", {})
        if isinstance(diagnostics, dict):
            rec["warning_no_syndrome"] = int(diagnostics.get("warning") == "no_syndrome_bits")
            rec["error_present"] = int("error" in diagnostics)
            rec["sx_count"] = _safe_int(diagnostics.get("sx_count"), default=0)
            rec["sz_count"] = _safe_int(diagnostics.get("sz_count"), default=0)

        correction = obj.get("correction", {})
        if not isinstance(correction, dict):
            correction = {}

        decoder_name = str(correction.get("decoder_name", "")).strip()
        rec["decoder_name_mismatch"] = int(bool(decoder_name) and decoder_name != expected_decoder)

        flips = correction.get("qubit_flips", [])
        if not isinstance(flips, list):
            flips = []
        flip_count = len(flips)
        rec["flip_count"] = flip_count
        rec["nonempty_flip"] = int(flip_count > 0)
        rec["unique_flip_qubits"] = [_safe_int(q, default=-1) for q in flips if _safe_int(q, default=-1) >= 0]
        records.append(rec)
    return records


def _aggregate_pair_stats(
    dataset: str,
    decoder: str,
    scope: str,
    request_file: str,
    response_file: str,
    request_records: list[dict[str, Any]],
    response_records: list[dict[str, Any]],
    request_exists: bool,
    response_exists: bool,
) -> dict[str, Any]:
    request_lines = len(request_records)
    response_lines = len(response_records)
    req_parse_errors = sum(0 if r["request_parse_ok"] else 1 for r in request_records)
    resp_parse_errors = sum(0 if r["response_parse_ok"] else 1 for r in response_records)

    event_sum = sum(int(r["request_event_count"]) for r in request_records)
    nonempty_req = sum(int(r["request_nonempty_event"]) for r in request_records)

    warning_count = sum(int(r["warning_no_syndrome"]) for r in response_records if r["response_parse_ok"])
    error_count = sum(int(r["error_present"]) for r in response_records if r["response_parse_ok"])
    sx_sum = sum(int(r["sx_count"]) for r in response_records if r["response_parse_ok"])
    sz_sum = sum(int(r["sz_count"]) for r in response_records if r["response_parse_ok"])
    flip_sum = sum(int(r["flip_count"]) for r in response_records if r["response_parse_ok"])
    nonempty_flip = sum(int(r["nonempty_flip"]) for r in response_records if r["response_parse_ok"])
    decoder_mismatch = sum(int(r["decoder_name_mismatch"]) for r in response_records if r["response_parse_ok"])

    unique_qubits: set[int] = set()
    for rec in response_records:
        for q in rec.get("unique_flip_qubits", []):
            if q >= 0:
                unique_qubits.add(int(q))

    status = "ok"
    if not request_exists:
        status = "missing_request"
    elif not response_exists:
        status = "missing_response"
    elif req_parse_errors > 0:
        status = "request_parse_errors"
    elif resp_parse_errors > 0:
        status = "response_parse_errors"

    return {
        "scope": scope,
        "dataset": dataset,
        "decoder": decoder,
        "status": status,
        "request_lines": request_lines,
        "request_parse_errors": req_parse_errors,
        "response_lines": response_lines,
        "response_parse_errors": resp_parse_errors,
        "response_ratio": _rate(response_lines, request_lines),
        "avg_request_events": _rate(event_sum, request_lines),
        "nonempty_request_event_rate": _rate(nonempty_req, request_lines),
        "warning_no_syndrome_count": warning_count,
        "warning_no_syndrome_rate": _rate(warning_count, response_lines),
        "error_count": error_count,
        "avg_sx_count": _rate(sx_sum, response_lines),
        "avg_sz_count": _rate(sz_sum, response_lines),
        "avg_flip_count": _rate(flip_sum, response_lines),
        "nonempty_flip_rate": _rate(nonempty_flip, response_lines),
        "unique_flip_qubits": len(unique_qubits),
        "decoder_name_mismatch_count": decoder_mismatch,
        "request_file": request_file,
        "response_file": response_file,
    }


def _request_level_rows(
    scope: str,
    dataset: str,
    decoder: str,
    request_records: list[dict[str, Any]],
    response_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, (req, resp) in enumerate(zip_longest(request_records, response_records, fillvalue=None)):
        req_rec = req or {
            "request_parse_ok": False,
            "request_event_count": 0,
            "request_nonempty_event": 0,
        }
        resp_rec = resp or {
            "response_parse_ok": False,
            "warning_no_syndrome": 0,
            "flip_count": 0,
            "nonempty_flip": 0,
        }
        rows.append(
            {
                "scope": scope,
                "dataset": dataset,
                "decoder": decoder,
                "line_index": idx,
                "request_parse_ok": int(req_rec.get("request_parse_ok", False)),
                "response_parse_ok": int(resp_rec.get("response_parse_ok", False)),
                "request_event_count": int(req_rec.get("request_event_count", 0)),
                "request_nonempty_event": int(req_rec.get("request_nonempty_event", 0)),
                "warning_no_syndrome": int(resp_rec.get("warning_no_syndrome", 0)),
                "flip_count": int(resp_rec.get("flip_count", 0)),
                "nonempty_flip": int(resp_rec.get("nonempty_flip", 0)),
            }
        )
    return rows


def _classify_scope(manifest_path: Path) -> str:
    name = manifest_path.parent.name.lower()
    if "replay_decoder_matrix" in name:
        return "fixture"
    if "real_data_slice" in name:
        return "real_slice"
    if "synthetic_holdout" in name:
        return "synthetic_holdout"
    if "real_data_full" in name:
        return "real_full_hpc"
    return name


def discover_replay_sources(results_root: Path) -> list[ReplaySource]:
    manifests = sorted(results_root.glob("**/replay_manifest.csv"))
    out: list[ReplaySource] = []
    for manifest in manifests:
        scope = _classify_scope(manifest)
        out.append(ReplaySource(scope=scope, manifest_path=manifest))
    return out


def load_replay_data(results_root: Path, logger: logging.Logger) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sources = discover_replay_sources(results_root)
    if not sources:
        logger.warning("No replay manifests found under %s", results_root)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    request_cache: dict[Path, list[dict[str, Any]]] = {}
    response_cache: dict[tuple[Path, str], list[dict[str, Any]]] = {}

    matrix_rows: list[dict[str, Any]] = []
    request_level_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []

    for source in sources:
        with source.manifest_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dataset = str(row.get("dataset", "")).strip()
                decoder = str(row.get("decoder", "")).strip()
                request_file = str(row.get("request_file", "")).strip()
                response_file = str(row.get("response_file", "")).strip()
                if not dataset or not decoder or not request_file or not response_file:
                    logger.warning(
                        "Skipping malformed manifest row in %s: %s",
                        source.manifest_path,
                        row,
                    )
                    continue

                request_path = source.manifest_path.parent / request_file
                response_path = source.manifest_path.parent / response_file
                request_exists = request_path.exists()
                response_exists = response_path.exists()

                req_records = request_cache.get(request_path)
                if req_records is None:
                    req_records = _request_records(request_path) if request_exists else []
                    request_cache[request_path] = req_records

                resp_key = (response_path, decoder)
                resp_records = response_cache.get(resp_key)
                if resp_records is None:
                    resp_records = _response_records(response_path, expected_decoder=decoder) if response_exists else []
                    response_cache[resp_key] = resp_records

                matrix_rows.append(
                    _aggregate_pair_stats(
                        dataset=dataset,
                        decoder=decoder,
                        scope=source.scope,
                        request_file=request_file,
                        response_file=response_file,
                        request_records=req_records,
                        response_records=resp_records,
                        request_exists=request_exists,
                        response_exists=response_exists,
                    )
                )

                request_level_rows.extend(
                    _request_level_rows(
                        scope=source.scope,
                        dataset=dataset,
                        decoder=decoder,
                        request_records=req_records,
                        response_records=resp_records,
                    )
                )
                manifest_rows.append(
                    {
                        "scope": source.scope,
                        "manifest_path": str(source.manifest_path),
                        "dataset": dataset,
                        "decoder": decoder,
                        "request_file": request_file,
                        "response_file": response_file,
                    }
                )

    matrix_df = pd.DataFrame(matrix_rows)
    request_df = pd.DataFrame(request_level_rows)
    manifest_df = pd.DataFrame(manifest_rows)
    return matrix_df, request_df, manifest_df


def _scope_from_quality_filename(path: Path) -> str:
    name = path.name.lower()
    if "fixture_quality" in name:
        return "fixture"
    if "real_quality" in name:
        return "real_slice"
    if "synthetic_heldout_quality" in name:
        return "synthetic_holdout"
    if "full_data_quality" in name:
        return "real_full_hpc"
    return path.stem.replace("table_", "").replace("_quality", "")


def load_quality_data(results_root: Path, logger: logging.Logger) -> pd.DataFrame:
    candidates = sorted(results_root.glob("**/table_*quality.csv"))
    if not candidates:
        logger.warning("No quality CSV tables found under %s", results_root)
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for path in candidates:
        try:
            df = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read quality table %s: %s", path, exc)
            continue
        df["scope"] = _scope_from_quality_filename(path)
        df["source_quality_table"] = str(path)
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
