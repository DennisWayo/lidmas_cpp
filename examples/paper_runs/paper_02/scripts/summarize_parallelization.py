#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def format_float(value):
    if value is None or math.isnan(value):
        return "nan"
    return f"{value:.6g}"


def safe_mean(values):
    if not values:
        return math.nan
    return sum(values) / len(values)


def load_series(csv_path, mode):
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"missing CSV: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}

    first = rows[0]
    x_col = "pauli_p" if mode == "pauli" else "sigma"
    if x_col not in first:
        x_col = "sigma" if "sigma" in first else "pauli_p"

    series = {}
    for row in rows:
        key = (str(row.get("distance", "")), str(row.get(x_col, "")))
        series[key] = (
            parse_float(row.get("ler")),
            parse_float(row.get("decoder_fail_rate")),
        )
    return series


def compare_series(reference, candidate):
    common_keys = sorted(set(reference.keys()) & set(candidate.keys()))
    ler_deltas = []
    fail_deltas = []
    for key in common_keys:
        ref_ler, ref_fail = reference[key]
        cand_ler, cand_fail = candidate[key]
        if not (math.isnan(ref_ler) or math.isnan(cand_ler)):
            ler_deltas.append(abs(ref_ler - cand_ler))
        if not (math.isnan(ref_fail) or math.isnan(cand_fail)):
            fail_deltas.append(abs(ref_fail - cand_fail))

    return {
        "points_compared": len(common_keys),
        "max_abs_delta_ler": max(ler_deltas) if ler_deltas else math.nan,
        "mean_abs_delta_ler": safe_mean(ler_deltas),
        "max_abs_delta_fail_rate": max(fail_deltas) if fail_deltas else math.nan,
        "mean_abs_delta_fail_rate": safe_mean(fail_deltas),
    }


def select_reference(rows, mode):
    target_label = f"{mode}_serial"
    for row in rows:
        if row.get("label") == target_label:
            return row
    for row in rows:
        if row.get("threads") == "1" and row.get("gpu", "0") in ("0", "false", "False", ""):
            return row
    return rows[0]


def main():
    parser = argparse.ArgumentParser(description="Summarize LiDMaS serial vs parallel comparisons.")
    parser.add_argument("--timings", required=True, help="CSV written by 06_parallelization.sh")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    timings_path = Path(args.timings)
    if not timings_path.exists():
        raise FileNotFoundError(f"missing timings file: {timings_path}")

    with timings_path.open(newline="", encoding="utf-8") as f:
        timing_rows = list(csv.DictReader(f))
    if not timing_rows:
        raise RuntimeError("timings CSV has no rows")

    by_mode = {}
    for row in timing_rows:
        mode = row.get("mode", "")
        by_mode.setdefault(mode, []).append(row)

    summary = []
    for mode, rows in by_mode.items():
        if len(rows) < 2:
            continue
        reference = select_reference(rows, mode)
        ref_label = reference.get("label", "")
        ref_seconds = parse_float(reference.get("seconds"))
        ref_series = load_series(reference.get("csv_path", ""), mode)

        for candidate in rows:
            cand_label = candidate.get("label", "")
            if cand_label == ref_label:
                continue
            cand_seconds = parse_float(candidate.get("seconds"))
            cand_series = load_series(candidate.get("csv_path", ""), mode)
            metrics = compare_series(ref_series, cand_series)
            speedup = math.nan
            if not (math.isnan(ref_seconds) or math.isnan(cand_seconds) or cand_seconds <= 0.0):
                speedup = ref_seconds / cand_seconds

            summary.append(
                {
                    "mode": mode,
                    "reference": ref_label,
                    "candidate": cand_label,
                    "points_reference": str(len(ref_series)),
                    "points_candidate": str(len(cand_series)),
                    "points_compared": str(metrics["points_compared"]),
                    "max_abs_delta_ler": format_float(metrics["max_abs_delta_ler"]),
                    "mean_abs_delta_ler": format_float(metrics["mean_abs_delta_ler"]),
                    "max_abs_delta_fail_rate": format_float(metrics["max_abs_delta_fail_rate"]),
                    "mean_abs_delta_fail_rate": format_float(metrics["mean_abs_delta_fail_rate"]),
                    "serial_seconds": format_float(ref_seconds),
                    "candidate_seconds": format_float(cand_seconds),
                    "speedup": format_float(speedup),
                }
            )

    fieldnames = [
        "mode",
        "reference",
        "candidate",
        "points_reference",
        "points_candidate",
        "points_compared",
        "max_abs_delta_ler",
        "mean_abs_delta_ler",
        "max_abs_delta_fail_rate",
        "mean_abs_delta_fail_rate",
        "serial_seconds",
        "candidate_seconds",
        "speedup",
    ]

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Parallelization Summary\n\n")
        f.write("| " + " | ".join(fieldnames) + " |\n")
        f.write("|" + "|".join(["---"] * len(fieldnames)) + "|\n")
        for row in summary:
            f.write("| " + " | ".join(row.get(field, "") for field in fieldnames) + " |\n")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
