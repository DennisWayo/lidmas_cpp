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
        label = label.strip()
        path = path.strip()
        if not label or not path:
            raise ValueError(f"invalid input mapping: {value}")
        parsed.append((label, Path(path)))
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge LiDMaS surface-threshold CSV files with decoder labels.")
    parser.add_argument("--input", action="append", required=True, help="Decoder label and CSV path as label=path")
    parser.add_argument("--out", required=True, help="Output merged CSV path")
    args = parser.parse_args()

    inputs = parse_inputs(args.input)
    merged_rows = []
    base_fields = None

    for label, path in inputs:
      if not path.exists():
        raise FileNotFoundError(f"missing input CSV: {path}")
      with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
      if not rows:
        raise RuntimeError(f"no rows found in {path}")
      if base_fields is None:
        base_fields = list(rows[0].keys())
      for row in rows:
        merged = {"decoder": label}
        merged.update(row)
        merged_rows.append(merged)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=["decoder"] + base_fields)
      writer.writeheader()
      writer.writerows(merged_rows)
    print(f"Wrote merged CSV: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

