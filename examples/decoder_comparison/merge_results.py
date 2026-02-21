#!/usr/bin/env python3
import argparse
import csv
import math
from typing import Dict, List


def read_rows(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def curve_map(rows: List[dict]) -> Dict[float, float]:
    out: Dict[float, float] = {}
    for row in rows:
        try:
            p = float(row.get("pauli_p", "nan"))
            ler = float(row.get("ler", "nan"))
        except ValueError:
            continue
        if math.isfinite(p) and math.isfinite(ler):
            out[p] = ler
    return out


def identical_curve(a: Dict[float, float], b: Dict[float, float], tol: float = 1e-15) -> bool:
    if not a or not b:
        return False
    if set(a.keys()) != set(b.keys()):
        return False
    for p in a:
        if abs(a[p] - b[p]) > tol:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge decoder comparison CSV outputs.")
    parser.add_argument("--mwpm", required=True)
    parser.add_argument("--uf", required=True)
    parser.add_argument("--neural", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    sources = [
        ("mwpm", args.mwpm),
        ("uf", args.uf),
        ("neural", args.neural),
    ]

    merged_rows: List[dict] = []
    base_fields: List[str] = []
    curves: Dict[str, Dict[float, float]] = {}

    for decoder_name, path in sources:
        rows = read_rows(path)
        if not rows:
            raise RuntimeError(f"No rows found in {path}")
        if not base_fields:
            base_fields = list(rows[0].keys())
        curves[decoder_name] = curve_map(rows)
        for row in rows:
            merged = {"decoder": decoder_name}
            merged.update(row)
            merged_rows.append(merged)

    fieldnames = ["decoder"] + base_fields
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_rows)

    mwpm_curve = curves.get("mwpm", {})
    warn = False
    for name in ("uf", "neural"):
        if identical_curve(mwpm_curve, curves.get(name, {})):
            warn = True
            break
    if warn:
        print("WARNING: Decoder results identical to MWPM — check neural model.")

    print(f"Wrote merged CSV: {args.out}")


if __name__ == "__main__":
    main()
