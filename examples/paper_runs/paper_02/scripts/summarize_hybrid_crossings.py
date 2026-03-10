#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def parse_inputs(values):
    parsed = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected label=path, got: {value}")
        label, path = value.split("=", 1)
        parsed.append((label.strip(), Path(path.strip())))
    return parsed


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def estimate_crossing(rows, d_low, d_high):
    by_distance = {d_low: {}, d_high: {}}
    for row in rows:
        distance = int(float(row["distance"]))
        if distance not in by_distance:
            continue
        sigma = float(row["sigma"])
        by_distance[distance][sigma] = float(row["ler"])

    common_sigma = sorted(set(by_distance[d_low]) & set(by_distance[d_high]))
    if not common_sigma:
        return {"crossing_sigma": "nan", "method": "no_overlap", "min_abs_delta_ler": "nan"}

    diffs = []
    for sigma in common_sigma:
        diffs.append((sigma, by_distance[d_low][sigma] - by_distance[d_high][sigma]))

    for idx, (sigma, diff) in enumerate(diffs):
        if diff == 0.0:
            return {
                "crossing_sigma": f"{sigma:.6g}",
                "method": "grid_exact",
                "min_abs_delta_ler": "0",
            }
        if idx == len(diffs) - 1:
            continue
        next_sigma, next_diff = diffs[idx + 1]
        if diff * next_diff < 0:
            crossing = sigma + (0.0 - diff) * (next_sigma - sigma) / (next_diff - diff)
            min_abs = min(abs(diff), abs(next_diff))
            return {
                "crossing_sigma": f"{crossing:.6g}",
                "method": "linear_interp",
                "min_abs_delta_ler": f"{min_abs:.6g}",
            }

    sigma, diff = min(diffs, key=lambda item: abs(item[1]))
    return {
        "crossing_sigma": f"{sigma:.6g}",
        "method": "min_abs_delta",
        "min_abs_delta_ler": f"{abs(diff):.6g}",
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize hybrid decoder crossings from LiDMaS CSV outputs.")
    parser.add_argument("--input", action="append", required=True, help="Decoder label and CSV path as label=path")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    rows = []
    for label, path in parse_inputs(args.input):
        if not path.exists():
            raise FileNotFoundError(f"missing CSV file: {path}")
        data = load_rows(path)
        pair_35 = estimate_crossing(data, 3, 5)
        pair_57 = estimate_crossing(data, 5, 7)
        rows.append(
            {
                "decoder": label,
                "crossing_d3_d5_sigma": pair_35["crossing_sigma"],
                "crossing_d3_d5_method": pair_35["method"],
                "crossing_d3_d5_min_abs_delta_ler": pair_35["min_abs_delta_ler"],
                "crossing_d5_d7_sigma": pair_57["crossing_sigma"],
                "crossing_d5_d7_method": pair_57["method"],
                "crossing_d5_d7_min_abs_delta_ler": pair_57["min_abs_delta_ler"],
            }
        )

    fieldnames = [
        "decoder",
        "crossing_d3_d5_sigma",
        "crossing_d3_d5_method",
        "crossing_d3_d5_min_abs_delta_ler",
        "crossing_d5_d7_sigma",
        "crossing_d5_d7_method",
        "crossing_d5_d7_min_abs_delta_ler",
    ]

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Hybrid Crossing Summary\n\n")
        f.write("| " + " | ".join(fieldnames) + " |\n")
        f.write("|" + "|".join(["---"] * len(fieldnames)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(row[field] for field in fieldnames) + " |\n")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
