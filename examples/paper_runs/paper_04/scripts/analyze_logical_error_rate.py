#!/usr/bin/env python3
"""Compute outer-code logical-parity error rates for paper_04 replay outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-dir", required=True, help="Directory containing truth_*.ndjson sidecars.")
    parser.add_argument("--replay-manifest", required=True, help="Replay manifest CSV.")
    parser.add_argument("--responses-dir", required=True, help="Directory containing decoder responses.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--out-md", required=True, help="Output Markdown path.")
    parser.add_argument("--out-prefix", required=True, help="Output figure prefix.")
    return parser.parse_args()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_ndjson(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    parse_errors = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            rows.append(obj if isinstance(obj, dict) else {})
    return rows, parse_errors


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _correction_indices(response: dict[str, Any]) -> set[int]:
    correction = response.get("correction", {})
    if not isinstance(correction, dict):
        correction = {}
    flips = correction.get("qubit_flips_x")
    if not isinstance(flips, list):
        flips = correction.get("qubit_flips", [])
    if not isinstance(flips, list):
        flips = []
    return {_safe_int(item) for item in flips}


def _parity(indices: set[int], logical_indices: list[int]) -> int:
    value = 0
    for idx in logical_indices:
        if idx in indices:
            value ^= 1
    return value


def _wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((phat * (1.0 - phat) / n) + (z * z / (4.0 * n * n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _status(*, truth_path: Path, response_path: Path, truth_parse_errors: int, response_parse_errors: int, truth_lines: int, response_lines: int) -> str:
    if not truth_path.exists():
        return "missing_truth"
    if not response_path.exists():
        return "missing_response"
    if truth_parse_errors or response_parse_errors:
        return "parse_errors"
    if truth_lines != response_lines:
        return "line_count_mismatch"
    return "ok"


def _analyze_cell(dataset: str, decoder: str, truth_path: Path, response_path: Path) -> dict[str, Any]:
    if not truth_path.exists() or not response_path.exists():
        return {
            "dataset": dataset,
            "decoder": decoder,
            "status": _status(
                truth_path=truth_path,
                response_path=response_path,
                truth_parse_errors=0,
                response_parse_errors=0,
                truth_lines=0,
                response_lines=0,
            ),
            "truth_lines": 0,
            "response_lines": 0,
            "valid_lines": 0,
            "logical_error_count": 0,
            "logical_error_rate": float("nan"),
            "logical_error_ci95_low": float("nan"),
            "logical_error_ci95_high": float("nan"),
            "logical_observable": "",
            "truth_model": "",
            "truth_file": truth_path.name,
            "response_file": response_path.name,
        }

    truth_rows, truth_parse_errors = _load_ndjson(truth_path)
    response_rows, response_parse_errors = _load_ndjson(response_path)
    paired = min(len(truth_rows), len(response_rows))
    logical_errors = 0
    valid = 0
    logical_observable = ""
    truth_model = ""

    for idx in range(paired):
        truth = truth_rows[idx]
        response = response_rows[idx]
        logical_indices = truth.get("logical_indices", [])
        if not isinstance(logical_indices, list):
            continue
        logical_indices_int = [_safe_int(item) for item in logical_indices]
        truth_value = _safe_int(truth.get("logical_truth", 0)) & 1
        correction_value = _parity(_correction_indices(response), logical_indices_int)
        residual_value = truth_value ^ correction_value
        logical_errors += residual_value
        valid += 1
        logical_observable = str(truth.get("logical_observable", logical_observable))
        truth_model = str(truth.get("truth_model", truth_model))

    low, high = _wilson(logical_errors, valid)
    return {
        "dataset": dataset,
        "decoder": decoder,
        "status": _status(
            truth_path=truth_path,
            response_path=response_path,
            truth_parse_errors=truth_parse_errors,
            response_parse_errors=response_parse_errors,
            truth_lines=len(truth_rows),
            response_lines=len(response_rows),
        ),
        "truth_lines": len(truth_rows),
        "response_lines": len(response_rows),
        "valid_lines": valid,
        "logical_error_count": logical_errors,
        "logical_error_rate": logical_errors / valid if valid else float("nan"),
        "logical_error_ci95_low": low,
        "logical_error_ci95_high": high,
        "logical_observable": logical_observable,
        "truth_model": truth_model,
        "truth_file": truth_path.name,
        "response_file": response_path.name,
    }


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.6f}"
    return value


def _write_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    fields = [
        "dataset",
        "decoder",
        "status",
        "truth_lines",
        "response_lines",
        "valid_lines",
        "logical_error_count",
        "logical_error_rate",
        "logical_error_ci95_low",
        "logical_error_ci95_high",
        "logical_observable",
        "truth_model",
        "truth_file",
        "response_file",
    ]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _fmt(row.get(field, "")) for field in fields})


def _write_md(rows: list[dict[str, Any]], out_md: Path) -> None:
    fields = ["dataset", "decoder", "status", "valid_lines", "logical_error_count", "logical_error_rate", "logical_error_ci95_low", "logical_error_ci95_high"]
    with out_md.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("| " + " | ".join(["---"] * len(fields)) + " |\n")
        for row in rows:
            f.write("| " + " | ".join(str(_fmt(row.get(field, ""))) for field in fields) + " |\n")


def _plot(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping LER plot ({exc}).")
        return

    ok_rows = [r for r in rows if str(r.get("status", "")) == "ok"]
    if not ok_rows:
        return

    datasets = sorted({str(r.get("dataset", "")) for r in ok_rows})
    decoders = sorted({str(r.get("decoder", "")) for r in ok_rows})
    colors = {"bp": "#1f77b4", "mwpm": "#2ca02c", "uf": "#d62728"}

    x = np.arange(len(datasets), dtype=float)
    width = 0.22 if len(decoders) > 1 else 0.45
    offsets = np.linspace(-width * (len(decoders) - 1), width * (len(decoders) - 1), len(decoders)) if decoders else []
    fig, ax = plt.subplots(figsize=(7.4, 4.1), dpi=320, constrained_layout=True)

    for d_idx, decoder in enumerate(decoders):
        vals = []
        lows = []
        highs = []
        for dataset in datasets:
            row = next((r for r in ok_rows if str(r.get("dataset", "")) == dataset and str(r.get("decoder", "")) == decoder), None)
            v = float(row.get("logical_error_rate", float("nan"))) if row else float("nan")
            lo = float(row.get("logical_error_ci95_low", float("nan"))) if row else float("nan")
            hi = float(row.get("logical_error_ci95_high", float("nan"))) if row else float("nan")
            vals.append(v)
            lows.append(max(0.0, v - lo) if np.isfinite(v) and np.isfinite(lo) else 0.0)
            highs.append(max(0.0, hi - v) if np.isfinite(v) and np.isfinite(hi) else 0.0)
        pos = x + float(offsets[d_idx] if len(decoders) > 1 else 0.0)
        ax.bar(pos, vals, width=width, color=colors.get(decoder, "#6B7280"), label=decoder.upper(), alpha=0.86)
        ax.errorbar(pos, vals, yerr=[lows, highs], fmt="none", ecolor="#111827", elinewidth=0.8, capsize=2.4)

    ax.set_xticks(x)
    ax.set_xticklabels(datasets, rotation=20, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Logical error rate")
    ax.set_title("Outer-code logical-parity error rate")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, ncol=min(3, len(decoders)))

    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    truth_dir = Path(args.truth_dir)
    responses_dir = Path(args.responses_dir)
    manifest_rows = _read_csv(Path(args.replay_manifest))

    rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        dataset = str(row.get("dataset", "")).strip()
        decoder = str(row.get("decoder", "")).strip()
        response_file = str(row.get("response_file", "")).strip()
        if not dataset or not decoder or not response_file:
            continue
        rows.append(
            _analyze_cell(
                dataset=dataset,
                decoder=decoder,
                truth_path=truth_dir / f"truth_{dataset}.ndjson",
                response_path=responses_dir / response_file,
            )
        )

    _write_csv(rows, Path(args.out_csv))
    _write_md(rows, Path(args.out_md))
    _plot(rows, Path(args.out_prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
