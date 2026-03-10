#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def parse_inputs(values):
    parsed = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected label=path, got: {value}")
        label, path = value.split("=", 1)
        parsed.append((label.strip(), Path(path.strip())))
    return parsed


def fmt_number(value):
    if value is None:
        return "nan"
    try:
        return f"{float(value):.6g}"
    except (TypeError, ValueError):
        return "nan"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize LiDMaS scaling-summary JSON files.")
    parser.add_argument("--input", action="append", required=True, help="Decoder label and JSON path as label=path")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    inputs = parse_inputs(args.input)
    rows = []
    for label, path in inputs:
        if not path.exists():
            raise FileNotFoundError(f"missing JSON file: {path}")
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        collapse = data.get("collapse", {}) or {}
        rows.append(
            {
                "decoder": label,
                "crossing_median_pc": fmt_number(data.get("crossing_median_pc")),
                "crossing_median_pc_low": fmt_number(data.get("crossing_median_pc_low")),
                "crossing_median_pc_high": fmt_number(data.get("crossing_median_pc_high")),
                "collapse_pc": fmt_number(collapse.get("pc")),
                "collapse_pc_low": fmt_number(collapse.get("pc_low")),
                "collapse_pc_high": fmt_number(collapse.get("pc_high")),
                "collapse_nu": fmt_number(collapse.get("nu")),
                "collapse_cost": fmt_number(collapse.get("cost")),
            }
        )

    fieldnames = [
        "decoder",
        "crossing_median_pc",
        "crossing_median_pc_low",
        "crossing_median_pc_high",
        "collapse_pc",
        "collapse_pc_low",
        "collapse_pc_high",
        "collapse_nu",
        "collapse_cost",
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
        f.write("# Threshold Summary\n\n")
        f.write("| " + " | ".join(fieldnames) + " |\n")
        f.write("|" + "|".join(["---"] * len(fieldnames)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(row[field] for field in fieldnames) + " |\n")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
